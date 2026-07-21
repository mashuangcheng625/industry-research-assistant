"""Runtime configuration and deployment probe tests."""
import os
import json
import tempfile
import warnings
from pathlib import Path
from unittest.mock import patch

import pytest
from pymilvus import connections

from core.health import (
    _openai_compatible_embedding,
    _openai_compatible_model,
    check_readiness,
    readiness_checks,
)
from core.runtime_config import cors_origins, env_bool
from service.milvus_service import MilvusService


def test_cors_defaults_are_explicit_local_origins():
    with patch.dict(os.environ, {}, clear=True):
        assert cors_origins() == ["http://localhost:5173", "http://127.0.0.1:5173"]


def test_runtime_boolean_parsing():
    with patch.dict(os.environ, {"FEATURE": "off"}, clear=True):
        assert env_bool("FEATURE", True) is False
        assert env_bool("MISSING", True) is True


def test_readiness_reports_success_without_exposing_details():
    result = check_readiness({"dependency": lambda: None})
    assert result["status"] == "ready"
    assert result["checks"]["dependency"]["status"] == "ok"


def test_readiness_reports_exception_type_only():
    def fail() -> None:
        raise RuntimeError("secret connection string")

    result = check_readiness({"dependency": fail})
    assert result["status"] == "not_ready"
    assert result["checks"]["dependency"]["error_type"] == "RuntimeError"
    assert "secret connection string" not in str(result)


def test_model_readiness_is_opt_in_and_checks_both_models():
    with patch.dict(os.environ, {}, clear=True):
        assert set(readiness_checks()) == {"postgres", "redis", "milvus"}
    with patch.dict(os.environ, {"READINESS_CHECK_MODELS": "true"}, clear=True):
        assert set(readiness_checks()) == {
            "postgres",
            "redis",
            "milvus",
            "generation_model",
            "embedding_model",
        }
    with patch.dict(os.environ, {"READINESS_CHECK_TASK_WORKER": "true"}, clear=True):
        assert set(readiness_checks()) == {"postgres", "redis", "milvus", "task_worker"}
    with patch.dict(
        os.environ,
        {"READINESS_CHECK_OUTBOX_DISPATCHER": "true"},
        clear=True,
    ):
        assert set(readiness_checks()) == {
            "postgres",
            "redis",
            "milvus",
            "outbox_dispatcher",
        }


def test_openai_compatible_model_readiness_requires_configured_model():
    response = patch("core.health.urlopen")
    with response as mocked_urlopen:
        context = mocked_urlopen.return_value.__enter__.return_value
        context.read.return_value = json.dumps(
            {"data": [{"id": "industry-qwen3:4b"}, {"id": "bge-m3:latest"}]}
        ).encode()
        _openai_compatible_model(
            "http://model.test/v1", "industry-qwen3:4b", "test-key"
        )
        _openai_compatible_model("http://model.test/v1", "bge-m3", "test-key")
        with pytest.raises(LookupError):
            _openai_compatible_model("http://model.test/v1", "missing", "test-key")

        context.read.return_value = json.dumps(
            {"data": [{"embedding": [0.25, 0.75]}]}
        ).encode()
        _openai_compatible_embedding(
            "http://model.test/v1", "text-embedding-v4", "test-key", 1024
        )

        request = mocked_urlopen.call_args.args[0]
        assert request.full_url == "http://model.test/v1/embeddings"
        assert request.method == "POST"
        assert json.loads(request.data)["dimensions"] == 1024

        context.read.return_value = json.dumps({"data": []}).encode()
        with pytest.raises(ValueError):
            _openai_compatible_embedding(
                "http://model.test/v1", "text-embedding-v4", "test-key", 1024
            )


@pytest.mark.integration
def test_milvus_lite_insert_and_search_integration():
    previous_tempdir = tempfile.tempdir
    tempfile.tempdir = "/tmp"
    try:
        with tempfile.TemporaryDirectory(dir="/tmp") as temp_dir, patch.dict(
            os.environ,
            {"MILVUS_URI": str(Path(temp_dir) / "integration.db")},
            clear=False,
        ), warnings.catch_warnings():
            warnings.simplefilter("ignore")
            service = MilvusService()
            collection_name = "integration_vectors"
            unit = [1.0] + [0.0] * 1023
            orthogonal = [0.0, 1.0] + [0.0] * 1022
            inserted = service.insert_documents(collection_name, [
                {
                    "id": "evidence-a",
                    "doc_id": "doc-a",
                    "kb_id": "kb-a",
                    "filename": "a.md",
                    "content": "traceable evidence",
                    "chunk_index": 0,
                    "vector": unit,
                },
                {
                    "id": "evidence-b",
                    "doc_id": "doc-b",
                    "kb_id": "kb-a",
                    "filename": "b.md",
                    "content": "other evidence",
                    "chunk_index": 0,
                    "vector": orthogonal,
                },
            ])
            results = service.search(collection_name, unit, top_k=1)
            assert inserted == 2
            assert results[0]["id"] == "evidence-a"
            assert results[0]["content"] == "traceable evidence"
            service.delete_collection(collection_name)
            connections.disconnect("default")
    finally:
        tempfile.tempdir = previous_tempdir
