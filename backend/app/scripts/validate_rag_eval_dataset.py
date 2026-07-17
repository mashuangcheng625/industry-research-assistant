"""Validate semiconductor RAG evaluation sets before they become scoreboards."""
from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any, Iterable


DOMAIN_KNOWLEDGE_BASES = {
    "芯片设计与EDA/IP": "semiconductor_chip_design_eda_ip",
    "半导体材料与设备": "semiconductor_materials_equipment",
    "晶圆制造与前道工艺": "semiconductor_process",
    "封装与测试": "semiconductor_packaging_testing",
}
ALLOWED_SPLITS = {"development", "regression", "test", "hidden"}
PUBLIC_QUESTION_FIELDS = {
    "id", "domain", "category", "split", "knowledge_base", "question",
}
PRIVATE_LABEL_FIELDS = {
    "expected_retrieval",
    "expected_terms",
    "required_term_groups",
    "gold_sources",
    "must_cite",
    "must_not_cite",
    "must_refuse",
    "forbidden_terms",
    "min_group_coverage",
    "gold_source_match",
}


def normalized_question(question: str) -> str:
    return re.sub(r"[^\w]+", "", question.casefold(), flags=re.UNICODE)


def question_ngrams(question: str, width: int = 3) -> set[str]:
    value = normalized_question(question)
    if len(value) <= width:
        return {value} if value else set()
    return {value[index:index + width] for index in range(len(value) - width + 1)}


def question_similarity(left: str, right: str) -> float:
    left_terms, right_terms = question_ngrams(left), question_ngrams(right)
    union = left_terms | right_terms
    return len(left_terms & right_terms) / len(union) if union else 1.0


def _issue(level: str, code: str, message: str, case_id: str | None = None) -> dict[str, str]:
    row = {"level": level, "code": code, "message": message}
    if case_id:
        row["case_id"] = case_id
    return row


