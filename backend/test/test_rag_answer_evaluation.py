from pathlib import Path
import sys
import unittest
from unittest.mock import patch

APP_DIR = Path(__file__).resolve().parents[1] / "app"
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

from scripts.evaluate_rag_answers import (  # noqa: E402
    evaluate_case,
    evaluate_term_group_citation_support,
)


BASE_CASE = {
    "id": "answer-eval-001",
    "domain": "design",
    "category": "qa",
    "question": "什么是 PPA？",
    "knowledge_base": "芯片设计与 EDA/IP",
    "required_term_groups": [["性能"], ["功耗"], ["面积"]],
    "expected_retrieval": True,
    "must_cite": True,
}


class RagAnswerEvaluationTests(unittest.TestCase):
    @patch("scripts.evaluate_rag_answers.call_chat_api")
    def test_quality_and_latency_are_reported_separately(self, mock_call):
        mock_call.return_value = (
            "PPA 包括性能、功耗和面积。[[1]]",
            [{"document_name": "design-guide.pdf", "content": "性能、功耗和面积"}],
            {"mode": "local"},
            [],
            21.0,
        )

        result = evaluate_case("http://example.test", BASE_CASE, "local", 30.0, 20.0)

        self.assertTrue(result["quality_passed"])
        self.assertFalse(result["latency_ok"])
        self.assertFalse(result["passed"])

    @patch("scripts.evaluate_rag_answers.call_chat_api")
    def test_quality_failure_does_not_hide_sla_success(self, mock_call):
        mock_call.return_value = (
            "PPA 包括性能和功耗。[[1]]",
            [{"document_name": "design-guide.pdf", "content": "性能、功耗和面积"}],
            {"mode": "local"},
            [],
            2.0,
        )

        result = evaluate_case("http://example.test", BASE_CASE, "local", 30.0, 20.0)

        self.assertFalse(result["quality_passed"])
        self.assertTrue(result["latency_ok"])
        self.assertFalse(result["passed"])

    def test_citation_number_alone_does_not_prove_claim_support(self):
        support = evaluate_term_group_citation_support(
            BASE_CASE,
            "PPA 包括性能、功耗和面积。[[1]]",
            [{"document_name": "unrelated.pdf", "content": "这里只讨论封装热管理。"}],
        )
        self.assertEqual(support["citation_completeness"], 1.0)
        self.assertEqual(support["citation_support_coverage"], 0.0)

    def test_each_required_group_can_be_traced_to_its_cited_chunk(self):
        support = evaluate_term_group_citation_support(
            BASE_CASE,
            "PPA 中性能和功耗需要权衡。[[1]]\n面积由第二条证据支持。[[2]]",
            [
                {"content": "性能与功耗是 PPA 核心指标。"},
                {"content": "面积反映物理实现成本。"},
            ],
        )
        self.assertEqual(support["citation_support_coverage"], 1.0)

    @patch("scripts.evaluate_rag_answers.call_chat_api")
    def test_api_exception_becomes_auditable_case_failure(self, mock_call):
        mock_call.side_effect = TimeoutError("model timeout")
        result = evaluate_case("http://example.test", BASE_CASE, "local", 1.0, 20.0)
        self.assertFalse(result["quality_passed"])
        self.assertEqual(result["errors"][0]["type"], "TimeoutError")
        self.assertIn("model timeout", result["errors"][0]["message"])
