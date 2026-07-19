"""Contract tests for the opt-in P1-5 live model smoke harness."""

from pathlib import Path
import sys
from unittest.mock import patch


SCRIPT_DIR = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import p1_5_model_smoke as smoke  # noqa: E402


def test_hybrid_retrieval_uses_production_keyword_contract():
    result_item = {
        "document_id": "smoke-doc-001",
        "score": 0.91,
        "retrieval_routes": ["cloud", "local"],
        "degraded_route": None,
    }
    with patch(
        "service.retrieval_service.retrieve_from_knowledge_base",
        return_value=[result_item],
    ) as retrieve:
        result = smoke._hybrid_retrieval(
            knowledge_base="p1_5_smoke",
            query="question",
            top_k=5,
            expected_document_ids=["smoke-doc-001"],
        )

    retrieve.assert_called_once_with(
        kb_name="p1_5_smoke",
        question="question",
        top_k=5,
        min_score=0.0,
    )
    assert result["ok"] is True
    assert result["gold_hit"] is True
    assert result["dual_route_hit"] is True
    assert result["route_coverage"] == ["cloud", "local"]


def test_hybrid_retrieval_rejects_single_route_or_degraded_results():
    result_item = {
        "document_id": "smoke-doc-001",
        "score": 0.75,
        "retrieval_routes": ["cloud"],
        "degraded_route": ["local"],
    }
    with patch(
        "service.retrieval_service.retrieve_from_knowledge_base",
        return_value=[result_item],
    ):
        result = smoke._hybrid_retrieval(
            knowledge_base="p1_5_smoke",
            query="question",
            top_k=5,
            expected_document_ids=["smoke-doc-001"],
        )

    assert result["ok"] is False
    assert result["gold_hit"] is True
    assert result["dual_route_hit"] is False
    assert result["degraded_routes"] == ["local"]


def test_gates_fail_closed_when_hybrid_stage_does_not_pass():
    report = {
        "generation": {"records": [{"ok": True}]},
        "judge": {"records": [{"ok": True, "score": 5}]},
        "embedding": {"records": [{"ok": True, "vector_dim": 1024}]},
        "rerank": {"records": [{"ok": True, "ranking": [{"index": 0}]}]},
        "hybrid": {"records": [{"ok": False}]},
    }
    gates = smoke._build_gates(
        report,
        generation_expected=1,
        judge_expected=1,
        embedding_expected=1,
        rerank_expected=1,
        hybrid_expected=1,
        embedding_dimensions=1024,
    )

    assert gates["generation"]["pass"] is True
    assert gates["hybrid"] == {"pass": False, "ok": 0, "expected": 1}
    assert all(gate["pass"] for gate in gates.values()) is False
