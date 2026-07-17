"""Chat grounding and reranker identity-preservation tests."""
from pathlib import Path
import json
import os
import sys
import unittest
from types import SimpleNamespace
from unittest.mock import patch

APP_DIR = Path(__file__).resolve().parents[1] / "app"
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

from service.chat_service import ChatService, sanitize_citations  # noqa: E402


class ChatGroundingTests(unittest.TestCase):
    def make_service(self):
        return ChatService(SimpleNamespace(), SimpleNamespace(), SimpleNamespace())

    def test_reranker_scores_are_mapped_back_by_source_identity(self):
        reranked = [
            SimpleNamespace(
                score=0.91,
                node=SimpleNamespace(metadata={"source_index": 1}),
            ),
            SimpleNamespace(
                score=0.12,
                node=SimpleNamespace(metadata={"source_index": 0}),
            ),
        ]
        fake_reranker = SimpleNamespace(postprocess_nodes=lambda *args, **kwargs: reranked)
        documents = [
            {"content": "first", "weight": 0.5},
            {"content": "second", "weight": 0.4},
        ]
        with patch.dict(os.environ, {"EMBEDDING_BASE_URL": "https://example.test"}), patch(
            "service.chat_service.DashScopeRerank", return_value=fake_reranker,
        ):
            scores = self.make_service().rerank_similarity("query", documents)
        self.assertEqual(scores, [0.12, 0.91])

    def test_out_of_range_citations_are_removed(self):
        self.assertEqual(
            sanitize_citations("证据[[1]]，伪造[[3]]。", reference_count=2),
            "证据[[1]]，伪造。",
        )

    def test_structured_grounding_filters_claims_before_sse_delivery(self):
        raw_answer = """{
          "answer_status": "grounded",
          "claims": [
            {
              "text": "PLACE_DENSITY controls placement density",
              "citation_ids": [1],
              "evidence_quotes": [{
                "citation_id": 1,
                "quote": "PLACE_DENSITY sets the placement density target."
              }],
              "uncertainty": "certain"
            },
            {
              "text": "Fabricated thermal pressure requires 900 C",
              "citation_ids": [1],
              "evidence_quotes": [{
                "citation_id": 1,
                "quote": "fabricated quote"
              }],
              "uncertainty": "certain"
            }
          ],
          "limitations": []
        }"""
        completion = [SimpleNamespace(choices=[SimpleNamespace(
            delta=SimpleNamespace(content=raw_answer),
        )])]
        fake_client = SimpleNamespace(
            chat=SimpleNamespace(
                completions=SimpleNamespace(create=lambda **_kwargs: completion),
            ),
        )
        endpoint = SimpleNamespace(
            api_key="test-key",
            base_url="https://example.test/v1",
            model="test-model",
            mode="local",
            public_info=lambda: {"model": "test-model", "mode": "local"},
        )
        references = [{
            "source": "doc.md",
            "content": "PLACE_DENSITY sets the placement density target.",
            "content_with_weight": "PLACE_DENSITY sets the placement density target.",
            "weight": 0.9,
        }]

        with patch.dict(os.environ, {
            "LLM_MOCK_MODE": "false",
            "RAG_STRUCTURED_GROUNDING_ENABLED": "true",
        }), patch(
            "service.chat_service.resolve_llm_endpoint", return_value=endpoint,
        ), patch(
            "service.chat_service.OpenAI", return_value=fake_client,
        ):
            events = list(self.make_service().get_chat_completion(
                session_id=None,
                question="PLACE_DENSITY 是什么？",
                retrieved_content=references,
                model_mode="local",
            ))

        payloads = [
            json.loads(line.removeprefix("data: "))
            for event in events
            for line in event.splitlines()
            if line.startswith("data: {")
        ]
        answer = "".join(
            payload.get("content", "")
            for payload in payloads
            if payload.get("role") == "assistant"
        )
        envelope = next(payload for payload in payloads if "model_info" in payload)
        audit = envelope["model_info"]["grounding"]

        self.assertIn("PLACE_DENSITY", answer)
        self.assertIn("[[1]]", answer)
        self.assertNotIn("Fabricated thermal pressure", answer)
        self.assertEqual(audit["accepted_claim_count"], 1)
        self.assertEqual(audit["rejected_claim_count"], 1)
        self.assertEqual(audit["rejected_claims"][0]["reason"], "insufficient_lexical_support")

    def test_optional_semantic_judge_filters_lexically_similar_fabrication(self):
        raw_answer = """{
          "answer_status": "grounded",
          "claims": [
            {
              "text": "UCIe is a die-to-die interconnect standard",
              "citation_ids": [1],
              "evidence_quotes": [{
                "citation_id": 1,
                "quote": "UCIe is a die-to-die interconnect standard."
              }],
              "uncertainty": "certain"
            },
            {
              "text": "UCIe guarantees zero interconnect latency",
              "citation_ids": [1],
              "evidence_quotes": [{
                "citation_id": 1,
                "quote": "UCIe is a die-to-die interconnect standard."
              }],
              "uncertainty": "certain"
            }
          ],
          "limitations": []
        }"""
        generation_completion = [SimpleNamespace(choices=[SimpleNamespace(
            delta=SimpleNamespace(content=raw_answer),
        )])]
        judge_completion = SimpleNamespace(choices=[SimpleNamespace(
            message=SimpleNamespace(content=json.dumps({
                "judgments": [
                    {"claim_index": 0, "verdict": "entailed", "reason": "direct"},
                    {
                        "claim_index": 1,
                        "verdict": "not_entailed",
                        "reason": "zero latency is absent",
                    },
                ],
            })),
        )])
        generation_client = SimpleNamespace(chat=SimpleNamespace(
            completions=SimpleNamespace(create=lambda **_kwargs: generation_completion),
        ))
        judge_client = SimpleNamespace(chat=SimpleNamespace(
            completions=SimpleNamespace(create=lambda **_kwargs: judge_completion),
        ))
        endpoint = SimpleNamespace(
            api_key="test-key",
            base_url="https://example.test/v1",
            model="judge-model",
            mode="local",
            public_info=lambda: {
                "model": "judge-model",
                "mode": "local",
                "provider": "test",
            },
        )
        references = [{
            "source": "standard.md",
            "content": "UCIe is a die-to-die interconnect standard.",
            "content_with_weight": "UCIe is a die-to-die interconnect standard.",
            "weight": 0.9,
        }]

        with patch.dict(os.environ, {
            "LLM_MOCK_MODE": "false",
            "RAG_STRUCTURED_GROUNDING_ENABLED": "true",
            "RAG_SEMANTIC_ENTAILMENT_ENABLED": "true",
        }), patch(
            "service.chat_service.resolve_llm_endpoint", return_value=endpoint,
        ), patch(
            "service.chat_service.OpenAI",
            side_effect=[generation_client, judge_client],
        ):
            events = list(self.make_service().get_chat_completion(
                session_id=None,
                question="UCIe 是什么？",
                retrieved_content=references,
                model_mode="local",
            ))

        payloads = [
            json.loads(line.removeprefix("data: "))
            for event in events
            for line in event.splitlines()
            if line.startswith("data: {")
        ]
        answer = "".join(
            payload.get("content", "")
            for payload in payloads
            if payload.get("role") == "assistant"
        )
        audit = next(
            payload for payload in payloads if "model_info" in payload
        )["model_info"]["grounding"]

        self.assertIn("die-to-die interconnect standard", answer)
        self.assertNotIn("zero interconnect latency", answer)
        self.assertEqual(audit["accepted_claim_count"], 1)
        self.assertEqual(audit["semantic_entailment_rejected_count"], 1)
        self.assertEqual(audit["semantic_verifier"]["model"], "judge-model")
        self.assertEqual(
            audit["semantic_entailment_verification"],
            "llm_judge_performed",
        )

    def test_semantic_model_routing_error_fails_closed(self):
        validation = {
            "status": "grounded",
            "accepted_claims": [{
                "text": "UCIe is an interconnect standard",
                "citation_ids": [1],
                "verified_evidence_quotes": [],
            }],
            "rejected_claims": [],
            "accepted_claim_count": 1,
            "rejected_claim_count": 0,
        }
        references = [{"content": "UCIe is an interconnect standard."}]
        with patch.dict(os.environ, {"RAG_ENTAILMENT_MODEL_MODE": "cloud"}), patch(
            "service.chat_service.resolve_llm_endpoint",
            side_effect=ValueError("cloud endpoint is not configured"),
        ):
            result = self.make_service()._verify_semantic_entailment(
                validation,
                references,
                "local",
            )

        self.assertEqual(result["status"], "insufficient")
        self.assertEqual(result["accepted_claim_count"], 0)
        self.assertEqual(
            result["semantic_entailment_verification"],
            "llm_judge_failed_closed",
        )
        self.assertIn("not configured", result["semantic_verifier_error"])
        self.assertEqual(result["semantic_verifier"]["mode"], "cloud")


if __name__ == "__main__":
    unittest.main()
