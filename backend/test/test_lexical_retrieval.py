"""Milvus BM25 schema, routing, fallback, and real-server tests."""

from __future__ import annotations

import os
import tempfile
import uuid
import warnings
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

import pytest

from service.milvus_service import (
    MilvusService,
    lexical_collection_name,
)
from service.retrieval_service import _collect_lexical_candidates
from service.docmind_service import process_document_with_docmind


def _collector(service, **environment):
    defaults = {
        "RAG_LEXICAL_BACKEND": "auto",
        "RAG_LEXICAL_FALLBACK_ENABLED": "true",
        "RAG_LEXICAL_TOP_K": "2",
        "RAG_RETRIEVAL_RRF_K": "60",
    }
    defaults.update(environment)
    with patch.dict(os.environ, defaults, clear=True):
        return _collect_lexical_candidates(
            service,
            dense_collection_name="kb_demo_dense",
            bm25_collection_name="kb_demo_bm25_v1",
            query_variants=["chiplet packaging", "advanced packaging"],
            query_focus_terms=[[], ["advanced packaging"]],
            question="chiplet advanced packaging",
            candidate_k=2,
            kb_id=None,
        )


def test_lexical_collection_name_is_versioned_and_validated():
    with patch.dict(os.environ, {"RAG_LEXICAL_COLLECTION_SUFFIX": "_bm25_v2"}):
        assert lexical_collection_name("kb_demo") == "kb_demo_bm25_v2"
    with patch.dict(os.environ, {"RAG_LEXICAL_COLLECTION_SUFFIX": "-invalid"}):
        with pytest.raises(ValueError, match="only letters"):
            lexical_collection_name("kb_demo")


def test_milvus_bm25_path_is_bounded_and_does_not_scan():
    service = Mock()
    service.supports_lexical_search.return_value = True
    service.search_lexical.side_effect = [
        [
            {"id": "shared", "doc_id": "a", "content": "chiplet packaging", "bm25_score": 3.0},
            {"id": "first", "doc_id": "b", "content": "chiplet", "bm25_score": 1.5},
        ],
        [
            {"id": "shared", "doc_id": "a", "content": "advanced packaging", "bm25_score": 2.5},
        ],
    ]

    candidates, backend, degradation = _collector(service)

    assert backend == "milvus_bm25"
    assert degradation is None
    assert set(candidates) == {"shared", "first"}
    assert candidates["shared"]["sparse_rrf_score"] > candidates["first"]["sparse_rrf_score"]
    assert service.search_lexical.call_count == 2
    service.list_chunks.assert_not_called()


def test_auto_mode_falls_back_to_scan_with_explicit_degradation():
    service = Mock()
    service.supports_lexical_search.return_value = False
    service.list_chunks.return_value = [
        {"id": "a", "doc_id": "doc-a", "content": "advanced chiplet packaging"},
        {"id": "b", "doc_id": "doc-b", "content": "wafer lithography"},
    ]
    service.get_collection_stats.return_value = {"num_entities": 2}

    candidates, backend, degradation = _collector(service)

    assert backend == "scan"
    assert degradation and "BM25 index unavailable" in degradation
    assert candidates["a"]["sparse_rrf_score"] > 0
    assert candidates["b"].get("sparse_rrf_score", 0) == 0


def test_strict_milvus_mode_fails_closed_when_fallback_is_disabled():
    service = Mock()
    service.supports_lexical_search.return_value = False
    with pytest.raises(LookupError, match="BM25 index unavailable"):
        _collector(
            service,
            RAG_LEXICAL_BACKEND="milvus",
            RAG_LEXICAL_FALLBACK_ENABLED="false",
        )
    service.list_chunks.assert_not_called()


def test_document_ingestion_updates_bm25_once_after_all_dense_routes(tmp_path):
    document = tmp_path / "evidence.md"
    document.write_text("# Packaging\n\nChiplet interconnect evidence.", encoding="utf-8")
    cloud = SimpleNamespace(
        name="cloud", provider="bailian", api_key="key", base_url="url",
        model="text-embedding-v4", model_slug="text_v4", dimensions=2, version="v1",
    )
    local = SimpleNamespace(
        name="local", provider="ollama", api_key="key", base_url="url",
        model="bge-m3", model_slug="bge_m3", dimensions=2, version="v1",
    )
    service = Mock()
    service.insert_documents.return_value = 1
    service.insert_lexical_documents.return_value = 1
    with patch.dict(
        os.environ,
        {"RAG_LEXICAL_BACKEND": "milvus", "RAG_LEXICAL_COLLECTION_SUFFIX": "_bm25_v1"},
    ), patch(
        "service.docmind_service.routes_for_ingestion",
        return_value=(cloud, local),
    ), patch(
        "service.docmind_service.generate_embedding",
        return_value=[[1.0, 0.0]],
    ):
        result = process_document_with_docmind(
            str(document),
            document.name,
            "kb_demo",
            milvus_service=service,
        )

    assert result["success"] is True
    assert result["embedding_routes"] == ["cloud", "local"]
    assert result["lexical_index"] == "kb_demo_bm25_v1"
    assert service.insert_documents.call_count == 2
    service.insert_lexical_documents.assert_called_once()


@pytest.mark.integration
def test_milvus_bm25_round_trip():
    collection_name = f"bm25_test_{uuid.uuid4().hex[:12]}"
    previous_tempdir = tempfile.tempdir
    tempfile.tempdir = "/tmp"
    try:
        with tempfile.TemporaryDirectory(dir="/tmp") as temp_dir, patch.dict(
            os.environ,
            {
                "MILVUS_URI": str(Path(temp_dir) / "lexical.db"),
                # Milvus Lite validates the BM25 protocol but does not ship the
                # ICU tokenizer available in Standalone 2.6.17.
                "RAG_LEXICAL_TOKENIZER": "standard",
            },
            clear=False,
        ):
            # The project still uses the PyMilvus ORM API consistently. 2.6
            # warns about its future 3.1 removal, which is an upgrade signal,
            # not a failure of this BM25 protocol test.
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                service = MilvusService()
                try:
                    service.insert_lexical_documents(
                        collection_name,
                        [
                            {
                                "id": "packaging",
                                "doc_id": "doc-a",
                                "kb_id": "kb-a",
                                "filename": "packaging.md",
                                "content": (
                                    "advanced packaging uses chiplet "
                                    "interconnect technology"
                                ),
                                "chunk_index": 0,
                            },
                            {
                                "id": "lithography",
                                "doc_id": "doc-b",
                                "kb_id": "kb-a",
                                "filename": "fab.md",
                                "content": "wafer lithography process control",
                                "chunk_index": 0,
                            },
                        ],
                    )
                    hits = service.search_lexical(
                        collection_name,
                        "chiplet packaging",
                        top_k=1,
                    )
                    assert hits[0]["id"] == "packaging"
                    assert hits[0]["bm25_score"] > 0
                finally:
                    assert service.delete_collection(collection_name)
                    from pymilvus import connections

                    connections.disconnect("default")
    finally:
        tempfile.tempdir = previous_tempdir