def validate_cases(
    cases: list[dict[str, Any]],
    *,
    min_cases: int = 0,
    require_balanced: bool = False,
    source_documents: dict[str, str] | None = None,
) -> list[dict[str, str]]:
    issues: list[dict[str, str]] = []
    if len(cases) < min_cases:
        issues.append(_issue("error", "case_count", f"题目数 {len(cases)} 少于要求 {min_cases}"))

    ids: Counter[str] = Counter(str(case.get("id") or "") for case in cases)
    for case_id, count in ids.items():
        if not case_id:
            issues.append(_issue("error", "missing_id", "存在缺少 id 的题目"))
        elif count > 1:
            issues.append(_issue("error", "duplicate_id", f"id 重复 {count} 次", case_id))

    seen_questions: dict[str, str] = {}
    for case in cases:
        case_id = str(case.get("id") or "<unknown>")
        domain = case.get("domain")
        if domain not in DOMAIN_KNOWLEDGE_BASES:
            issues.append(_issue("error", "invalid_domain", f"无效领域: {domain}", case_id))
        elif case.get("knowledge_base") != DOMAIN_KNOWLEDGE_BASES[domain]:
            issues.append(_issue("error", "knowledge_base_mismatch", "领域与知识库不匹配", case_id))
        question = str(case.get("question") or "").strip()
        if len(question) < 8:
            issues.append(_issue("error", "short_question", "问题为空或过短", case_id))
        key = normalized_question(question)
        if key in seen_questions:
            issues.append(_issue(
                "error", "duplicate_question", f"与 {seen_questions[key]} 问题相同", case_id
            ))
        else:
            seen_questions[key] = case_id

        split = case.get("split")
        if split is not None and split not in ALLOWED_SPLITS:
            issues.append(_issue("error", "invalid_split", f"无效 split: {split}", case_id))
        expected = case.get("expected_retrieval")
        if not isinstance(expected, bool):
            issues.append(_issue("error", "missing_expectation", "expected_retrieval 必须是布尔值", case_id))
        elif expected:
            if not case.get("required_term_groups"):
                issues.append(_issue("error", "missing_terms", "正例缺少 required_term_groups", case_id))
            if not case.get("gold_sources"):
                issues.append(_issue("error", "missing_gold", "正例缺少 gold_sources", case_id))
            if case.get("must_cite") is not True:
                issues.append(_issue("error", "citation_policy", "正例必须要求引用", case_id))
            coverage = case.get("min_group_coverage")
            if not isinstance(coverage, (int, float)) or not 0 < coverage <= 1:
                issues.append(_issue("error", "invalid_coverage", "正例覆盖率必须在 (0, 1]", case_id))
            if source_documents is not None and case.get("gold_sources"):
                names = [
                    source.get("document") if isinstance(source, dict) else source
                    for source in case["gold_sources"]
                ]
                missing_documents = [name for name in names if name not in source_documents]
                if missing_documents:
                    issues.append(_issue(
                        "error", "missing_gold_document",
                        f"金标文档不存在: {missing_documents}", case_id,
                    ))
                evidence = " ".join(source_documents.get(name, "") for name in names)
                normalized_evidence = re.sub(r"\s+", "", evidence.casefold())
                for group in case.get("required_term_groups") or []:
                    if not any(
                        re.sub(r"\s+", "", str(term).casefold()) in normalized_evidence
                        for term in group
                    ):
                        issues.append(_issue(
                            "error", "gold_term_absent",
                            f"金标文档不含术语组: {group}", case_id,
                        ))
        else:
            if case.get("must_refuse") is not True or case.get("must_not_cite") is not True:
                issues.append(_issue("error", "refusal_policy", "负例必须拒答且不得引用", case_id))
            if case.get("gold_sources"):
                issues.append(_issue("error", "negative_gold", "负例不得配置金标来源", case_id))

    # Exact duplicates are errors; near duplicates are review warnings.
    for left_index, left in enumerate(cases):
        for right in cases[left_index + 1:]:
            if normalized_question(left.get("question", "")) == normalized_question(right.get("question", "")):
                continue
            similarity = question_similarity(left.get("question", ""), right.get("question", ""))
            if similarity >= 0.78:
                issues.append(_issue(
                    "warning",
                    "near_duplicate_question",
                    f"与 {left.get('id')} 相似度 {similarity:.2f}",
                    str(right.get("id")),
                ))

    if require_balanced:
        domain_counts = Counter(case.get("domain") for case in cases)
        expected_count = len(cases) // len(DOMAIN_KNOWLEDGE_BASES)
        for domain in DOMAIN_KNOWLEDGE_BASES:
            if domain_counts[domain] != expected_count:
                issues.append(_issue(
                    "error", "domain_imbalance",
                    f"{domain} 有 {domain_counts[domain]} 题，应为 {expected_count} 题",
                ))
    return issues


