"""Prometheus lifecycle metrics for research runs."""

import asyncio
from pathlib import Path
import sys
import unittest

from prometheus_client import REGISTRY, generate_latest


APP_DIR = Path(__file__).resolve().parents[1] / "app"
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

from core.metrics import safe_phase, safe_reason  # noqa: E402
from service.deep_research_v2.service import DeepResearchV2Service  # noqa: E402


def metric_value(name: str, labels: dict[str, str] | None = None) -> float:
    return float(REGISTRY.get_sample_value(name, labels or {}) or 0.0)


class ResearchObservabilityTests(unittest.TestCase):
    def make_service(self, events):
        class FakeGraph:
            async def run(self, *_args, **_kwargs):
                for event in events:
                    yield event

        service = DeepResearchV2Service.__new__(DeepResearchV2Service)
        service.graph = FakeGraph()
        service.model = "fake-model"
        return service

    def test_approved_run_records_terminal_and_phase_metrics(self):
        service = self.make_service([
            {"type": "phase", "phase": "planning"},
            {
                "type": "research_complete",
                "completion_reason": "review_passed",
            },
        ])
        labels = {"resume": "false", "outcome": "approved"}
        before = metric_value("industry_research_runs_total", labels)
        phase_before = metric_value(
            "industry_research_phase_duration_seconds_count",
            {"phase": "planning", "outcome": "approved"},
        )

        async def collect():
            return [item async for item in service.research(
                "question",
                session_id="metrics-approved",
                search_web=False,
                search_local=True,
            )]

        events = asyncio.run(collect())
        self.assertTrue(events[-1].endswith("[DONE]\n\n"))
        self.assertEqual(
            metric_value("industry_research_runs_total", labels) - before,
            1.0,
        )
        self.assertEqual(
            metric_value(
                "industry_research_phase_duration_seconds_count",
                {"phase": "planning", "outcome": "approved"},
            ) - phase_before,
            1.0,
        )
        self.assertEqual(metric_value("industry_research_active_runs"), 0.0)

    def test_closing_stream_records_client_disconnect(self):
        service = self.make_service([
            {"type": "phase", "phase": "planning"},
            {"type": "thought", "content": "still running"},
        ])
        labels = {"resume": "false", "outcome": "client_disconnected"}
        before = metric_value("industry_research_runs_total", labels)

        async def open_then_close():
            stream = service.research(
                "question",
                session_id="metrics-disconnect",
                search_web=False,
                search_local=True,
            )
            await anext(stream)
            await stream.aclose()

        asyncio.run(open_then_close())
        self.assertEqual(
            metric_value("industry_research_runs_total", labels) - before,
            1.0,
        )
        self.assertEqual(metric_value("industry_research_active_runs"), 0.0)

    def test_metrics_exposition_and_label_bounding(self):
        exposition = generate_latest().decode("utf-8")
        self.assertIn("industry_research_runs_total", exposition)
        self.assertEqual(safe_phase("user-controlled-value"), "unknown")
        self.assertEqual(safe_reason("raw exception text"), "unknown")


if __name__ == "__main__":
    unittest.main()
