"""公开资料治理的离线单元测试。"""
from pathlib import Path
import math
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch
from types import SimpleNamespace

APP_DIR = Path(__file__).resolve().parents[1] / "app"
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

from service.source_governance import (  # noqa: E402
    SourceCandidate,
    allowed_domain,
    deduplicate,
    download_and_normalize,
    normalize_pdf_text,
    portable_managed_path,
    resolve_managed_path,
)
from service.docmind_service import chunk_markdown  # noqa: E402
from service.milvus_service import MilvusService  # noqa: E402
from service.retrieval_service import (  # noqa: E402
    _build_query_variants,
    _expand_with_neighbor_chunks,
    _passes_strict_identifier_gate,
    _select_facet_diverse_results,
    _strict_identifier_score,
    _technical_exact_score,
)
from scripts.evaluate_rag_retrieval import (  # noqa: E402
    evaluate_gold_sources,
    gold_ranking_metrics,
    gold_document_names,
    normalize_evidence_text,
    required_group_coverage,
)
from scripts.evaluate_rag_answers import (  # noqa: E402
    evaluate_gold_citations,
    normalize_match_text,
)
from service.scheduler_service import collection_sources_configured  # noqa: E402
from service.embedding_service import generate_embedding  # noqa: E402
from scripts.ingest_approved_sources import ingest_candidate  # noqa: E402


def make_candidate(candidate_id: str, fulltext_url: str) -> SourceCandidate:
    candidate = SourceCandidate(
        candidate_id=candidate_id,
        source_id="test",
        source_name="Test Standard Body",
        title=f"Document {candidate_id}",
        domains=["chip_design_eda_ip"],
        document_type="technical_standard",
        source_url="https://example.org/specifications",
        fulltext_url=fulltext_url,
        authority_level="industry_standard",
        claim_type="industry_standard",
        license_url="https://example.org/license",
        ingestion_policy="fulltext_allowed",
        review_status="approved",
    )
    candidate.validate()
    candidate.calculate_quality()
    return candidate


