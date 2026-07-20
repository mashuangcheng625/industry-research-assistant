"""Production-path context-budget tests for auxiliary LLM calls."""

import asyncio
import os
from types import SimpleNamespace
from unittest.mock import Mock, patch

from service.chat_service import ChatService
from service.memory_service import MemoryService
from service.text2sql_service import Text2SQLService


def _completion(content: str) -> SimpleNamespace:
    return SimpleNamespace(choices=[SimpleNamespace(
        message=SimpleNamespace(content=content),
    )])


def _client(content: str) -> tuple[SimpleNamespace, Mock]:
    create = Mock(return_value=_completion(content))
    return SimpleNamespace(chat=SimpleNamespace(
        completions=SimpleNamespace(create=create),
    )), create


def test_memory_summary_caps_provider_output() -> None:
    service = MemoryService.__new__(MemoryService)
    service.model = "test-model"
    service.client, create = _client(
        '{"summary":"摘要","key_insights":[],"user_preferences":{},"topics":[]}'
    )
    messages = [SimpleNamespace(role="user", content="讨论先进封装技术路线。")]

    with patch.dict(os.environ, {
        "CONTEXT_BUDGET_TOTAL_TOKENS": "1024",
        "MEMORY_MAX_OUTPUT_TOKENS": "900",
        "MEMORY_MIN_OUTPUT_TOKENS": "64",
    }, clear=False):
        result = service.summarize_conversation(messages)

    assert result["summary"] == "摘要"
    assert 64 <= create.call_args.kwargs["max_tokens"] < 900


def test_memory_summary_skips_provider_when_budget_is_exhausted() -> None:
    service = MemoryService.__new__(MemoryService)
    service.model = "test-model"
    service.client, create = _client("{}")
    messages = [SimpleNamespace(role="user", content="超长对话" * 10_000)]

    with patch.dict(os.environ, {
        "CONTEXT_BUDGET_TOTAL_TOKENS": "1024",
        "MEMORY_MIN_OUTPUT_TOKENS": "256",
    }, clear=False):
        result = service.summarize_conversation(messages)

    create.assert_not_called()
    assert result["summary"] == "对话包含 1 条消息"


def _text2sql_service() -> Text2SQLService:
    service = Text2SQLService(
        llm_api_key="test-key",
        llm_base_url="https://example.test/v1",
    )
    return service


def test_text2sql_caps_provider_output() -> None:
    service = _text2sql_service()
    service.client, create = _client(
        '{"sql":"SELECT * FROM company_data LIMIT 10",'
        '"explanation":"查询企业", "expected_columns":[], '
        '"visualization_hint":"table", "confidence":0.9}'
    )

    with patch.dict(os.environ, {
        "CONTEXT_BUDGET_TOTAL_TOKENS": "4096",
        "TEXT2SQL_MAX_OUTPUT_TOKENS": "3500",
        "TEXT2SQL_MIN_OUTPUT_TOKENS": "128",
    }, clear=False):
        result = asyncio.run(service.generate_sql("查询企业列表"))

    assert result["sql"].startswith("SELECT")
    assert 128 <= create.call_args.kwargs["max_tokens"] < 3500


def test_text2sql_returns_deterministic_error_before_provider_call() -> None:
    service = _text2sql_service()
    service.client, create = _client("{}")

    with patch.dict(os.environ, {
        "CONTEXT_BUDGET_TOTAL_TOKENS": "1024",
        "TEXT2SQL_MIN_OUTPUT_TOKENS": "256",
    }, clear=False):
        result = asyncio.run(service.generate_sql("超长问题" * 10_000))

    create.assert_not_called()
    assert result["sql"] == ""
    assert "上下文预算" in result["explanation"]
    assert result["context_budget"]["remaining"] < 256


def test_semantic_judge_fails_closed_before_provider_call() -> None:
    validation = {
        "status": "grounded",
        "accepted_claims": [{
            "text": "先进封装使用 TSV。",
            "citation_ids": [1],
            "verified_evidence_quotes": [],
        }],
        "rejected_claims": [],
        "accepted_claim_count": 1,
        "rejected_claim_count": 0,
    }
    references = [{"content": "证据" * 10_000}]
    endpoint = SimpleNamespace(
        api_key="test-key",
        base_url="https://example.test/v1",
        model="judge-model",
        public_info=lambda: {"model": "judge-model", "mode": "cloud"},
    )
    provider = Mock()
    service = ChatService(SimpleNamespace(), SimpleNamespace())

    with patch.dict(os.environ, {
        "CONTEXT_BUDGET_TOTAL_TOKENS": "1024",
        "RAG_ENTAILMENT_MAX_EVIDENCE_CHARS": "100000",
        "RAG_ENTAILMENT_MIN_OUTPUT_TOKENS": "256",
    }, clear=False), patch(
        "service.chat_service.resolve_llm_endpoint", return_value=endpoint,
    ), patch("service.chat_service.OpenAI", provider):
        result = service._verify_semantic_entailment(
            validation,
            references,
            "cloud",
        )

    provider.assert_not_called()
    assert result["status"] == "insufficient"
    assert result["semantic_entailment_verification"] == "llm_judge_failed_closed"
    assert result["semantic_verifier"]["context_budget"]["remaining"] < 256