def validate_public_questions(
    cases: list[dict[str, Any]],
    *,
    min_cases: int = 0,
    require_balanced: bool = False,
) -> list[dict[str, str]]:
    """Validate public test/hidden questions and reject any private answer labels."""
    issues: list[dict[str, str]] = []
    if len(cases) < min_cases:
        issues.append(_issue("error", "case_count", f"题目数 {len(cases)} 少于要求 {min_cases}"))

    ids: Counter[str] = Counter(str(case.get("id") or "") for case in cases)
    for case_id, count in ids.items():
        if not case_id:
            issues.append(_issue("error", "missing_id", "存在缺少 id 的题目"))
        elif count > 1:
            issues.append(_issue("error", "duplicate_id", f"id 重复 {count} 次", case_id))

    seen_questions: dict[str, str] = {}
    for case in cases:
        case_id = str(case.get("id") or "<unknown>")
        missing_fields = sorted(PUBLIC_QUESTION_FIELDS - case.keys())
        if missing_fields:
            issues.append(_issue(
                "error", "missing_public_field", f"缺少公开字段: {missing_fields}", case_id,
            ))
        leaked_fields = sorted(PRIVATE_LABEL_FIELDS & case.keys())
        if leaked_fields:
            issues.append(_issue(
                "error", "private_label_leak", f"公开问题含私有标签: {leaked_fields}", case_id,
            ))

        domain = case.get("domain")
        if domain not in DOMAIN_KNOWLEDGE_BASES:
            issues.append(_issue("error", "invalid_domain", f"无效领域: {domain}", case_id))
        elif case.get("knowledge_base") != DOMAIN_KNOWLEDGE_BASES[domain]:
            issues.append(_issue("error", "knowledge_base_mismatch", "领域与知识库不匹配", case_id))

        if not str(case.get("category") or "").strip():
            issues.append(_issue("error", "missing_category", "category 不得为空", case_id))
        question = str(case.get("question") or "").strip()
        if len(question) < 8:
            issues.append(_issue("error", "short_question", "问题为空或过短", case_id))
        key = normalized_question(question)
        if key in seen_questions:
            issues.append(_issue(
                "error", "duplicate_question", f"与 {seen_questions[key]} 问题相同", case_id,
            ))
        else:
            seen_questions[key] = case_id

        split = case.get("split")
        if split not in {"test", "hidden"}:
            issues.append(_issue(
                "error", "invalid_public_split", f"公开无标签问题只允许 test/hidden: {split}", case_id,
            ))

    if require_balanced:
        domain_counts = Counter(case.get("domain") for case in cases)
        expected_count = len(cases) // len(DOMAIN_KNOWLEDGE_BASES)
        for domain in DOMAIN_KNOWLEDGE_BASES:
            if domain_counts[domain] != expected_count:
                issues.append(_issue(
                    "error", "domain_imbalance",
                    f"{domain} 有 {domain_counts[domain]} 题，应为 {expected_count} 题",
                ))
    return issues


def load_cases(paths: Iterable[Path]) -> list[dict[str, Any]]:
    cases: list[dict[str, Any]] = []
    for path in paths:
        payload = json.loads(path.read_text(encoding="utf-8"))
        rows = payload.get("cases") if isinstance(payload, dict) else payload
        if not isinstance(rows, list):
            raise ValueError(f"{path}: 顶层必须是数组或包含 cases 数组")
        cases.extend(rows)
    return cases


def load_source_documents(directories: Iterable[Path]) -> dict[str, str]:
    documents: dict[str, str] = {}
    # Earlier directories have priority, allowing normalized-v2 to override v1.
    for directory in reversed(list(directories)):
        for path in directory.glob("*.md"):
            documents[path.name] = path.read_text(encoding="utf-8", errors="replace")
    return documents


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("datasets", type=Path, nargs="+")
    parser.add_argument("--min-cases", type=int, default=0)
    parser.add_argument("--require-balanced", action="store_true")
    parser.add_argument(
        "--questions-only",
        action="store_true",
        help="校验仅包公开字段的 test/hidden 问题集，并拒绝私有标签",
    )
    parser.add_argument("--corpus-dir", type=Path, action="append", default=[])
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    cases = load_cases(args.datasets)
    if args.questions_only:
        issues = validate_public_questions(
            cases,
            min_cases=args.min_cases,
            require_balanced=args.require_balanced,
        )
    else:
        issues = validate_cases(
            cases,
            min_cases=args.min_cases,
            require_balanced=args.require_balanced,
            source_documents=load_source_documents(args.corpus_dir) if args.corpus_dir else None,
        )
    report = {
        "datasets": [str(path) for path in args.datasets],
        "case_count": len(cases),
        "domain_counts": dict(Counter(case.get("domain") for case in cases)),
        "category_counts": dict(Counter(case.get("category") for case in cases)),
        "split_counts": dict(Counter(case.get("split", "unspecified") for case in cases)),
        "errors": sum(issue["level"] == "error" for issue in issues),
        "warnings": sum(issue["level"] == "warning" for issue in issues),
        "issues": issues,
    }
    rendered = json.dumps(report, ensure_ascii=False, indent=2)
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(rendered, encoding="utf-8")
    print(rendered)
    return 1 if report["errors"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
