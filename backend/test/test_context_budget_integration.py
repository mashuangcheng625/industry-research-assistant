"""Production call-path tests for request-wide context budgeting."""

import asyncio
import json
import os
from types import SimpleNamespace
from unittest.mock import Mock, patch

import pytest

from core.context_budget import ContextBudgetExceeded
from service.chat_service import ChatService
from service.deep_research_v2.agents.base import BaseAgent


def _endpoint() -> SimpleNamespace:
    return SimpleNamespace(
        api_key="test-key",
        base_url="https://example.test/v1",
        model="test-model",
        mode="local",
        public_info=lambda: {"model": "test-model", "mode": "local"},
    )


def _chat_client(answer: str = "预算内回答") -> tuple[SimpleNamespace, Mock]:
    create = Mock(return_value=[SimpleNamespace(choices=[SimpleNamespace(
        delta=SimpleNamespace(content=answer),
    )])])
    client = SimpleNamespace(chat=SimpleNamespace(
        completions=SimpleNamespace(create=create),
    ))
    return client, create


def _event_payloads(events: list[str]) -> list[dict]:
    return [
        json.loads(line.removeprefix("data: "))
        for event in events
        for line in event.splitlines()
        if line.startswith("data: {")
    ]


def test_chat_caps_output_and_exposes_budget_summary() -> None:
    client, create = _chat_client()
    environment = {
        "LLM_MOCK_MODE": "false",
        "CONTEXT_BUDGET_TOTAL_TOKENS": "1024",
        "CONTEXT_BUDGET_MIN_OUTPUT_TOKENS": "64",
        "LOCAL_LLM_MAX_OUTPUT_TOKENS": "900",
    }
    with patch.dict(os.environ, environment, clear=False), patch(
        "service.chat_service.resolve_llm_endpoint", return_value=_endpoint(),
    ), patch("service.chat_service.OpenAI", return_value=client):
        service = ChatService(SimpleNamespace(), SimpleNamespace())
        events = list(service.get_chat_completion(
            session_id=None,
            question="请简要解释先进封装。",
            retrieved_content=[],
            model_mode="local",
        ))

    effective_output = create.call_args.kwargs["max_tokens"]
    assert 64 <= effective_output < 900

    model_info = next(
        payload["model_info"]
        for payload in _event_payloads(events)
        if "model_info" in payload
    )
    summary = model_info["context_budget"]
    assert summary["output"] == effective_output
    assert summary["total_with_output"] <= summary["total_cap"] == 1024
    assert summary["fits"] is True


def test_chat_rejects_oversized_prompt_before_provider_call() -> None:
    openai_factory = Mock()
    environment = {
        "LLM_MOCK_MODE": "false",
        "CONTEXT_BUDGET_TOTAL_TOKENS": "1024",
        "CONTEXT_BUDGET_MIN_OUTPUT_TOKENS": "256",
        "LOCAL_LLM_MAX_OUTPUT_TOKENS": "512",
    }
    with patch.dict(os.environ, environment, clear=False), patch(
        "service.chat_service.resolve_llm_endpoint", return_value=_endpoint(),
    ), patch("service.chat_service.OpenAI", openai_factory):
        service = ChatService(SimpleNamespace(), SimpleNamespace())
        events = list(service.get_chat_completion(
            session_id=None,
            question="超长附件上下文" * 2000,
            retrieved_content=[],
            model_mode="local",
        ))

    openai_factory.assert_not_called()
    payloads = _event_payloads(events)
    error = next(payload for payload in payloads if payload.get("role") == "error")
    assert error["code"] == "context_budget_exceeded"
    assert error["context_budget"]["remaining"] < 256
    assert events[-1] == "event: end\ndata: [DONE]\n\n"


