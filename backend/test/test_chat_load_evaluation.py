"""Deterministic aggregation tests for the concurrent chat load tool."""

from pathlib import Path
import sys
import unittest


APP_DIR = Path(__file__).resolve().parents[1] / "app"
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

from scripts.load_test_chat import percentile, summarize_load  # noqa: E402


class ChatLoadEvaluationTests(unittest.TestCase):
    def test_nearest_rank_percentiles_cover_small_samples(self):
        values = [1.0, 2.0, 3.0, 10.0]
        self.assertEqual(percentile(values, 0.50), 2.0)
        self.assertEqual(percentile(values, 0.95), 10.0)
        self.assertEqual(percentile(values, 0.99), 10.0)

    def test_summary_separates_availability_latency_and_quality(self):
        results = [
            {"latency_seconds": 2.0, "errors": [], "quality_passed": True},
            {"latency_seconds": 4.0, "errors": [], "quality_passed": False},
            {
                "latency_seconds": 8.0,
                "errors": [{"type": "TimeoutError"}],
                "quality_passed": False,
            },
        ]
        summary = summarize_load(
            results,
            wall_seconds=10.0,
            max_p95_seconds=7.0,
            max_error_rate=0.20,
            min_quality_pass_rate=0.50,
        )
        self.assertEqual(summary["p95_latency_seconds"], 8.0)
        self.assertEqual(summary["error_rate"], 0.3333)
        self.assertEqual(summary["quality_pass_rate"], 0.3333)
        self.assertFalse(summary["thresholds"]["p95_latency"])
        self.assertFalse(summary["thresholds"]["error_rate"])
        self.assertFalse(summary["thresholds"]["quality_pass_rate"])
        self.assertFalse(summary["passed"])


if __name__ == "__main__":
    unittest.main()
