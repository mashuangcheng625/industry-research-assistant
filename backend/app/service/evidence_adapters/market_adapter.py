"""股票/市场行情 → 统一 Evidence 适配器。

将 StockService 查询结果转换为 Evidence 对象。
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from service.evidence_contract import Evidence


def adapt_stock_quote(quote: dict[str, Any]) -> Evidence:
    """将单条股票行情数据转换为 Evidence 对象。

    预期输入字段:
        name: 股票名称
        gid: 股票代码
        nowPri: 当前价格
        increase: 涨跌额
        increPer: 涨跌幅
        todayStartPri: 今日开盘价
        yestodEndPri: 昨日收盘价
        todayMax: 今日最高价
        todayMin: 今日最低价
        traAmount: 成交量
        traNumber: 成交额
    """
    name = str(quote.get("name") or "未知")
    code = str(quote.get("gid") or "")
    now_pri = quote.get("nowPri", "")
    incre_per = quote.get("increPer", "")
    increase = quote.get("increase", "")
    today_start = quote.get("todayStartPri", "")
    yestod_end = quote.get("yestodEndPri", "")
    today_max = quote.get("todayMax", "")
    today_min = quote.get("todayMin", "")

    # 构建人类可读内容
    content_text = (
        f"{name} ({code}): "
        f"现价 ¥{now_pri}, 涨跌 {increase} ({incre_per}), "
        f"今开 ¥{today_start}, 昨收 ¥{yestod_end}, "
        f"最高 ¥{today_max}, 最低 ¥{today_min}"
    )

    publisher = "聚合数据股票API"

    locator: dict[str, Any] = {
        "stock_code": code,
        "data_provider": "juhe_finance",
    }

    # 优先保留上游行情时点；缺失时才使用适配时刻。
    as_of = str(
        quote.get("as_of")
        or datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    )

    return Evidence.create(
        source_kind="market_quote",
        title=f"{name} ({code}) 实时行情",
        publisher=publisher,
        content=content_text,
        url=None,
        as_of=as_of,
        locator=locator,
        quality_tier="secondary",  # 第三方数据提供商，非交易所直连
        license_or_terms="第三方行情数据，仅用于研究参考，不构成投资建议",
    )


def adapt_stock_data_points(
    data_points: list[dict[str, Any]],
    company_name: str = "",
) -> list[Evidence]:
    """将 Scout 中股票相关的 data_points 转换为 Evidence 列表。

    预期输入字段 (来自 _fetch_stock_data_if_relevant):
        name: 指标名称
        value: 指标值
        unit: 单位
        source: 数据来源
        source_type: 来源类型
    """
    evidences = []
    for dp in data_points:
        content_text = f"{dp.get('name', '')}: {dp.get('value', '')} {dp.get('unit', '')}"
        if not content_text.strip():
            continue

        evidence = Evidence.create(
            source_kind="market_quote",
            title=str(dp.get("name", "市场数据")),
            publisher=str(dp.get("source", "聚合数据股票API")),
            content=content_text,
            url=None,
            as_of=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            locator={"data_type": "data_point"},
            quality_tier="secondary",
            license_or_terms="第三方行情数据，仅用于研究参考，不构成投资建议",
        )
        evidences.append(evidence)
    return evidences


def adapt_web_search_result(search_result: dict[str, Any]) -> Evidence:
    """将网络搜索结果转换为 Evidence 对象。

    预期输入字段:
        url: 链接
        title / name: 标题
        summary / snippet: 摘要
        site_name / siteName: 来源网站
        date: 发布时间 (可选)
    """
    title = str(search_result.get("title") or search_result.get("name") or "无标题")
    content_text = str(
        search_result.get("summary") or search_result.get("snippet") or ""
    )
    url = str(search_result.get("url") or "")
    site_name = str(search_result.get("site_name") or search_result.get("siteName") or "未知来源")
    date = str(search_result.get("date") or search_result.get("datePublished") or "")

    publisher = site_name

    locator: dict[str, Any] = {
        "search_engine": "bocha",
    }

    return Evidence.create(
        source_kind="web_search",
        title=title,
        publisher=publisher,
        content=content_text,
        url=url if url else None,
        published_at=date if date else None,
        locator=locator,
        quality_tier="unknown",
        license_or_terms="not_assessed",
    )