def test_chat_does_not_duplicate_current_question_in_history() -> None:
    class SessionStore:
        def __init__(self):
            self.messages = [{"role": "assistant", "content": "上一轮回答"}]

        def add_message(self, _session_id: str, role: str, content: str) -> None:
            self.messages.append({"role": role, "content": content})

        def get_messages_for_prompt(self, _session_id: str) -> list[dict[str, str]]:
            return list(self.messages)

    client, create = _chat_client()
    question = "当前唯一问题"
    with patch.dict(os.environ, {"LLM_MOCK_MODE": "false"}, clear=False), patch(
        "service.chat_service.resolve_llm_endpoint", return_value=_endpoint(),
    ), patch("service.chat_service.OpenAI", return_value=client):
        service = ChatService(SimpleNamespace(), SessionStore())
        list(service.get_chat_completion(
            session_id="session-1",
            question=question,
            retrieved_content=[],
            model_mode="local",
        ))

    rendered_prompt = create.call_args.kwargs["messages"][0]["content"]
    assert rendered_prompt.count(question) == 1


def test_chat_response_exposes_citation_locator_without_removing_legacy_fields() -> None:
    reference = {
        "id": 1,
        "source": "knowledge",
        "title": "先进封装手册",
        "content": "TSV 是关键互连结构。",
        "content_with_weight": "TSV 是关键互连结构。",
        "link": "local://kb/packaging/doc-1",
        "page": 9,
    }
    with patch.dict(os.environ, {"LLM_MOCK_MODE": "true"}, clear=False):
        service = ChatService(SimpleNamespace(), SimpleNamespace())
        events = list(service.get_chat_completion(
            session_id=None,
            question="解释 TSV",
            retrieved_content=[reference],
        ))

    documents = next(
        payload["documents"]
        for payload in _event_payloads(events)
        if "documents" in payload
    )
    assert documents[0]["link"] == reference["link"]
    assert documents[0]["source"] == "knowledge"
    assert documents[0]["citation_locator"]["anchor"] == "p. 9"
    assert documents[0]["citation_locator"]["source_kind"] == "document"


class _BudgetAgent(BaseAgent):
    async def process(self, state):
        return state


def _agent() -> _BudgetAgent:
    return _BudgetAgent(
        name="BudgetAgent",
        role="test",
        llm_api_key="test-key",
        llm_base_url="https://example.test/v1",
        model="test-model",
    )


def test_agent_caps_output_before_provider_call() -> None:
    agent = _agent()
    create = Mock(return_value=SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content="ok"))],
        usage=None,
    ))
    agent.client = SimpleNamespace(chat=SimpleNamespace(
        completions=SimpleNamespace(create=create),
    ))
    environment = {
        "MODEL_ROUTING_MODE": "cloud",
        "CONTEXT_BUDGET_TOTAL_TOKENS": "1024",
        "CONTEXT_BUDGET_MIN_OUTPUT_TOKENS": "64",
        "AGENT_MAX_OUTPUT_TOKENS": "900",
    }

    with patch.dict(os.environ, environment, clear=False):
        result = asyncio.run(agent.call_llm(
            system_prompt="系统规则" * 60,
            user_prompt="研究资料" * 100,
            json_mode=False,
            max_tokens=900,
        ))

    assert result == "ok"
    assert 64 <= create.call_args.kwargs["max_tokens"] < 900


def test_agent_rejects_oversized_prompt_before_provider_call() -> None:
    agent = _agent()
    create = Mock()
    agent.client = SimpleNamespace(chat=SimpleNamespace(
        completions=SimpleNamespace(create=create),
    ))
    environment = {
        "MODEL_ROUTING_MODE": "cloud",
        "CONTEXT_BUDGET_TOTAL_TOKENS": "1024",
        "CONTEXT_BUDGET_MIN_OUTPUT_TOKENS": "256",
        "AGENT_MAX_OUTPUT_TOKENS": "512",
    }

    with patch.dict(os.environ, environment, clear=False), pytest.raises(ContextBudgetExceeded):
        asyncio.run(agent.call_llm(
            system_prompt="系统规则" * 1000,
            user_prompt="研究资料" * 1000,
            json_mode=False,
            max_tokens=512,
        ))

    create.assert_not_called()
