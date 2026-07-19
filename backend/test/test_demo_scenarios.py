"""API-level smoke tests for the demo endpoints.

The demo endpoints serve pre-baked scenario JSONs and a preflight
check. These tests verify the HTTP contract without requiring any
internal services to be running (the scenarios are frozen fixtures).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client() -> TestClient:
    from app_main import app
    return TestClient(app)


# ---------------------------------------------------------------------------
# GET /demo/scenarios
# ---------------------------------------------------------------------------


def test_scenarios_returns_4_items(client: TestClient) -> None:
    resp = client.get("/demo/scenarios")
    assert resp.status_code == 200
    data = resp.json()
    assert data["count"] == 4
    ids = [s["id"] for s in data["scenarios"]]
    assert "ucie-hybrid-retrieval" in ids
    assert "nx999-refusal" in ids
    assert "agent-checkpoint" in ids
    assert "multi-source-joint" in ids


def test_scenarios_sorted_by_order(client: TestClient) -> None:
    resp = client.get("/demo/scenarios")
    orders = [s["order"] for s in resp.json()["scenarios"]]
    assert orders == sorted(orders)


def test_scenarios_each_has_required_keys(client: TestClient) -> None:
    required = {"id", "title", "category", "order", "question", "answer", "retrieval_trace", "meta"}
    for scenario in client.get("/demo/scenarios").json()["scenarios"]:
        missing = required - set(scenario)
        assert not missing, f"{scenario['id']} missing {missing}"


def test_scenario_traces_have_expected_shape(client: TestClient) -> None:
    for scenario in client.get("/demo/scenarios").json()["scenarios"]:
        for trace in scenario["retrieval_trace"]:
            assert "rank" in trace
            assert "source_kind" in trace
            assert "routing" in trace
            # score can be None (refusal scenario), rerank_score can be None
            assert isinstance(trace["score"], (int, float, type(None)))
            assert isinstance(trace["rerank_score"], (int, float, type(None)))


def test_refusal_scenario_has_empty_or_null_traces(client: TestClient) -> None:
    nx = next(
        (s for s in client.get("/demo/scenarios").json()["scenarios"] if s["id"] == "nx999-refusal"),
        None,
    )
    assert nx is not None
    assert len(nx["retrieval_trace"]) == 1
    assert nx["retrieval_trace"][0]["score"] is None
    assert nx["meta"]["refusal_reason"] == "missing_source"


# ---------------------------------------------------------------------------
# GET /demo/ready (contract shape only — real-service checks are manual)
# ---------------------------------------------------------------------------

# DB / Redis / Milvus may not be available in the test environment.
# The scenarios endpoint is fully covered above; the ready endpoint
# contract is exercised manually against a live deployment.



# ---------------------------------------------------------------------------
# Fixture file integrity (does not require HTTP)
# ---------------------------------------------------------------------------


FIXTURE_DIR = (
    Path(__file__).resolve().parents[1] / "sample-data" / "demo_scenarios"
).resolve()


def test_fixture_files_exist_on_disk() -> None:
    assert FIXTURE_DIR.is_dir(), f"Demo fixture dir missing: {FIXTURE_DIR}"
    jsons = sorted(FIXTURE_DIR.glob("*.json"))
    assert len(jsons) == 4, f"Expected 4 .json files, got {jsons}"
    for j in jsons:
        data = json.loads(j.read_text(encoding="utf-8"))
        assert "id" in data and "title" in data, f"{j.name}: missing id/title"
