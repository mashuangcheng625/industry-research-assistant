"""Evaluation-set governance tests."""
from pathlib import Path
import sys
import unittest

APP_DIR = Path(__file__).resolve().parents[1] / "app"
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

from scripts.validate_rag_eval_dataset import (  # noqa: E402
    question_similarity,
    validate_cases,
    validate_public_questions,
)


def valid_case(case_id: str = "design-001"):
    return {
        "id": case_id,
        "domain": "芯片设计与EDA/IP",
        "category": "单文档事实题",
        "knowledge_base": "semiconductor_chip_design_eda_ip",
        "question": "OpenROAD 的布局和布线阶段分别解决什么问题？",
        "expected_retrieval": True,
        "required_term_groups": [["placement", "布局"], ["routing", "布线"]],
        "gold_sources": [{"document": "openroad.md"}],
        "must_cite": True,
        "min_group_coverage": 1.0,
        "split": "test",
    }


def valid_public_question(case_id: str = "design-hidden-001"):
    return {
        "id": case_id,
        "domain": "芯片设计与EDA/IP",
        "category": "单文档事实题",
        "knowledge_base": "semiconductor_chip_design_eda_ip",
        "question": "OpenROAD 的布局和布线阶段分别解决什么问题？",
        "split": "hidden",
    }


class RagEvalDatasetTests(unittest.TestCase):
    def test_valid_case_has_no_schema_errors(self):
        issues = validate_cases([valid_case()])
        self.assertFalse([issue for issue in issues if issue["level"] == "error"])

    def test_duplicate_question_and_id_are_rejected(self):
        issues = validate_cases([valid_case(), valid_case()])
        codes = {issue["code"] for issue in issues}
        self.assertIn("duplicate_id", codes)
        self.assertIn("duplicate_question", codes)

    def test_positive_case_requires_gold_evidence(self):
        case = valid_case()
        case["gold_sources"] = []
        codes = {issue["code"] for issue in validate_cases([case])}
        self.assertIn("missing_gold", codes)

    def test_gold_terms_must_exist_in_gold_document(self):
        case = valid_case()
        issues = validate_cases(
            [case], source_documents={"openroad.md": "Placement is documented."}
        )
        self.assertIn("gold_term_absent", {issue["code"] for issue in issues})
        self.assertFalse([
            issue for issue in validate_cases(
                [case],
                source_documents={"openroad.md": "Placement and rout\ning are documented."},
            )
            if issue["code"] == "gold_term_absent"
        ])

    def test_negative_case_requires_refusal_contract(self):
        case = valid_case()
        case.update({"expected_retrieval": False, "gold_sources": [], "must_cite": False})
        codes = {issue["code"] for issue in validate_cases([case])}
        self.assertIn("refusal_policy", codes)

    def test_question_similarity_flags_paraphrase_but_not_other_topic(self):
        self.assertGreater(
            question_similarity(
                "OpenROAD 的布局和布线阶段分别解决什么问题？",
                "OpenROAD布局和布线阶段分别解决什么问题?",
            ),
            0.78,
        )
        self.assertLess(
            question_similarity(
                "OpenROAD 的布局和布线阶段分别解决什么问题？",
                "先进封装为什么需要热管理？",
            ),
            0.3,
        )

    def test_public_question_has_no_schema_errors(self):
        issues = validate_public_questions([valid_public_question()])
        self.assertFalse([issue for issue in issues if issue["level"] == "error"])

    def test_public_question_rejects_private_labels(self):
        case = valid_public_question()
        case.update({"gold_sources": [{"document": "openroad.md"}], "expected_retrieval": True})
        codes = {issue["code"] for issue in validate_public_questions([case])}
        self.assertIn("private_label_leak", codes)

    def test_public_question_requires_public_fields_and_blind_split(self):
        case = valid_public_question()
        del case["category"]
        case["split"] = "development"
        codes = {issue["code"] for issue in validate_public_questions([case])}
        self.assertIn("missing_public_field", codes)
        self.assertIn("invalid_public_split", codes)


if __name__ == "__main__":
    unittest.main()
