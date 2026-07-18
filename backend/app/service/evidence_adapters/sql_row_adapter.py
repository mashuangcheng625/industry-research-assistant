"""Text2SQL 查询结果行 → 统一 Evidence 适配器。

将 Text2SQL 服务返回的查询结果中的每一行转换为 Evidence 对象。
"""

from __future__ import annotations

import hashlib
from typing import Any

from service.evidence_contract import Evidence


def adapt_sql_row(
    row: dict[str, Any],
    *,
    table_name: str = "",
    sql: str = "",
    columns: list[str] | None = None,
) -> Evidence:
    """将单行 SQL 查询结果转换为 Evidence 对象。

    Args:
        row: 查询结果中的一行数据 (dict)
        table_name: 来源表名
        sql: 执行的 SQL 语句 (用于溯源)
        columns: 列名列表 (用于构建 locator)
    """
    cols = columns or list(row.keys())

    # 生成行内容的稳定哈希作为 row_id
    row_text = "|".join(f"{col}={row.get(col)}" for col in sorted(cols))
    row_hash = hashlib.sha256(row_text.encode("utf-8")).hexdigest()[:16]

    # 构建人类可读的内容描述
    content_parts = []
    for col in cols:
        value = row.get(col)
        if value is not None:
            content_parts.append(f"{col}={value}")
    content_text = "; ".join(content_parts)

    # 尝试推断有意义的标题
    title_cols = [
        col for col in cols
        if col.lower() in {
            "industry_name", "company_name", "metric_name",
            "policy_name", "name", "title", "department",
        }
    ]
    title = str(row.get(title_cols[0])) if title_cols else f"SQL 行 ({row_hash[:8]})"

    # 尝试推断发布方
    source_col = next(
        (col for col in cols if "source" in col.lower()), None
    )
    publisher = str(row.get(source_col)) if source_col else "产业数据库"

    locator: dict[str, Any] = {
        "row_id": row_hash,
        "table_name": table_name,
        "columns": cols,
    }
    # 不将完整 SQL 放入 locator（可能很长），但保留用于调试的摘要
    if sql:
        locator["sql_hash"] = hashlib.sha256(sql.encode("utf-8")).hexdigest()[:12]

    return Evidence.create(
        source_kind="sql_row",
        title=str(title),
        publisher=str(publisher),
        content=content_text,
        url=None,
        as_of=_infer_as_of(row, cols),
        locator=locator,
        quality_tier="primary",  # 结构化数据库视为一手数据
        license_or_terms="结构化产业数据，引用需注明数据库和查询口径",
    )


def adapt_sql_result(
    result: dict[str, Any],
    *,
    table_name: str = "",
) -> list[Evidence]:
    """将完整 Text2SQL 查询结果转换为 Evidence 列表。

    预期输入字段:
        data: 行数据列表 [{col: value, ...}]
        columns: 列名列表 [str, ...]
        sql: 执行的 SQL 语句
    """
    rows = result.get("data", [])
    columns = result.get("columns", [])
    sql = result.get("sql", "")

    return [
        adapt_sql_row(row, table_name=table_name, sql=sql, columns=columns)
        for row in rows
    ]


# ---- 内部辅助函数 ----


def _infer_as_of(row: dict[str, Any], columns: list[str]) -> str | None:
    """从行数据中推断统计口径时点。"""
    # 查找时间相关列
    time_keywords = ("year", "quarter", "month", "period", "date", "as_of")
    found = []
    for col in columns:
        col_lower = col.lower()
        if any(keyword in col_lower for keyword in time_keywords):
            value = row.get(col)
            if value is not None:
                found.append(f"{col}={value}")
    if found:
        return "; ".join(found)
    return None
