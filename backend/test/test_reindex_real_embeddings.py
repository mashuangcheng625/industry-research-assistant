"""Regression tests for the fail-closed real Embedding rebuild."""

from __future__ import annotations

from pathlib import Path
import sys
from unittest.mock import patch

import pytest


SCRIPT_DIR = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import reindex_real_embeddings as reindex  # noqa: E402


class _FakeCollection:
    def __init__(self, vectors: list[list[float]], num_entities: int | None = None):
        self._vectors = vectors
        self.num_entities = len(vectors) if num_entities is None else num_entities

    def query(self, **_: object) -> list[dict[str, list[float]]]:
        return [{"vector": vector} for vector in self._vectors]


def test_validate_vector_rejects_zero_vector() -> None:
    with pytest.raises(RuntimeError, match="zero vector"):
        reindex._validate_vector([0.0] * 4, dimensions=4, label="batch")


def test_validate_vector_rejects_dimension_mismatch() -> None:
    with pytest.raises(RuntimeError, match="expected 4 dimensions"):
        reindex._validate_vector([1.0, 0.0], dimensions=4, label="batch")


def test_collection_audit_fails_closed_on_zero_vector() -> None:
    audit = reindex._audit_collection_vectors(
        _FakeCollection([[1.0, 0.0], [0.0, 0.0]]),
        expected_dimensions=2,
    )

    assert audit["zero_vectors"] == 1
    assert audit["passed"] is False


def test_collection_audit_requires_all_entities_to_be_returned() -> None:
    audit = reindex._audit_collection_vectors(
        _FakeCollection([[1.0, 0.0]], num_entities=2),
        expected_dimensions=2,
    )

    assert audit["queried_vectors"] == 1
    assert audit["num_entities"] == 2
    assert audit["passed"] is False


def test_cloud_preflight_uses_configured_route_and_rejects_none() -> None:
    with patch.object(reindex, "generate_embedding", return_value=None):
        with pytest.raises(RuntimeError, match="invalid response shape"):
            reindex._cloud_embedding_preflight()
