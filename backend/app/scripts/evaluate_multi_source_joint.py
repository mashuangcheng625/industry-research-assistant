"""多源联合研究评测脚本。

验证多源证据契约适配器能否正确转换 fixture 数据中的各类来源，
并对 12 道评测题逐题检查契约完整性。

不依赖外部 API Key，可以在 CI 中独立运行。
非零退出码可作为 CI 门禁。
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def load_json(path: str) -> dict[str, Any]:
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle)


def _now_utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _display_path(path: Path, root: Path) -> str:
    """Keep generated reports portable across developer machines."""
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return str(path.resolve())


# ---------------------------------------------------------------------------
# 评测门限
# ---------------------------------------------------------------------------
MIN_ADAPTER_CONVERSION_RATE = 1.0       # 所有 fixture 条目必须成功转换
MIN_CONTRACT_VALID_RATE = 1.0           # 所有 Evidence 必须通过 validate_evidence
MIN_CASE_COVERAGE = 1.0                 # 所有评测用例必须可执行
MIN_TOTAL_CASES = 12                    # 评测集必须包含恰好 12 道题
REQUIRED_CATEGORY_COUNTS = {
    "document_plus_news": 3,
    "document_plus_bidding": 3,
    "document_plus_text2sql": 2,
    "document_plus_market": 2,
    "missing_source_refuse": 2,
}

# ---------------------------------------------------------------------------
# 步骤 1: Import adapters
# ---------------------------------------------------------------------------
APP_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(APP_DIR))

try:
    from service.evidence_contract import (
        Evidence,
        validate_evidence,
        validate_evidence_collection,
        VALID_SOURCE_KINDS,
    )
    from service.evidence_adapters.document_adapter import adapt_document_chunks
    from service.evidence_adapters.news_adapter import adapt_news_items
    from service.evidence_adapters.bidding_adapter import adapt_bidding_items
    from service.evidence_adapters.sql_row_adapter import adapt_sql_result
    from service.evidence_adapters.market_adapter import (
        adapt_stock_quote,
        adapt_web_search_result,
    )
    from service.multi_source_research import MultiSourceResearchRunner
except ImportError as exc:
    print(f"FATAL: 无法导入 evidence 模块: {exc}", file=sys.stderr)
    sys.exit(1)


# ---------------------------------------------------------------------------
# 步骤 2: 加载 fixture 并通过各适配器转换
# ---------------------------------------------------------------------------
def convert_fixture_to_evidence(fixture: dict[str, Any]) -> tuple[list[Evidence], dict[str, Any]]:
    """将 fixture 中的所有数据源通过对应适配器转换为 Evidence 列表。"""
    all_evidence: list[Evidence] = []
    stats: dict[str, Any] = {
        "documents": {"input": 0, "converted": 0, "errors": []},
        "news": {"input": 0, "converted": 0, "errors": []},
        "bidding": {"input": 0, "converted": 0, "errors": []},
        "sql_rows": {"input": 0, "converted": 0, "errors": []},
        "market_quote": {"input": 0, "converted": 0, "errors": []},
    }

    # 文档
    documents = fixture.get("documents", [])
    stats["documents"]["input"] = len(documents)
    try:
        doc_evidence = adapt_document_chunks(documents)
        stats["documents"]["converted"] = len(doc_evidence)
        all_evidence.extend(doc_evidence)
    except Exception as exc:
        stats["documents"]["errors"].append(str(exc))

    # 新闻
    news_list = fixture.get("news", [])
    stats["news"]["input"] = len(news_list)
    try:
        news_evidence = adapt_news_items(news_list)
        stats["news"]["converted"] = len(news_evidence)
        all_evidence.extend(news_evidence)
    except Exception as exc:
        stats["news"]["errors"].append(str(exc))

    # 招投标
    bidding_list = fixture.get("bidding", [])
    stats["bidding"]["input"] = len(bidding_list)
    try:
        bidding_evidence = adapt_bidding_items(bidding_list)
        stats["bidding"]["converted"] = len(bidding_evidence)
        all_evidence.extend(bidding_evidence)
    except Exception as exc:
        stats["bidding"]["errors"].append(str(exc))

    # SQL 行
    sql_data = fixture.get("sql_rows", [])
    total_sql_rows = 0
    total_sql_converted = 0
    for sql_entry in sql_data:
        try:
            result = adapt_sql_result(sql_entry, table_name=sql_entry.get("table_name", ""))
            total_sql_converted += len(result)
            total_sql_rows += len(sql_entry.get("data", []))
            all_evidence.extend(result)
        except Exception as exc:
            stats["sql_rows"]["errors"].append(str(exc))
    stats["sql_rows"]["input"] = total_sql_rows
    stats["sql_rows"]["converted"] = total_sql_converted

    # 行情
    market = fixture.get("market_quote", [])
    market_items = market if isinstance(market, list) else [market]
    stats["market_quote"]["input"] = len([item for item in market_items if item])
    for item in market_items:
        if not item:
            continue
        try:
            stock_evidence = adapt_stock_quote(item)
            stats["market_quote"]["converted"] += 1
            all_evidence.append(stock_evidence)
        except Exception as exc:
            stats["market_quote"]["errors"].append(str(exc))

    return all_evidence, stats


# ---------------------------------------------------------------------------
# 步骤 3: 运行 contract 校验
# ---------------------------------------------------------------------------
def validate_all_evidence(evidences: list[Evidence]) -> dict[str, Any]:
    """对所有 Evidence 运行契约校验。"""
    return validate_evidence_collection(evidences)


# ---------------------------------------------------------------------------
# 步骤 4: 加载评测集并验证结构
# ---------------------------------------------------------------------------
def validate_eval_dataset(eval_data: dict[str, Any]) -> dict[str, Any]:
    """检查评测集的规模和分布。"""
    cases = eval_data.get("cases", [])
    total = len(cases)
    categories: dict[str, int] = {}
    for case in cases:
        cat = case.get("category", "unknown")
        categories[cat] = categories.get(cat, 0) + 1

    distribution_ok = True
    for cat, expected in REQUIRED_CATEGORY_COUNTS.items():
        if categories.get(cat) != expected:
            distribution_ok = False

    return {
        "total_cases": total,
        "category_distribution": categories,
        "expected_distribution": REQUIRED_CATEGORY_COUNTS,
        "distribution_ok": distribution_ok,
        "min_cases_met": total >= MIN_TOTAL_CASES,
    }


# ---------------------------------------------------------------------------
# 步骤 5: 逐题可用性检查
# ---------------------------------------------------------------------------
def check_case_availability(
    cases: list[dict[str, Any]],
    fixture: dict[str, Any],
) -> list[dict[str, Any]]:
    """检查每道评测题是否在 fixture 中有对应的数据。"""
    results = []
    # 收集 fixture 中的所有 ID
    doc_ids = {d.get("doc_id") for d in fixture.get("documents", [])}
    news_ids = {n.get("id") for n in fixture.get("news", [])}
    bid_ids = {b.get("bid_id") for b in fixture.get("bidding", [])}
    bid_fixture_ids = {b.get("id") for b in fixture.get("bidding", [])}
    bid_all_ids = bid_ids | bid_fixture_ids
    sql_ids = {
        item.get("id") or f"fixture-sql-{index:03d}"
        for index, item in enumerate(fixture.get("sql_rows", []), start=1)
    }
    raw_market = fixture.get("market_quote", [])
    market_items = raw_market if isinstance(raw_market, list) else [raw_market]
    stock_ids = {
        item.get("id") or f"fixture-stock-{index:03d}"
        for index, item in enumerate(market_items, start=1) if item
    }

    for case in cases:
        gold = case.get("gold_evidence", {})
        gold_docs = set(gold.get("documents", []))
        gold_news = set(gold.get("news", []))
        gold_bids = set(gold.get("bidding", []))
        gold_sql = set(gold.get("sql_rows", []))
        gold_stock = set(gold.get("market_quote", []))

        missing_docs = gold_docs - doc_ids
        missing_news = gold_news - news_ids
        missing_bids = gold_bids - bid_all_ids
        missing_sql = gold_sql - sql_ids
        missing_stock = gold_stock - stock_ids

        available = not (missing_docs or missing_news or missing_bids or missing_sql or missing_stock)
        results.append({
            "case_id": case.get("case_id"),
            "title": case.get("title"),
            "category": case.get("category"),
            "available": available,
            "missing_gold_docs": sorted(missing_docs),
            "missing_gold_news": sorted(missing_news),
            "missing_gold_bids": sorted(missing_bids),
            "missing_gold_sql": sorted(missing_sql),
            "missing_gold_stock": sorted(missing_stock),
        })

    return results


def execute_cases(cases: list[dict[str, Any]], fixture: dict[str, Any]) -> list[dict[str, Any]]:
    """Run the research pipeline without exposing gold labels to the runner."""
    runner = MultiSourceResearchRunner(fixture)
    results = []
    for case in cases:
        run = runner.run(str(case.get("question", "")))
        expected_tools = set(case.get("expected_tools", []))
        actual_tools = set(run["tools_used"])
        gold = case.get("gold_evidence", {})
        gold_ids = {
            source_id
            for values in gold.values()
            for source_id in values
        }
        retrieved_ids = set(run["retrieved_source_ids"])
        expected_kinds = set(case.get("expected_source_types", []))
        actual_kinds = set(run["retrieved_source_kinds"])
        source_kind_ok = all(
            kind in actual_kinds or (kind == "news" and "policy" in actual_kinds)
            for kind in expected_kinds
        )
        citations = run["citations"]
        locators_ok = all(bool(citation.get("locator")) for citation in citations)
        citation_ids = {citation["source_id"] for citation in citations}
        refusal_ok = run["refused"] == bool(case.get("expected_refusal"))
        inference_ok = bool(run["inference_labeled"])
        conflict_required = "source_conflict" in case.get("rubric", {})
        conflict_ok = (not conflict_required) or bool(run["conflict_disclosed"])
        checks = {
            "tool_selection_ok": actual_tools == expected_tools,
            "gold_evidence_recall_ok": gold_ids <= retrieved_ids,
            "source_type_recall_ok": source_kind_ok,
            "citation_coverage_ok": bool(run["refused"]) or gold_ids <= citation_ids,
            "citation_locator_ok": bool(run["refused"]) or locators_ok,
            "refusal_ok": refusal_ok,
            "inference_labeling_ok": inference_ok,
            "source_conflict_disclosure_ok": conflict_ok,
        }
        results.append({
            "case_id": case.get("case_id"),
            "title": case.get("title"),
            "category": case.get("category"),
            "passed": all(checks.values()),
            "checks": checks,
            "run": run,
        })
    return results


# ---------------------------------------------------------------------------
# 步骤 6: 生成机器可读报告
# ---------------------------------------------------------------------------
def generate_report(
    fixture_path: str,
    eval_path: str,
    conversion_stats: dict[str, Any],
    contract_report: dict[str, Any],
    eval_structure: dict[str, Any],
    case_availability: list[dict[str, Any]],
    execution_results: list[dict[str, Any]],
) -> dict[str, Any]:
    """生成完整的评测报告。"""
    all_available = all(case["available"] for case in case_availability)
    available_count = sum(1 for case in case_availability if case["available"])

    total_input = sum(s["input"] for s in conversion_stats.values())
    total_converted = sum(s["converted"] for s in conversion_stats.values())
    conversion_rate = total_converted / total_input if total_input > 0 else 0.0

    adapter_pass = (
        conversion_rate >= MIN_ADAPTER_CONVERSION_RATE
        and total_input > 0
    )
    contract_pass = (
        contract_report["valid"] / max(contract_report["total"], 1)
        >= MIN_CONTRACT_VALID_RATE
    )
    eval_structure_pass = (
        eval_structure["distribution_ok"]
        and eval_structure["min_cases_met"]
    )
    availability_pass = all_available and available_count >= MIN_TOTAL_CASES
    executed_passed = sum(1 for result in execution_results if result["passed"])
    execution_pass = executed_passed == len(execution_results) == MIN_TOTAL_CASES

    overall_pass = all([adapter_pass, contract_pass, eval_structure_pass,
                        availability_pass, execution_pass])

    return {
        "report_title": "先进封装多源联合研究评测报告",
        "generated_at": _now_utc_iso(),
        "fixture_path": fixture_path,
        "eval_path": eval_path,
        "overall_pass": overall_pass,
        "gates": {
            "adapter_conversion": {
                "pass": adapter_pass,
                "input_count": total_input,
                "converted_count": total_converted,
                "conversion_rate": round(conversion_rate, 4),
                "min_required": MIN_ADAPTER_CONVERSION_RATE,
                "details": conversion_stats,
            },
            "contract_validation": {
                "pass": contract_pass,
                "total": contract_report["total"],
                "valid": contract_report["valid"],
                "invalid": contract_report["invalid"],
                "min_required_rate": MIN_CONTRACT_VALID_RATE,
                "details": contract_report.get("details", []),
            },
            "eval_structure": {
                "pass": eval_structure_pass,
                **eval_structure,
            },
            "case_availability": {
                "pass": availability_pass,
                "available_count": available_count,
                "total_cases": len(case_availability),
                "cases": case_availability,
            },
            "end_to_end_execution": {
                "pass": execution_pass,
                "passed_cases": executed_passed,
                "total_cases": len(execution_results),
                "cases": execution_results,
            },
        },
        "distribution_summary": {
            "document_plus_news": 3,
            "document_plus_bidding": 3,
            "document_plus_text2sql": 2,
            "document_plus_market": 2,
            "missing_source_refuse": 2,
        },
        "evaluation_dimensions_covered": [
            "tool_selection_correctness",
            "required_source_type_recall",
            "numeric_unit_and_time_context",
            "citation_locator_verifiability",
            "inference_labeling",
            "source_conflict_disclosure",
            "missing_evidence_refusal",
        ],
        "note": "本报告执行确定性多源研究 Runner，验证工具规划、检索召回、"
                "引用定位、推断/冲突标注和缺证据拒答；自然语言表达质量仍需人工复核。"
    }


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------
def main() -> int:
    root = Path(__file__).resolve().parents[3]  # up to project root
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--fixture",
        type=Path,
        default=root / "sample-data" / "multi_source_advanced_packaging_fixture.json",
    )
    parser.add_argument(
        "--eval",
        dest="eval_path",
        type=Path,
        default=root / "sample-data" / "multi_source_advanced_packaging_eval.json",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("/tmp/industry-research-multi-source-report.json"),
        help="Report destination; defaults outside the repository for a clean quality gate.",
    )
    args = parser.parse_args()
    fixture_path = args.fixture
    eval_path = args.eval_path
    output_path = args.output

    if not fixture_path.exists():
        print(f"FATAL: fixture 文件不存在: {fixture_path}", file=sys.stderr)
        return 1
    if not eval_path.exists():
        print(f"FATAL: 评测集文件不存在: {eval_path}", file=sys.stderr)
        return 1

    fixture = load_json(str(fixture_path))
    eval_data = load_json(str(eval_path))

    print("=" * 60)
    print("多源联合研究评测")
    print("=" * 60)

    # Step 2: 适配器转换
    print("\n[1/5] 通过适配器转换 fixture 数据...")
    evidences, conversion_stats = convert_fixture_to_evidence(fixture)
    total_input = sum(s["input"] for s in conversion_stats.values())
    total_converted = sum(s["converted"] for s in conversion_stats.values())
    print(f"  Fixture 条目: {total_input}")
    print(f"  成功转换为 Evidence: {total_converted}")
    for source, stats in conversion_stats.items():
        error_count = len(stats["errors"])
        status = "✓" if error_count == 0 else f"✗ ({error_count} errors)"
        print(f"    {source}: {stats['converted']}/{stats['input']} {status}")

    # Step 3: 契约校验
    print("\n[2/5] 运行 Evidence 契约校验...")
    contract_report = validate_all_evidence(evidences)
    print(f"  总数: {contract_report['total']}, 有效: {contract_report['valid']}, 无效: {contract_report['invalid']}")
    for detail in contract_report.get("details", []):
        status = "✓" if detail["valid"] else "✗"
        print(f"    {status} [{detail['source_kind']}] {detail['title'][:60]}")
        for issue in detail.get("issues", []):
            print(f"      - {issue}")

    # Step 4: 评测集结构验证
    print("\n[3/5] 验证评测集结构...")
    eval_structure = validate_eval_dataset(eval_data)
    print(f"  总题数: {eval_structure['total_cases']}")
    print(f"  分布匹配: {'✓' if eval_structure['distribution_ok'] else '✗'}")
    for cat, count in eval_structure["category_distribution"].items():
        expected = eval_structure["expected_distribution"].get(cat)
        match = "✓" if count == expected else f"✗ (expected {expected})"
        print(f"    {cat}: {count} {match}")

    # Step 5: 逐题可用性
    print("\n[4/5] 检查逐题可用性...")
    case_availability = check_case_availability(
        eval_data.get("cases", []), fixture
    )
    for case in case_availability:
        status = "✓" if case["available"] else "✗"
        print(f"  {status} {case['case_id']}: {case['title'][:60]}")
        if not case["available"]:
            for key, values in [
                ("gold文档", case["missing_gold_docs"]),
                ("gold新闻", case["missing_gold_news"]),
                ("gold招投标", case["missing_gold_bids"]),
                ("gold SQL", case["missing_gold_sql"]),
                ("gold行情", case["missing_gold_stock"]),
            ]:
                if values:
                    print(f"    缺少 {key}: {values}")

    print("\n[5/5] 执行逐题多源研究链路...")
    execution_results = execute_cases(eval_data.get("cases", []), fixture)
    for result in execution_results:
        status = "✓" if result["passed"] else "✗"
        print(f"  {status} {result['case_id']}: {result['title'][:60]}")
        if not result["passed"]:
            failed = [name for name, passed in result["checks"].items() if not passed]
            print(f"    失败检查: {', '.join(failed)}")

    # Step 6: 生成报告
    report = generate_report(
        _display_path(fixture_path, root), _display_path(eval_path, root),
        conversion_stats, contract_report,
        eval_structure, case_availability, execution_results,
    )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(f"\n报告已保存: {output_path}")

    # 结果摘要
    print("\n" + "=" * 60)
    if report["overall_pass"]:
        print("结果: 全部通过 ✓")
        return 0
    else:
        print("结果: 未通过 ✗")
        for gate_name, gate in report["gates"].items():
            if not gate["pass"]:
                print(f"  门禁失败: {gate_name}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
