"""Structured claim grounding validation tests."""
from pathlib import Path
import sys
import unittest

APP_DIR = Path(__file__).resolve().parents[1] / "app"
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

from service.grounding_service import (  # noqa: E402
    GroundingValidationError,
    apply_semantic_entailment_judgments,
    build_semantic_entailment_cases,
    fail_closed_semantic_entailment,
    lexical_support_score,
    parse_structured_answer,
    parse_semantic_entailment_response,
    render_validated_answer,
    validate_structured_answer,
)


class GroundingServiceTests(unittest.TestCase):
    def test_fenced_json_is_parsed_but_invalid_status_is_rejected(self):
        payload = parse_structured_answer(
            '```json\n{"answer_status":"grounded","claims":[],"limitations":[]}\n```'
        )
        self.assertEqual(payload["answer_status"], "grounded")
        with self.assertRaises(GroundingValidationError):
            parse_structured_answer('{"answer_status":"maybe","claims":[]}')

    def test_only_in_range_supported_claims_are_retained(self):
        payload = {
            "answer_status": "grounded",
            "claims": [
                {
                    "text": "PLACE_DENSITY controls placement density",
                    "citation_ids": [1],
                    "evidence_quotes": [{
                        "citation_id": 1,
                        "quote": "PLACE_DENSITY sets the placement density target.",
                    }],
                    "uncertainty": "certain",
                },
                {
                    "text": "Unrelated thermal assertion",
                    "citation_ids": [1],
                    "evidence_quotes": [],
                    "uncertainty": "certain",
                },
                {
                    "text": "Out of range claim",
                    "citation_ids": [3],
                    "evidence_quotes": [],
                    "uncertainty": "limited",
                },
            ],
            "limitations": [],
        }
        validation = validate_structured_answer(
            payload,
            [{"content": "PLACE_DENSITY sets the placement density target."}],
            minimum_support_score=0.12,
        )
        self.assertEqual(validation["accepted_claim_count"], 1)
        self.assertEqual(validation["rejected_claim_count"], 2)
        self.assertIn("PLACE_DENSITY", render_validated_answer(validation))
        self.assertIn("[[1]]", render_validated_answer(validation))
        self.assertEqual(validation["verified_quote_count"], 1)

    def test_cross_language_claim_requires_a_verbatim_source_quote(self):
        references = [{
            "content": "Ukraine produced approximately half of the global neon supply in 2022."
        }]
        validation = validate_structured_answer({
            "answer_status": "grounded",
            "claims": [{
                "text": "2022 年乌克兰生产了全球约一半的氖气供应",
                "citation_ids": [1],
                "evidence_quotes": [{
                    "citation_id": 1,
                    "quote": "Ukraine produced approximately half of the global neon supply in 2022.",
                }],
                "uncertainty": "certain",
            }],
            "limitations": [],
        }, references)
        self.assertEqual(validation["accepted_claim_count"], 1)
        self.assertTrue(validation["accepted_claims"][0]["provenance_only"])
        self.assertEqual(validation["accepted_claims"][0]["uncertainty"], "limited")

        fabricated = validate_structured_answer({
            "answer_status": "grounded",
            "claims": [{
                "text": "2022 年乌克兰生产了全球约一半的氖气供应",
                "citation_ids": [1],
                "evidence_quotes": [{"citation_id": 1, "quote": "fabricated quote"}],
                "uncertainty": "limited",
            }],
            "limitations": [],
        }, references)
        self.assertEqual(fabricated["accepted_claim_count"], 0)

    def test_verbatim_quote_cannot_authorize_an_absent_identifier(self):
        validation = validate_structured_answer({
            "answer_status": "grounded",
            "claims": [{
                "text": "该工艺需要 900 C 的处理温度",
                "citation_ids": [1],
                "evidence_quotes": [{
                    "citation_id": 1,
                    "quote": "Ukraine produced approximately half of the global neon supply in 2022.",
                }],
                "uncertainty": "limited",
            }],
            "limitations": [],
        }, [{
            "content": "Ukraine produced approximately half of the global neon supply in 2022."
        }])
        self.assertEqual(validation["accepted_claim_count"], 0)
        self.assertEqual(
            validation["rejected_claims"][0]["reason"],
            "insufficient_lexical_support",
        )

    def test_all_rejected_claims_fail_closed(self):
        validation = validate_structured_answer(
            {
                "answer_status": "grounded",
                "claims": [{"text": "No citation", "citation_ids": []}],
                "limitations": [],
            },
            [{"content": "evidence"}],
        )
        self.assertEqual(validation["status"], "insufficient")
        self.assertIn("未通过逐论断证据校验", render_validated_answer(validation))

    def test_support_score_is_auditable_token_recall(self):
        self.assertGreater(
            lexical_support_score("在线计量支持过程控制", "在线计量可用于过程控制和反馈"),
            lexical_support_score("在线计量支持过程控制", "封装需要热管理"),
        )

    def test_semantic_judge_requires_exactly_one_verdict_per_claim(self):
        judgments = parse_semantic_entailment_response(
            '{"judgments":['
            '{"claim_index":0,"verdict":"entailed","reason":"direct"},'
            '{"claim_index":1,"verdict":"uncertain","reason":"scope missing"}'
            ']}',
            expected_claim_count=2,
        )
        self.assertEqual([item["claim_index"] for item in judgments], [0, 1])
        with self.assertRaises(GroundingValidationError):
            parse_semantic_entailment_response(
                '{"judgments":[{"claim_index":0,"verdict":"entailed"}]}',
                expected_claim_count=2,
            )
        with self.assertRaises(GroundingValidationError):
            parse_semantic_entailment_response(
                '{"judgments":['
                '{"claim_index":0,"verdict":"entailed"},'
                '{"claim_index":0,"verdict":"not_entailed"}'
                ']}',
                expected_claim_count=2,
            )

    def test_semantic_judge_filters_non_entailed_claims(self):
        references = [{"content": "UCIe is a die-to-die interconnect standard."}]
        lexical_validation = validate_structured_answer({
            "answer_status": "grounded",
            "claims": [
                {
                    "text": "UCIe is a die-to-die interconnect standard",
                    "citation_ids": [1],
                    "evidence_quotes": [{
                        "citation_id": 1,
                        "quote": "UCIe is a die-to-die interconnect standard.",
                    }],
                    "uncertainty": "certain",
                },
                {
                    "text": "UCIe guarantees zero interconnect latency",
                    "citation_ids": [1],
                    "evidence_quotes": [{
                        "citation_id": 1,
                        "quote": "UCIe is a die-to-die interconnect standard.",
                    }],
                    "uncertainty": "limited",
                },
            ],
            "limitations": [],
        }, references, minimum_support_score=0)
        cases = build_semantic_entailment_cases(lexical_validation, references)
        self.assertEqual(len(cases), 2)
        self.assertEqual(cases[0]["evidence"][0]["citation_id"], 1)

        judged = apply_semantic_entailment_judgments(
            lexical_validation,
            [
                {"claim_index": 0, "verdict": "entailed", "reason": "direct"},
                {"claim_index": 1, "verdict": "not_entailed", "reason": "latency absent"},
            ],
            verifier={"model": "judge-model", "method": "second_pass_llm_judge"},
        )
        self.assertEqual(judged["accepted_claim_count"], 1)
        self.assertEqual(judged["semantic_entailment_rejected_count"], 1)
        self.assertTrue(judged["accepted_claims"][0]["semantic_entailment_verified"])
        self.assertEqual(judged["semantic_entailment_verification"], "llm_judge_performed")
        self.assertEqual(judged["rejected_claims"][-1]["reason"], "semantic_not_entailed")

    def test_semantic_judge_error_fails_closed(self):
        validation = {
            "status": "grounded",
            "accepted_claims": [{"text": "candidate"}],
            "rejected_claims": [],
            "accepted_claim_count": 1,
            "rejected_claim_count": 0,
        }
        failed = fail_closed_semantic_entailment(
            validation,
            verifier={"model": "judge-model"},
            error="invalid JSON",
        )
        self.assertEqual(failed["status"], "insufficient")
        self.assertEqual(failed["accepted_claim_count"], 0)
        self.assertEqual(failed["rejected_claims"][0]["reason"], "semantic_verifier_error")
        self.assertEqual(
            failed["semantic_entailment_verification"],
            "llm_judge_failed_closed",
        )


if __name__ == "__main__":
    unittest.main()
