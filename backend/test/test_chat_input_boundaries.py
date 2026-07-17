"""Deterministic request-size and retrieved-context boundary tests."""

from pathlib import Path
import sys
import unittest
from unittest.mock import Mock

from pydantic import ValidationError


APP_DIR = Path(__file__).resolve().parents[1] / "app"
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

from schemas.chat import (  # noqa: E402
    CHAT_QUESTION_MAX_CHARS,
    ChatRequest,
    ChatWithAttachmentsRequest,
)
from service.chat_service import ChatService  # noqa: E402


class ChatInputBoundaryTests(unittest.TestCase):
    def test_chat_requests_reject_empty_and_oversized_questions(self):
        for request_type in (ChatRequest, ChatWithAttachmentsRequest):
            with self.subTest(request_type=request_type.__name__, boundary="empty"):
                with self.assertRaises(ValidationError):
                    request_type(question="")
            with self.subTest(request_type=request_type.__name__, boundary="oversized"):
                with self.assertRaises(ValidationError):
                    request_type(question="芯" * (CHAT_QUESTION_MAX_CHARS + 1))

            accepted = request_type(question="芯" * CHAT_QUESTION_MAX_CHARS)
            self.assertEqual(len(accepted.question), CHAT_QUESTION_MAX_CHARS)

    def test_context_budget_skips_oversized_document_and_keeps_smaller_evidence(self):
        service = ChatService(Mock(), Mock(), Mock())
        oversized = "超长文档 " * 100
        small = "UCIe 提供芯粒间互连标准。"
        service.max_tokens = len(service.encoding.encode(small))
        service.rerank_similarity = Mock(return_value=[1.0, 0.9])
        documents = [
            {"id": 99, "content": oversized, "weight": 1.0, "title": "oversized"},
            {"id": 98, "content": small, "weight": 0.9, "title": "small"},
        ]

        filtered = service.rerank_documents("什么是 UCIe？", documents)

        self.assertEqual([doc["title"] for doc in filtered], ["small"])
        self.assertEqual(filtered[0]["id"], 1)
        self.assertLessEqual(
            sum(len(service.encoding.encode(doc["content"])) for doc in filtered),
            service.max_tokens,
        )

    def test_rerank_failure_still_enforces_context_budget(self):
        service = ChatService(Mock(), Mock(), Mock())
        service.max_tokens = 20
        service.rerank_similarity = Mock(side_effect=RuntimeError("reranker unavailable"))
        documents = [
            {
                "id": index,
                "content": f"文档 {index} " * 20,
                "weight": float(20 - index),
                "title": f"doc-{index}",
            }
            for index in range(12)
        ]

        filtered = service.rerank_documents("压测问题", documents)

        token_count = sum(
            len(service.encoding.encode(doc["content"])) for doc in filtered
        )
        self.assertLessEqual(token_count, service.max_tokens)
        self.assertLessEqual(len(filtered), 10)


if __name__ == "__main__":
    unittest.main()