class SourceGovernanceTests(unittest.TestCase):
    def test_failed_ingestion_is_committed_and_safe_to_retry(self):
        class FakeQuery:
            def __init__(self, value):
                self.value = value

            def filter(self, *args):
                return self

            def first(self):
                return self.value

        class FakeDb:
            def __init__(self, kb, document):
                self.kb = kb
                self.document = document
                self.commits = 0
                self.rollbacks = 0

            def query(self, model):
                from models.knowledge import Document, KnowledgeBase
                return FakeQuery(self.kb if model is KnowledgeBase else self.document)

            def add(self, value):
                return None

            def commit(self):
                self.commits += 1

            def rollback(self):
                self.rollbacks += 1

        candidate = make_candidate("one", "https://example.org/one.pdf")
        candidate.local_normalized_path = "normalized/one.md"
        candidate.content_hash = "a" * 64
        document = SimpleNamespace(status="failed", chunk_count=9, error_message="old")
        kb = SimpleNamespace(id="kb-id", document_count=1)
        db = FakeDb(kb, document)
        milvus = SimpleNamespace(delete_by_doc_id=lambda *args: True)

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            path = root / candidate.local_normalized_path
            path.parent.mkdir()
            path.write_text("# Evidence\n\nTraceable evidence.", encoding="utf-8")
            with patch(
                "scripts.ingest_approved_sources.get_milvus_service", return_value=milvus,
            ), patch(
                "scripts.ingest_approved_sources.process_document_with_docmind",
                return_value={"success": False, "message": "embedding failed", "document_count": 0},
            ):
                with self.assertRaisesRegex(RuntimeError, "embedding failed"):
                    ingest_candidate(
                        db, SimpleNamespace(id="user-id"), candidate,
                        "chip_design_eda_ip", False, 1200, True, root,
                    )

        self.assertEqual(document.status, "failed")
        self.assertEqual(document.chunk_count, 0)
        self.assertEqual(document.error_message, "embedding failed")
        self.assertEqual(db.commits, 2)
        self.assertEqual(db.rollbacks, 1)

    def test_ingestion_stops_when_orphan_cleanup_fails(self):
        class FakeQuery:
            def __init__(self, value):
                self.value = value

            def filter(self, *args):
                return self

            def first(self):
                return self.value

        class FakeDb:
            def __init__(self, kb, document):
                self.values = {"KnowledgeBase": kb, "Document": document}

            def query(self, model):
                return FakeQuery(self.values[model.__name__])

            def commit(self):
                return None

            def rollback(self):
                return None

        candidate = make_candidate("one", "https://example.org/one.pdf")
        candidate.local_normalized_path = "normalized/one.md"
        candidate.content_hash = "a" * 64
        document = SimpleNamespace(status="failed", chunk_count=2, error_message=None)
        db = FakeDb(SimpleNamespace(id="kb-id", document_count=1), document)

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            path = root / candidate.local_normalized_path
            path.parent.mkdir()
            path.write_text("# Evidence\n\nTraceable evidence.", encoding="utf-8")
            with patch(
                "scripts.ingest_approved_sources.get_milvus_service",
                return_value=SimpleNamespace(delete_by_doc_id=lambda *args: False),
            ), patch(
                "scripts.ingest_approved_sources.process_document_with_docmind",
            ) as process:
                with self.assertRaisesRegex(RuntimeError, "旧向量删除失败"):
                    ingest_candidate(
                        db, SimpleNamespace(id="user-id"), candidate,
                        "chip_design_eda_ip", False, 1200, True, root,
                    )
                process.assert_not_called()
        self.assertEqual(document.status, "failed")
        self.assertEqual(document.chunk_count, 0)

    def test_manifest_paths_are_portable_and_cannot_escape_source_root(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            document = root / "normalized" / "document.md"
            document.parent.mkdir()
            document.write_text("evidence", encoding="utf-8")

            portable = portable_managed_path(root, str(document))
            self.assertEqual(portable, "normalized/document.md")
            self.assertEqual(resolve_managed_path(root, portable), document)
            with self.assertRaisesRegex(ValueError, "路径越界"):
                resolve_managed_path(root, "../outside.md")

    def test_embedding_batches_retry_and_preserve_order(self):
        class FakeEmbeddings:
            calls = 0

            def create(self, **kwargs):
                self.calls += 1
                if self.calls == 1:
                    raise RuntimeError("temporary")
                return SimpleNamespace(data=[
                    SimpleNamespace(embedding=[float(ord(value[0]))])
                    for value in kwargs["input"]
                ])

        fake = FakeEmbeddings()
        client = SimpleNamespace(embeddings=fake)
        with patch(
            "service.embedding_service.OpenAI", return_value=client
        ), patch(
            "service.embedding_service.time.sleep"
        ), patch.dict(
            "os.environ", {"EMBEDDING_PROGRESS_EVERY_BATCHES": "1"}
        ):
            vectors = generate_embedding(
                ["a", "b", "c"], api_key="test", max_batch_size=2, max_retries=1
            )
        self.assertEqual(vectors, [[97.0], [98.0], [99.0]])
        self.assertEqual(fake.calls, 3)

    def test_pdf_normalization_removes_repeated_margins_and_repairs_words(self):
        pages = []
        for number in range(1, 4):
            pages.append(
                "CHIPS FOR AMERICA\n"
                "Public technical report\n"
                "ADVANCED METROLOGY\n"
                "Semicon-\n"
                "ductor manufacturing needs traceable measurements.\n"
                "The in-\n"
                "depth review remains auditable.\n"
                "• Inspect voids and interfaces\n"
                "across every buried layer\n"
                "\n# assembler comment\n"
                "Calibration supports comparison.\n"
                "Results remain auditable.\n"
                f"Page {number}"
            )
        normalized = normalize_pdf_text("\f".join(pages))
        self.assertNotIn("CHIPS FOR AMERICA", normalized)
        self.assertNotIn("Page 1", normalized)
        self.assertIn("## ADVANCED METROLOGY", normalized)
        self.assertIn("Semiconductor manufacturing", normalized)
        self.assertIn("in-depth review", normalized)
        self.assertIn("- Inspect voids and interfaces across every buried layer", normalized)
        self.assertIn(r"\# assembler comment", normalized)

    def test_pdf_normalization_does_not_strip_repeated_body_claim(self):
        text = "\f".join(
            f"Report header\nSection {number}\nUnique introduction {number}.\n"
            "Process control is essential.\nEvidence remains traceable.\n"
            f"Unique conclusion {number}.\nPage {number}"
            for number in range(1, 4)
        )
        normalized = normalize_pdf_text(text)
        self.assertEqual(normalized.count("Process control is essential."), 3)

    def test_subdomain_whitelist(self):
        self.assertTrue(allowed_domain("https://docs.example.org/a.pdf", ["example.org"]))
        self.assertFalse(allowed_domain("https://example.org.evil.test/a.pdf", ["example.org"]))

    def test_distinct_documents_on_same_index_page_are_preserved(self):
        first = make_candidate("one", "https://example.org/one.pdf")
        second = make_candidate("two", "https://example.org/two.pdf")
        self.assertEqual(len(deduplicate([first, second])), 2)

    def test_metadata_only_cannot_be_approved_for_fulltext(self):
        candidate = make_candidate("one", "https://example.org/one.pdf")
        candidate.ingestion_policy = "metadata_only"
        with self.assertRaisesRegex(ValueError, "fulltext_allowed"):
            candidate.validate()

    def test_quality_score_rewards_traceability(self):
        candidate = make_candidate("one", "https://example.org/one.pdf")
        self.assertGreaterEqual(candidate.quality_score, 65)

    def test_markdown_fulltext_is_archived_and_normalized(self):
        candidate = make_candidate(
            "open-doc",
            "https://raw.githubusercontent.com/example/project/commit/docs/guide.md",
        )
        candidate.content_format = "markdown"
        markdown = ("# Open EDA Guide\n\nRTL to GDSII synthesis placement routing.\n" * 20).encode()

        class FakeResponse:
            url = candidate.fulltext_url

            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

            def raise_for_status(self):
                return None

            def iter_content(self, chunk_size):
                yield markdown

        with tempfile.TemporaryDirectory() as temp_dir, patch(
            "service.source_governance.requests.get",
            return_value=FakeResponse(),
        ):
            root = Path(temp_dir)
            result = download_and_normalize(
                candidate,
                {"allowed_domains": ["raw.githubusercontent.com"]},
                root / "raw",
                root / "normalized",
            )
            raw_path = Path(result.local_raw_path)
            normalized_path = Path(result.local_normalized_path)
            self.assertEqual(raw_path.suffix, ".md")
            self.assertEqual(raw_path.read_bytes(), markdown)
            normalized = normalized_path.read_text(encoding="utf-8")
            self.assertIn("content_format: markdown", normalized)
            self.assertIn("RTL to GDSII", normalized)

    def test_invalid_content_format_is_rejected(self):
        candidate = make_candidate("one", "https://example.org/one.txt")
        candidate.content_format = "html"
        with self.assertRaisesRegex(ValueError, "无效全文格式"):
            candidate.validate()

    def test_markdown_chunks_keep_heading_breadcrumb(self):
        text = (
            "# OpenROAD Flow\n\n"
            + ("overview content " * 60)
            + "\n\n## Detailed Routing\n\n"
            + ("DRC search and repair " * 60)
        )
        chunks = chunk_markdown(text, chunk_size=500, overlap=50)
        routing_chunks = [chunk for chunk in chunks if "DRC search" in chunk]
        self.assertTrue(routing_chunks)
        self.assertTrue(all(
            chunk.startswith("文档位置：OpenROAD Flow > Detailed Routing")
            for chunk in routing_chunks
        ))

    def test_neighbor_expansion_never_crosses_document(self):
        seeds = [{
            "id": "a-2",
            "doc_id": "doc-a",
            "chunk_index": 2,
            "score": 0.8,
        }]
        pool = [
            {"id": "a-1", "doc_id": "doc-a", "chunk_index": 1, "content": "before"},
            {"id": "a-3", "doc_id": "doc-a", "chunk_index": 3, "content": "after"},
            {"id": "b-1", "doc_id": "doc-b", "chunk_index": 1, "content": "other"},
        ]
        expanded = _expand_with_neighbor_chunks(seeds, pool, window=1, max_neighbors=4)
        self.assertEqual({item["id"] for item in expanded}, {"a-1", "a-2", "a-3"})
        self.assertTrue(all(item["doc_id"] == "doc-a" for item in expanded))
        self.assertTrue(all(item.get("is_neighbor") for item in expanded[1:]))

    def test_exact_eda_identifiers_receive_full_match_score(self):
        question = "如何调优 PLACE_DENSITY、CORE_UTILIZATION 和 PPA？"
        exact = _technical_exact_score(
            question,
            "Set PLACE_DENSITY and CORE_UTILIZATION, then compare PPA reports.",
        )
        partial = _technical_exact_score(question, "General OpenROAD placement guidance.")
        self.assertEqual(exact, 1.0)
        self.assertEqual(partial, 0.0)

    def test_gold_sources_support_any_and_all_modes(self):
        case = {
            "expected_retrieval": True,
            "gold_sources": [
                {"document": "a.md", "heading": "A"},
                "b.md",
            ],
        }
        results = [{"document_name": "b.md"}]
        self.assertEqual(gold_document_names(case), ["a.md", "b.md"])
        self.assertEqual(evaluate_gold_sources(case, results), (True, []))

        case["gold_source_match"] = "all"
        self.assertEqual(evaluate_gold_sources(case, results), (False, ["a.md"]))

    def test_gold_ranking_metrics_use_unique_document_ranks(self):
        case = {"expected_retrieval": True, "gold_sources": ["gold.md"]}
        results = [
            {"document_name": "other.md"},
            {"document_name": "other.md"},
            {"document_name": "gold.md"},
        ]
        rank, reciprocal_rank, ndcg = gold_ranking_metrics(case, results, top_k=3)
        self.assertEqual(rank, 2)
        self.assertEqual(reciprocal_rank, 0.5)
        self.assertAlmostEqual(ndcg, 1 / math.log2(3))

    def test_required_group_coverage_accepts_synonyms(self):
        case = {"required_term_groups": [["warpage", "翘曲"], ["voids", "空洞"]]}
        coverage, missing = required_group_coverage(
            case, normalize_evidence_text("Low warpage and 空洞 inspection"),
        )
        self.assertEqual(coverage, 1.0)
        self.assertEqual(missing, [])

    def test_evidence_matching_ignores_pdf_line_breaks(self):
        self.assertIn(
            normalize_evidence_text("control or optimization"),
            normalize_evidence_text("control or\n optimization"),
        )

    def test_answer_matching_ignores_layout_whitespace(self):
        answer = normalize_match_text("需要检查内部 3D结构和 power\n delivery。")
        self.assertIn(normalize_match_text("3D 结构"), answer)
        self.assertIn(normalize_match_text("power delivery"), answer)

    def test_news_scheduler_requires_at_least_one_provider(self):
        with patch.dict("os.environ", {}, clear=True):
            self.assertFalse(collection_sources_configured())
        with patch.dict("os.environ", {"BOCHA_API_KEY": "configured"}, clear=True):
            self.assertTrue(collection_sources_configured())

    def test_answer_citation_must_point_to_gold_document(self):
        case = {"gold_sources": [{"document": "gold.md"}]}
        documents = [
            {"document_name": "other.md"},
            {"document_name": "gold.md"},
        ]
        retrieved, cited, names, cited_names = evaluate_gold_citations(
            case,
            documents,
            [1],
        )
        self.assertTrue(retrieved)
        self.assertFalse(cited)
        self.assertEqual(names, ["other.md", "gold.md"])
        self.assertEqual(cited_names, ["other.md"])
        self.assertTrue(evaluate_gold_citations(case, documents, [2])[1])

    def test_strict_identifier_gate_does_not_filter_plain_acronyms(self):
        self.assertIsNone(_strict_identifier_score("PPA and RTL", "unrelated"))
        self.assertIsNone(_strict_identifier_score("2.5D/3D integration", "unrelated"))
        self.assertEqual(_strict_identifier_score("QFAB-X99", "unrelated"), 0.0)
        with patch.dict("os.environ", {"RAG_REQUIRE_ANY_STRICT_IDENTIFIER": "true"}):
            self.assertTrue(_passes_strict_identifier_gate(None))
            self.assertTrue(_passes_strict_identifier_gate(0.5))
            self.assertFalse(_passes_strict_identifier_gate(0.0))

    def test_multi_query_variants_add_auditable_domain_terms(self):
        variants = _build_query_variants(
            "先进封装为什么要检查翘曲、空洞、应力和粘附？",
            limit=4,
        )
        self.assertEqual(variants[0], "先进封装为什么要检查翘曲、空洞、应力和粘附？")
        combined = " ".join(variants).casefold()
        self.assertIn("warpage", combined)
        self.assertIn("voids", combined)
        self.assertIn("stresses", combined)
        self.assertIn("adhesion", combined)
        self.assertLessEqual(len(variants), 4)

    def test_combined_glossary_entry_becomes_independent_facets(self):
        plan = _build_query_variants(
            "还应规划哪些供应链、人才和安全能力？", limit=5
        )
        combined = " ".join(plan).casefold()
        self.assertIn("cybersecurity", combined)
        self.assertIn("operational security", combined)
        self.assertTrue(any("cybersecurity" in item.casefold() for item in plan[1:]))

    def test_single_broad_glossary_hit_does_not_trigger_rewrite(self):
        question = "半导体供应链面临什么风险？"
        self.assertEqual(_build_query_variants(question, limit=4), [question])

    def test_single_expansion_is_safe_with_strong_technical_anchor(self):
        variants = _build_query_variants(
            "SDC 中的时钟周期如何影响流程？", limit=4
        )
        self.assertGreater(len(variants), 1)
        self.assertIn("clock period", " ".join(variants).casefold())

    def test_facet_selection_reserves_evidence_for_each_subquery(self):
        rows = [
            {
                "id": "overall",
                "doc_id": "a",
                "score": 0.9,
                "query_relevance_scores": [0.9, 0.2, 0.1],
            },
            {
                "id": "facet-1",
                "doc_id": "a",
                "score": 0.7,
                "query_relevance_scores": [0.3, 0.95, 0.1],
            },
            {
                "id": "facet-2",
                "doc_id": "b",
                "score": 0.6,
                "query_relevance_scores": [0.1, 0.2, 0.96],
            },
        ]
        selected = _select_facet_diverse_results(rows, query_count=3, top_k=3)
        self.assertEqual(
            {row["id"] for row in selected},
            {"overall", "facet-1", "facet-2"},
        )

    def test_filename_chunk_query_is_reachable_and_sorted(self):
        class FakeCollection:
            def load(self):
                return None

            def query(self, **kwargs):
                self.kwargs = kwargs
                return [
                    {"id": "two", "chunk_index": 2},
                    {"id": "one", "chunk_index": 1},
                ]

        fake_collection = FakeCollection()
        service = MilvusService.__new__(MilvusService)
        with patch(
            "service.milvus_service.utility.has_collection",
            return_value=True,
        ), patch(
            "service.milvus_service.Collection",
            return_value=fake_collection,
        ):
            chunks = service.get_chunks_by_filename(
                "kb_test",
                'guide"quoted.md',
            )
        self.assertEqual([chunk["chunk_index"] for chunk in chunks], [1, 2])
        self.assertIn('guide\\"quoted.md', fake_collection.kwargs["expr"])

    def test_chunk_scan_cache_reuses_snapshot_and_can_be_invalidated(self):
        class FakeIterator:
            def __init__(self):
                self.returned = False

            def next(self):
                if self.returned:
                    return []
                self.returned = True
                return [{"id": "one", "content": "evidence"}]

            def close(self):
                return None

        class FakeCollection:
            query_count = 0

            def load(self):
                return None

            def query_iterator(self, **kwargs):
                self.query_count += 1
                return FakeIterator()

        fake_collection = FakeCollection()
        service = MilvusService.__new__(MilvusService)
        service._chunk_cache = {}
        service._chunk_cache_lock = threading.Lock()
        with patch.dict(
            "os.environ",
            {"RAG_CHUNK_CACHE_TTL_SECONDS": "300"},
        ), patch(
            "service.milvus_service.utility.has_collection",
            return_value=True,
        ), patch(
            "service.milvus_service.Collection",
            return_value=fake_collection,
        ):
            first = service.list_chunks("kb_test", limit=10)
            second = service.list_chunks("kb_test", limit=10)
            service._invalidate_chunk_cache("kb_test")
            third = service.list_chunks("kb_test", limit=10)
        self.assertEqual(first, second)
        self.assertEqual(second, third)
        self.assertEqual(fake_collection.query_count, 2)


if __name__ == "__main__":
    unittest.main()
