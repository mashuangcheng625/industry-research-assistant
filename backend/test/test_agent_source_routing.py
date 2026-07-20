"""Deep Research V2 的模型和本地知识库路由测试。"""
from pathlib import Path
import asyncio
import os
import sys
import unittest
from unittest.mock import AsyncMock, patch

APP_DIR = Path(__file__).resolve().parents[1] / "app"
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

from config.llm_config import reload_config  # noqa: E402
from service.deep_research_v2.agents.architect import ChiefArchitect  # noqa: E402
from service.deep_research_v2.agents.critic import CriticMaster  # noqa: E402
from service.deep_research_v2.agents.scout import DeepScout  # noqa: E402
from service.deep_research_v2.agents.writer import LeadWriter  # noqa: E402
from service.deep_research_v2.graph import DeepResearchGraph, _build_ui_references  # noqa: E402
from service.deep_research_v2.state import ResearchPhase, create_initial_state  # noqa: E402
from service.llm_router import resolve_llm_endpoint  # noqa: E402


class AgentSourceRoutingTests(unittest.TestCase):
    def test_graph_uses_core_cancellation_control_without_router_cycle(self):
        import service.deep_research_v2.graph as graph_module

        self.assertEqual(
            graph_module.is_research_cancelled.__module__,
            "core.research_control",
        )

    def test_cancel_flag_is_cleared_before_start_event(self):
        graph = DeepResearchGraph.__new__(DeepResearchGraph)
        graph.max_iterations = 1
        graph.checkpoint_service = None

        async def first_event():
            stream = graph.run("研究问题", "clear-before-start")
            try:
                return await stream.__anext__()
            finally:
                await stream.aclose()

        with patch(
            "service.deep_research_v2.graph.clear_cancel_flag",
        ) as clear:
            event = asyncio.run(first_event())

        clear.assert_called_once_with("clear-before-start")
        self.assertEqual(event["type"], "research_start")

    def test_closing_stream_cancels_active_agent_task(self):
        cancelled = []

        class StreamingSlowAgent:
            name = "architect"

            async def process(self, state):
                await state["_message_queue"].put({"type": "agent_started"})
                try:
                    await asyncio.sleep(10)
                except asyncio.CancelledError:
                    cancelled.append(True)
                    raise

        graph = DeepResearchGraph.__new__(DeepResearchGraph)
        graph.max_iterations = 1
        graph.agent_timeout_seconds = 30
        graph.checkpoint_service = None
        graph.architect = StreamingSlowAgent()
        state = create_initial_state("研究问题", "disconnect-session")

        async def consume_then_close():
            stream = graph._run_simplified(state)
            phase = await stream.__anext__()
            started = await stream.__anext__()
            await stream.aclose()
            return phase, started

        with patch(
            "service.deep_research_v2.graph.is_research_cancelled",
            return_value=False,
        ):
            phase, started = asyncio.run(consume_then_close())

        self.assertEqual(phase["type"], "phase")
        self.assertEqual(started["type"], "agent_started")
        self.assertEqual(cancelled, [True])
        self.assertIsNone(state["_active_agent_task"])

    def test_cancellation_does_not_mark_partial_phase_completed(self):
        class SlowAgent:
            name = "architect"

            async def process(self, state):
                await state["_message_queue"].put({"type": "agent_started"})
                await asyncio.sleep(10)

        graph = DeepResearchGraph.__new__(DeepResearchGraph)
        graph.max_iterations = 1
        graph.agent_timeout_seconds = 30
        graph.checkpoint_service = None
        graph.architect = SlowAgent()
        state = create_initial_state("研究问题", "cancel-phase-session")
        checks = 0

        def cancellation_sequence(_session_id):
            nonlocal checks
            checks += 1
            # Phase 边界与 Agent 启动前均未取消；Agent 运行后触发取消。
            return checks >= 3

        async def collect_events():
            return [event async for event in graph._run_simplified(state)]

        with patch(
            "service.deep_research_v2.graph.is_research_cancelled",
            side_effect=cancellation_sequence,
        ):
            events = asyncio.run(collect_events())

        event_types = [event.get("type") for event in events]
        self.assertIn("research_cancelled", event_types)
        self.assertNotIn("checkpoint_saved", event_types)
        self.assertEqual(state["phase"], ResearchPhase.INIT.value)

    def test_state_keeps_selected_knowledge_base(self):
        state = create_initial_state(
            "Chiplet 接口标准",
            "test-session",
            search_web=False,
            search_local=True,
            kb_name="semiconductor_packaging_testing",
        )
        self.assertEqual(state["kb_name"], "semiconductor_packaging_testing")
        self.assertFalse(state["search_web"])
        self.assertTrue(state["search_local"])

    def test_agent_config_reuses_local_model_route(self):
        environment = {
            "MODEL_ROUTING_MODE": "local",
            "LOCAL_LLM_API_KEY": "ollama",
            "LOCAL_LLM_BASE_URL": "http://127.0.0.1:11434/v1",
            "LOCAL_LLM_MODEL": "industry-qwen3:4b",
        }
        with patch.dict(os.environ, environment, clear=True):
            config = reload_config()
        self.assertEqual(config.default_model, "industry-qwen3:4b")
        self.assertEqual(config.agents.scout.model, "industry-qwen3:4b")
        self.assertEqual(config.agents.writer.model, "industry-qwen3:4b")

    def test_agent_config_auto_uses_cloud_when_fully_configured(self):
        environment = {
            "MODEL_ROUTING_MODE": "auto",
            "LOCAL_LLM_MODEL": "industry-qwen3:4b",
            "DASHSCOPE_API_KEY": "test-bailian-key",
            "CLOUD_LLM_BASE_URL": "https://example.invalid/v1",
            "CLOUD_LLM_MODEL": "test-cloud-model",
            "CLOUD_AGENT_SCOUT_MODEL": "test-cloud-scout",
        }
        with patch.dict(os.environ, environment, clear=True):
            config = reload_config()
            endpoint = resolve_llm_endpoint()
        self.assertEqual(config.api_key, "test-bailian-key")
        self.assertEqual(endpoint.api_key, "test-bailian-key")
        self.assertEqual(endpoint.mode, "cloud")
        self.assertEqual(config.default_model, "test-cloud-model")
        self.assertEqual(config.agents.scout.model, "test-cloud-scout")
        self.assertEqual(config.agents.writer.model, "test-cloud-model")

    def test_agent_config_auto_falls_back_to_local_without_cloud_key(self):
        environment = {
            "MODEL_ROUTING_MODE": "auto",
            "LOCAL_LLM_MODEL": "industry-qwen3:4b",
            "CLOUD_LLM_BASE_URL": "https://example.invalid/v1",
            "CLOUD_LLM_MODEL": "test-cloud-model",
            "CLOUD_AGENT_SCOUT_MODEL": "test-cloud-scout",
        }
        with patch.dict(os.environ, environment, clear=True):
            config = reload_config()
        self.assertEqual(config.default_model, "industry-qwen3:4b")
        self.assertEqual(config.agents.scout.model, "industry-qwen3:4b")
        self.assertEqual(config.agents.writer.model, "industry-qwen3:4b")

    def test_local_agent_caps_requested_output_tokens(self):
        environment = {
            "MODEL_ROUTING_MODE": "local",
            "LOCAL_LLM_MAX_OUTPUT_TOKENS": "2048",
        }
        with patch.dict(os.environ, environment, clear=False):
            scout = DeepScout(
                "ollama",
                "http://127.0.0.1:11434/v1",
                "",
                "industry-qwen3:4b",
            )
            self.assertEqual(scout._effective_max_tokens(16000), 2048)
            self.assertEqual(scout._effective_max_tokens(512), 512)

    def test_scout_searches_exact_selected_collection(self):
        config = reload_config()
        scout = DeepScout(config.api_key, config.base_url, "", config.agents.scout.model)
        fake_result = [{
            "document_id": "doc-1",
            "document_name": "nist-chips-1400-2.md",
            "content_with_weight": "Chiplets Interfaces and technical standards priorities",
            "score": 0.88,
            "chunk_index": 4,
        }]
        with patch(
            "service.deep_research_v2.agents.scout.retrieve_from_knowledge_base",
            return_value=fake_result,
        ) as retrieve:
            rows = asyncio.run(scout._execute_local_search(
                "chiplet interface priorities",
                top_k=3,
                kb_name="semiconductor_packaging_testing",
            ))
        retrieve.assert_called_once_with(
            "semiconductor_packaging_testing",
            "chiplet interface priorities",
            3,
        )
        self.assertEqual(rows[0]["title"], "nist-chips-1400-2.md")
        self.assertEqual(rows[0]["kb_id"], "semiconductor_packaging_testing")
        self.assertTrue(rows[0]["url"].startswith("local://kb/semiconductor_packaging_testing/"))

    def test_scout_rejects_fabricated_source_url(self):
        config = reload_config()
        scout = DeepScout(config.api_key, config.base_url, "", config.agents.scout.model)
        local_result = {
            "url": "local://kb/semiconductor_packaging_testing/doc-1",
            "title": "nist-chips-1400-2.md",
            "site_name": "本地知识库/semiconductor_packaging_testing",
            "is_local": True,
            "kb_id": "semiconductor_packaging_testing",
            "doc_id": "doc-1",
            "chunk_index": 4,
            "score": 0.88,
        }
        grounded = scout._ground_fact_source({
            "content": "Chiplet 互连协议是标准化缺口之一。",
            "source_url": "https://fabricated.example/report",
            "source_name": "模型猜测来源",
            "credibility_score": 0.9,
        }, [local_result])
        self.assertEqual(grounded["source_url"], local_result["url"])
        self.assertEqual(
            grounded["_source_metadata"]["evidence_origin"],
            "local_knowledge_base",
        )
        self.assertEqual(grounded["citation_locator"]["anchor"], "chunk 4")
        self.assertEqual(grounded["citation_locator"]["source_kind"], "document")

    def test_scout_grounds_multiple_chunks_from_one_document(self):
        config = reload_config()
        scout = DeepScout(config.api_key, config.base_url, "", config.agents.scout.model)
        url = "local://kb/semiconductor_packaging_testing/doc-1"
        results = [
            {"url": url, "title": "NIST", "is_local": True, "kb_id": "kb", "chunk_index": 1},
            {"url": url, "title": "NIST", "is_local": True, "kb_id": "kb", "chunk_index": 2},
        ]
        grounded = scout._ground_fact_source({
            "content": "fact",
            "source_url": "https://fabricated.example",
            "credibility_score": 0.9,
        }, results)
        self.assertEqual(grounded["source_url"], url)
        self.assertEqual(grounded["_source_metadata"]["evidence_origin"], "local_knowledge_base")

    def test_writer_removes_unapproved_links_and_charts(self):
        config = reload_config()
        writer = LeadWriter(config.api_key, config.base_url, config.agents.writer.model)
        allowed = "local://kb/semiconductor_packaging_testing/doc-1"
        content = (
            f"[NIST]({allowed}) 提供证据；"
            "[伪来源](https://fabricated.example/report) 不应保留。\n"
            "![虚构图表](chart_001)"
        )
        sanitized = writer._sanitize_markdown_evidence(content, {allowed}, set())
        self.assertIn(f"[NIST]({allowed})", sanitized)
        self.assertNotIn("https://fabricated.example", sanitized)
        self.assertNotIn("!(chart_001)", sanitized)
        self.assertNotIn("![", sanitized)

    def test_writer_deduplicates_references_by_url(self):
        state = {"references": []}
        url = "local://kb/semiconductor_packaging_testing/doc-1"
        first_added = LeadWriter._append_reference_if_new(
            state,
            marker="[1]",
            source="NIST",
            url=url,
        )
        second_added = LeadWriter._append_reference_if_new(
            state,
            marker="证据来源",
            source="同一文档",
            url=url,
            citation_locator={
                "anchor": "chunk 4",
                "reference_url": url,
                "source_kind": "document",
            },
        )
        self.assertTrue(first_added)
        self.assertFalse(second_added)
        self.assertEqual(len(state["references"]), 1)
        self.assertEqual(state["references"][0]["citation_locator"]["anchor"], "chunk 4")

    def test_research_ui_reference_preserves_unified_locator(self):
        url = "local://kb/semiconductor_packaging_testing/doc-1"
        locator = {
            "anchor": "chunk 4",
            "reference_url": url,
            "source_kind": "document",
        }
        references = _build_ui_references(
            [{
                "source_url": url,
                "source_name": "先进封装手册",
                "content": "TSV 是关键互连结构。",
                "citation_locator": locator,
            }],
            [{
                "id": 1,
                "source": "先进封装手册",
                "url": url,
                "citation_locator": locator,
            }],
        )

        self.assertEqual(references[0]["link"], url)
        self.assertEqual(references[0]["citation_locator"], locator)

    def test_critic_cannot_pass_with_critical_issue(self):
        config = reload_config()
        critic = CriticMaster(config.api_key, config.base_url, config.agents.critic.model)
        normalized = critic._normalize_review_result({
            "overall_assessment": {"quality_score": 8, "verdict": "pass"},
            "issues": [{"severity": "critical", "description": "核心事实无证据"}],
        })
        assessment = normalized["overall_assessment"]
        self.assertEqual(assessment["verdict"], "major_issues")
        self.assertLessEqual(assessment["quality_score"], 4)

    def test_critic_rejects_unresolved_critical_issue_at_iteration_limit(self):
        config = reload_config()
        critic = CriticMaster(config.api_key, config.base_url, config.agents.critic.model)
        state = create_initial_state("研究问题", "review-session")
        state["phase"] = ResearchPhase.REVIEWING.value
        state["iteration"] = 1
        state["max_iterations"] = 2
        state["final_report"] = "未经充分证据支持的草稿"
        review = {
            "overall_assessment": {"quality_score": 8, "verdict": "pass"},
            "issues": [{
                "severity": "critical",
                "issue_type": "missing_source",
                "description": "核心事实无证据",
                "suggestion": "补充一手来源",
            }],
            "missing_aspects": [],
        }
        with patch.object(critic, "_review_content", AsyncMock(return_value=review)):
            result = asyncio.run(critic.process(state))

        self.assertEqual(result["iteration"], 2)
        self.assertEqual(result["phase"], ResearchPhase.REVIEW_FAILED.value)
        self.assertEqual(result["review_status"], "rejected")
        self.assertEqual(result["critical_issues"], 1)
        self.assertEqual(result["unresolved_issues"], 1)
        self.assertEqual(
            result["completion_reason"],
            "max_iterations_with_unresolved_issues",
        )

    def test_critic_approves_only_clean_review(self):
        config = reload_config()
        critic = CriticMaster(config.api_key, config.base_url, config.agents.critic.model)
        state = create_initial_state("研究问题", "review-session")
        state["phase"] = ResearchPhase.REVIEWING.value
        review = {
            "overall_assessment": {"quality_score": 8, "verdict": "pass"},
            "issues": [],
            "missing_aspects": [],
        }
        with patch.object(critic, "_review_content", AsyncMock(return_value=review)):
            result = asyncio.run(critic.process(state))

        self.assertEqual(result["phase"], ResearchPhase.COMPLETED.value)
        self.assertEqual(result["review_status"], "approved")
        self.assertEqual(result["completion_reason"], "review_passed")
        self.assertEqual(result["iteration"], 1)

    def test_simplified_graph_never_emits_complete_after_review_rejection(self):
        class FakeAgent:
            def __init__(self, name, process_fn=None):
                self.name = name
                self._process_fn = process_fn

            async def process(self, state):
                if self._process_fn:
                    self._process_fn(state)
                return state

        graph = DeepResearchGraph.__new__(DeepResearchGraph)
        graph.max_iterations = 1
        graph.checkpoint_service = None
        graph.architect = FakeAgent("architect")
        graph.scout = FakeAgent("scout")
        graph.data_analyst = FakeAgent("data_analyst")
        graph.wizard = FakeAgent("wizard")
        graph.writer = FakeAgent(
            "writer",
            lambda state: state.update(final_report="未批准草稿"),
        )

        def reject_review(state):
            state.update(
                iteration=1,
                phase=ResearchPhase.REVIEW_FAILED.value,
                review_status="rejected",
                completion_reason="max_iterations_with_unresolved_issues",
                critical_issues=1,
                major_issues=0,
                unresolved_issues=1,
            )

        graph.critic = FakeAgent("critic", reject_review)
        state = create_initial_state("研究问题", "graph-review-session")
        state["max_iterations"] = 1

        async def collect_events():
            return [event async for event in graph._run_simplified(state)]

        with patch(
            "service.deep_research_v2.graph.is_research_cancelled",
            return_value=False,
        ), patch("service.deep_research_v2.graph.clear_cancel_flag"):
            events = asyncio.run(collect_events())

        event_types = [event.get("type") for event in events]
        self.assertIn("research_review_failed", event_types)
        self.assertNotIn("research_complete", event_types)
        failed = next(event for event in events if event.get("type") == "research_review_failed")
        self.assertEqual(failed["review_status"], "rejected")
        self.assertEqual(failed["critical_issues"], 1)
        self.assertEqual(failed["final_report"], "未批准草稿")

    def test_resume_from_review_skips_completed_agents(self):
        calls = []

        class FakeAgent:
            def __init__(self, name, process_fn=None):
                self.name = name
                self._process_fn = process_fn

            async def process(self, state):
                calls.append(self.name)
                if self._process_fn:
                    self._process_fn(state)
                return state

        def approve_review(state):
            state.update(
                iteration=1,
                phase=ResearchPhase.COMPLETED.value,
                review_status="approved",
                completion_reason="review_passed",
                unresolved_issues=0,
                critical_issues=0,
                major_issues=0,
            )

        graph = DeepResearchGraph.__new__(DeepResearchGraph)
        graph.max_iterations = 2
        graph.checkpoint_service = None
        graph.architect = FakeAgent("architect")
        graph.scout = FakeAgent("scout")
        graph.data_analyst = FakeAgent("data_analyst")
        graph.wizard = FakeAgent("wizard")
        graph.writer = FakeAgent("writer")
        graph.critic = FakeAgent("critic", approve_review)

        state = create_initial_state("研究问题", "resume-review-session")
        state.update(
            phase=ResearchPhase.REVIEWING.value,
            last_completed_phase=ResearchPhase.WRITING.value,
            final_report="已保存草稿",
            max_iterations=2,
            _resume_from_phase=ResearchPhase.REVIEWING.value,
            _resume_after_phase=ResearchPhase.WRITING.value,
        )

        async def collect_events():
            return [event async for event in graph._run_simplified(state)]

        with patch(
            "service.deep_research_v2.graph.is_research_cancelled",
            return_value=False,
        ), patch("service.deep_research_v2.graph.clear_cancel_flag"):
            events = asyncio.run(collect_events())

        self.assertEqual(calls, ["critic"])
        skipped = {
            event.get("phase")
            for event in events
            if event.get("type") == "phase_skipped"
        }
        self.assertEqual(skipped, {"planning", "researching", "analyzing", "writing"})
        self.assertEqual(events[-1]["type"], "research_complete")

    def test_mid_research_checkpoint_resumes_research_not_analysis(self):
        calls = []

        class FakeAgent:
            def __init__(self, name, process_fn=None):
                self.name = name
                self._process_fn = process_fn

            async def process(self, state):
                calls.append(self.name)
                if self._process_fn:
                    self._process_fn(state)
                return state

        def approve(state):
            state.update(
                iteration=1,
                phase=ResearchPhase.COMPLETED.value,
                review_status="approved",
                completion_reason="review_passed",
            )

        graph = DeepResearchGraph.__new__(DeepResearchGraph)
        graph.max_iterations = 1
        graph.agent_timeout_seconds = 5
        graph.checkpoint_service = None
        graph.architect = FakeAgent("architect")
        graph.scout = FakeAgent("scout")
        graph.data_analyst = FakeAgent("data_analyst")
        graph.wizard = FakeAgent("wizard")
        graph.writer = FakeAgent(
            "writer",
            lambda state: state.update(
                final_report="恢复后的草稿",
                phase=ResearchPhase.REVIEWING.value,
            ),
        )
        graph.critic = FakeAgent("critic", approve)

        state = create_initial_state("研究问题", "mid-research-resume")
        state.update(
            phase=ResearchPhase.RESEARCHING.value,
            last_completed_phase=ResearchPhase.PLANNING.value,
            max_iterations=1,
            _resume_from_phase=ResearchPhase.RESEARCHING.value,
            _resume_after_phase=ResearchPhase.PLANNING.value,
        )

        async def collect_events():
            return [event async for event in graph._run_simplified(state)]

        with patch(
            "service.deep_research_v2.graph.is_research_cancelled",
            return_value=False,
        ):
            events = asyncio.run(collect_events())

        self.assertNotIn("architect", calls)
        self.assertEqual(calls[0], "scout")
        self.assertIn("writer", calls)
        self.assertEqual(calls[-1], "critic")
        self.assertEqual(events[-1]["type"], "research_complete")

    def test_agent_exception_terminates_workflow(self):
        class FailingAgent:
            name = "architect"

            async def process(self, _state):
                raise RuntimeError("synthetic agent failure")

        graph = DeepResearchGraph.__new__(DeepResearchGraph)
        graph.max_iterations = 1
        graph.agent_timeout_seconds = 1
        graph.checkpoint_service = None
        graph.architect = FailingAgent()
        state = create_initial_state("研究问题", "agent-failure-session")

        async def collect_events():
            return [event async for event in graph._run_simplified(state)]

        with patch(
            "service.deep_research_v2.graph.is_research_cancelled",
            return_value=False,
        ), patch("service.deep_research_v2.graph.clear_cancel_flag"):
            events = asyncio.run(collect_events())

        self.assertEqual(events[-1]["type"], "error")
        self.assertIn("synthetic agent failure", events[-1]["content"])
        self.assertFalse(any(event.get("type") == "research_complete" for event in events))
        self.assertTrue(any("synthetic agent failure" in error for error in state["errors"]))

    def test_agent_timeout_terminates_workflow(self):
        class SlowAgent:
            name = "architect"

            async def process(self, state):
                await asyncio.sleep(1)
                return state

        graph = DeepResearchGraph.__new__(DeepResearchGraph)
        graph.max_iterations = 1
        graph.agent_timeout_seconds = 0.02
        graph.checkpoint_service = None
        graph.architect = SlowAgent()
        state = create_initial_state("研究问题", "agent-timeout-session")

        async def collect_events():
            return [event async for event in graph._run_simplified(state)]

        with patch(
            "service.deep_research_v2.graph.is_research_cancelled",
            return_value=False,
        ), patch("service.deep_research_v2.graph.clear_cancel_flag"):
            events = asyncio.run(collect_events())

        self.assertEqual(events[-1]["type"], "error")
        self.assertIn("exceeded 0.02s timeout", events[-1]["content"])
        self.assertFalse(any(event.get("type") == "research_complete" for event in events))

    def test_recursive_search_inherits_local_only_mode(self):
        config = reload_config()
        scout = DeepScout(config.api_key, config.base_url, "", config.agents.scout.model)
        state = create_initial_state(
            "Chiplet 测试验证",
            "test-session",
            search_web=False,
            search_local=True,
            kb_name="semiconductor_packaging_testing",
        )
        local_rows = [{"url": "local://kb/test/doc", "title": "local evidence"}]
        with patch.object(scout, "_execute_search", return_value=[]) as web_search, patch.object(
            scout,
            "_execute_local_search",
            return_value=local_rows,
        ) as local_search:
            rows = asyncio.run(scout._execute_configured_search(state, "query", count=6))
        web_search.assert_not_called()
        local_search.assert_called_once_with(
            "query",
            top_k=6,
            kb_name="semiconductor_packaging_testing",
        )
        self.assertEqual(rows, local_rows)

    def test_architect_flat_plan_preserves_analysis_requirements(self):
        config = reload_config()
        architect = ChiefArchitect(config.api_key, config.base_url, config.agents.architect.model)
        result = architect._convert_flat_to_outline({
            "sec_1_title": "证据与现状",
            "sec_1_query": "chiplet evidence",
            "sec_1_requires_data": False,
            "sec_1_requires_chart": False,
            "sec_2_title": "关键缺口",
            "sec_2_query": "chiplet gaps",
            "sec_2_requires_data": True,
            "sec_2_requires_chart": False,
            "sec_3_title": "待验证项",
            "sec_3_query": "chiplet validation",
        })
        self.assertEqual(len(result["outline"]), 3)
        self.assertFalse(result["outline"][0]["requires_data"])
        self.assertTrue(result["outline"][1]["requires_data"])
        self.assertFalse(result["outline"][2]["requires_chart"])


if __name__ == "__main__":
    unittest.main()
