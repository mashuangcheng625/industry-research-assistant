"""Context-budget coverage for the ReAct and DR-G compatibility paths."""

import asyncio
import json
import os
from types import SimpleNamespace
from unittest.mock import Mock, patch

from service.dr_g import ResearchService, qwen_llm
from service.react_controller import ReActContext, ReActController
from scripts.stress_context_budget import REQUEST_PATHS, build_request_wide_matrix


def _completion(content: str) -> SimpleNamespace:
    return SimpleNamespace(choices=[SimpleNamespace(
        message=SimpleNamespace(content=content),
    )])


def _react_controller(create: Mock) -> ReActController:
    controller = ReActController.__new__(ReActController)
    controller.tools = {}
    controller.model = "test-model"
    controller.client = SimpleNamespace(chat=SimpleNamespace(
        completions=SimpleNamespace(create=create),
    ))
    controller.context_budget_summaries = {}
    return controller


def test_react_plan_think_and_reflect_cap_provider_output() -> None:
    create = Mock(side_effect=[
        _completion(json.dumps({
            "understanding": "研究先进封装",
            "sub_queries": [],
            "strategy": "检索并核验",
            "expected_aspects": ["技术路线"],
        }, ensure_ascii=False)),
        _completion(json.dumps({
            "thought": "资料足够",
            "should_finish": True,
            "action": None,
            "confidence": 0.9,
        }, ensure_ascii=False)),
        _completion(json.dumps({
            "coverage_analysis": "覆盖充分",
            "missing_aspects": [],
            "is_sufficient": True,
            "additional_queries": [],
            "confidence": 0.9,
        }, ensure_ascii=False)),
    ])
    controller = _react_controller(create)
    context = ReActContext("分析先进封装技术路线")

    with patch.dict(os.environ, {
        "CONTEXT_BUDGET_TOTAL_TOKENS": "4096",
        "REACT_MAX_OUTPUT_TOKENS": "5000",
        "REACT_MIN_OUTPUT_TOKENS": "64",
    }, clear=False):
        plan = asyncio.run(controller._generate_plan(context))
        context.plan = plan
        thought = asyncio.run(controller._think(context))
        reflection = asyncio.run(controller._reflect(context))

    assert thought.should_finish is True
    assert reflection["is_sufficient"] is True
    assert set(controller.context_budget_summaries) == {"plan", "think", "reflect"}
    for call in create.call_args_list:
        assert 64 <= call.kwargs["max_tokens"] < 5000


def test_react_budget_exhaustion_uses_existing_safe_fallbacks() -> None:
    create = Mock()
    controller = _react_controller(create)
    context = ReActContext("超长研究问题" * 10_000)

    with patch.dict(os.environ, {
        "CONTEXT_BUDGET_TOTAL_TOKENS": "1024",
        "REACT_MIN_OUTPUT_TOKENS": "256",
    }, clear=False):
        plan = asyncio.run(controller._generate_plan(context))
        thought = asyncio.run(controller._think(context))
        context.plan = plan
        reflection = asyncio.run(controller._reflect(context))

    create.assert_not_called()
    assert plan.strategy == "直接搜索"
    assert thought.should_finish is True
    assert reflection["is_sufficient"] is True
    assert set(controller.context_budget_summaries) == {"plan", "think", "reflect"}
    assert all(
        summary["remaining"] < 256
        for summary in controller.context_budget_summaries.values()
    )


def test_drg_qwen_helper_caps_output_before_call() -> None:
    create = Mock(return_value=_completion("ok"))
    client = SimpleNamespace(chat=SimpleNamespace(
        completions=SimpleNamespace(create=create),
    ))
    with patch.dict(os.environ, {
        "CONTEXT_BUDGET_TOTAL_TOKENS": "1024",
        "DRG_QWEN_MAX_OUTPUT_TOKENS": "2000",
        "DRG_QWEN_MIN_OUTPUT_TOKENS": "64",
    }, clear=False), patch("service.dr_g.OpenAI", return_value=client):
        result = qwen_llm("规划先进封装研究子问题")

    assert result == "ok"
    assert 64 <= create.call_args.kwargs["max_tokens"] < 2000


def test_drg_qwen_helper_skips_provider_when_budget_is_exhausted() -> None:
    provider = Mock()
    with patch.dict(os.environ, {
        "CONTEXT_BUDGET_TOTAL_TOKENS": "1024",
        "DRG_QWEN_MIN_OUTPUT_TOKENS": "256",
    }, clear=False), patch("service.dr_g.OpenAI", provider):
        result = qwen_llm("超长研究资料" * 10_000)

    assert result is None
    provider.assert_not_called()


async def _collect_report(service: ResearchService, memory: list[dict]) -> list[dict]:
    events = []
    async for event in service._generate_final_report("先进封装", memory, [], []):
        events.append(json.loads(event))
    return events


def test_drg_report_caps_streaming_provider_output() -> None:
    create = Mock(return_value=[])
    client = SimpleNamespace(chat=SimpleNamespace(
        completions=SimpleNamespace(create=create),
    ))
    service = ResearchService(
        llm_api_key="test-key",
        llm_base_url="https://example.test/v1",
        use_react=False,
    )
    memory = [{"url": "https://example.test/1", "name": "资料", "summary": "TSV 互连证据"}]

    with patch.dict(os.environ, {
        "CONTEXT_BUDGET_TOTAL_TOKENS": "2048",
        "DRG_REPORT_MAX_OUTPUT_TOKENS": "3000",
        "DRG_REPORT_MIN_OUTPUT_TOKENS": "128",
    }, clear=False), patch("service.dr_g.OpenAI", return_value=client):
        events = asyncio.run(_collect_report(service, memory))

    assert 128 <= create.call_args.kwargs["max_tokens"] < 3000
    assert events[-1]["type"] == "complete"


def test_drg_report_budget_exhaustion_emits_error_without_provider() -> None:
    provider = Mock()
    service = ResearchService(
        llm_api_key="test-key",
        llm_base_url="https://example.test/v1",
        use_react=False,
    )
    memory = [{
        "url": "https://example.test/1",
        "name": "超长资料",
        "summary": "先进封装证据" * 10_000,
    }]

    with patch.dict(os.environ, {
        "CONTEXT_BUDGET_TOTAL_TOKENS": "1024",
        "DRG_REPORT_MIN_OUTPUT_TOKENS": "256",
    }, clear=False), patch("service.dr_g.OpenAI", provider):
        events = asyncio.run(_collect_report(service, memory))

    provider.assert_not_called()
    assert events[-1]["type"] == "error"
    assert events[-1]["code"] == "context_budget_exceeded"
    assert events[-1]["context_budget"]["remaining"] < 256
    assert not any(event["type"] == "thinking_start" for event in events)


def test_request_wide_stress_matrix_covers_every_direct_call_path() -> None:
    report = build_request_wide_matrix(total_cap=32768)

    assert report["passed"] is True
    assert set(report["paths"]) == set(REQUEST_PATHS)
    assert len(report["cases"]) == len(REQUEST_PATHS) * 4
