"""Contract tests for the blind-v2 retrieval evaluator."""

from __future__ import annotations

import asyncio
from pathlib import Path
import sys
from unittest.mock import patch


SCRIPT_DIR = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import evaluate_blind_v2 as evaluator  # noqa: E402


def test_retrieval_uses_production_contract_and_content_field() -> None:
    item = {
        "chunk_id": "chunk-1",
        "document_name": "source.md",
        "chunk_index": 3,
        "content_with_weight": "grounded evidence",
        "score": 0.9,
        "retrieval_routes": ["cloud"],
    }
    with patch.object(
        evaluator,
        "retrieve_from_knowledge_base",
        return_value=[item],
    ) as retrieve:
        result = asyncio.run(
            evaluator._retrieve_evidence("semiconductor_process", "question")
        )

    retrieve.assert_called_once_with(
        kb_name="semiconductor_process",
        question="question",
        top_k=5,
        min_score=0.0,
    )
    assert result["ok"] is True
    assert "grounded evidence" in result["evidence"]
    assert result["items"][0]["document_name"] == "source.md"


def test_cross_domain_retrieval_queries_all_knowledge_bases() -> None:
    with patch.object(
        evaluator,
        "retrieve_from_knowledge_base",
        return_value=[],
    ) as retrieve:
        result = asyncio.run(evaluator._retrieve_evidence("all", "question"))

    assert retrieve.call_count == len(evaluator.ALL_KNOWLEDGE_BASES)
    assert result["target_knowledge_bases"] == list(evaluator.ALL_KNOWLEDGE_BASES)


def test_retrieval_failure_is_structured_not_prompt_evidence() -> None:
    with patch.object(
        evaluator,
        "retrieve_from_knowledge_base",
        side_effect=RuntimeError("milvus unavailable"),
    ):
        result = asyncio.run(
            evaluator._retrieve_evidence("semiconductor_process", "question")
        )

    assert result["ok"] is False
    assert result["evidence"] == ""
    assert result["items"] == []
    assert "milvus unavailable" in result["error"]


def test_source_retrieval_metrics_support_compound_public_sources() -> None:
    question = {
        "source_document": "nist-chips-1000.md 和 riscv-privileged-20260120.md"
    }
    items = [
        {"document_name": "unrelated.md"},
        {"document_name": "riscv-privileged-20260120.md"},
    ]

    metrics = evaluator._source_retrieval_metrics(question, items)

    assert metrics["expected_documents"] == [
        "nist-chips-1000.md",
        "riscv-privileged-20260120.md",
    ]
    assert metrics["matched_documents"] == ["riscv-privileged-20260120.md"]
    assert metrics["hit"] is True
    assert metrics["first_hit_rank"] == 2


def test_source_retrieval_metrics_excludes_no_evidence_cases() -> None:
    metrics = evaluator._source_retrieval_metrics(
        {"source_document": "无"},
        [{"document_name": "irrelevant.md"}],
    )

    assert metrics["expected_documents"] == []
    assert metrics["hit"] is None
