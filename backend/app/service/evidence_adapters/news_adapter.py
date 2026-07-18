"""行业资讯 → 统一 Evidence 适配器。

将 IndustryNews 对象的 to_dict() 输出转换为 Evidence 对象。
"""

from __future__ import annotations

from typing import Any

from service.evidence_contract import Evidence


def adapt_news_item(news: dict[str, Any]) -> Evidence:
    """将单条行业资讯转换为 Evidence 对象。

    预期输入字段 (来自 IndustryNews.to_dict()):
        id: 数据库主键
        title: 资讯标题
        content: 资讯内容/摘要
        source: 来源名称
        source_url: 来源链接
        category: 分类 (政策/纪要/研报/新闻)
        department: 发布部门
        publish_time: 发布时间 (ISO-8601 字符串)
        collected_at: 采集时间 (ISO-8601 字符串)
    """
    title = str(news.get("title") or "无标题")
    content_text = str(news.get("content") or "")
    publisher = str(news.get("department") or news.get("source") or "未知来源")
    category = str(news.get("category") or "新闻")

    # 新闻资讯的定位信息
    locator: dict[str, Any] = {
        "news_id": str(news.get("id") or ""),
    }

    # 根据分类确定 source_kind
    source_kind = _category_to_source_kind(category)

    # 根据来源确定质量层级
    quality_tier = _classify_news_quality(publisher, category)

    return Evidence.create(
        source_kind=source_kind,
        title=title,
        publisher=publisher,
        content=content_text,
        url=str(news.get("source_url")) if news.get("source_url") else None,
        published_at=str(news.get("publish_time")) if news.get("publish_time") else None,
        retrieved_at=str(news.get("collected_at")) if news.get("collected_at") else None,
        locator=locator,
        quality_tier=quality_tier,
        license_or_terms=_infer_news_license(publisher, category),
    )


def adapt_news_items(news_list: list[dict[str, Any]]) -> list[Evidence]:
    """批量转换行业资讯。"""
    return [adapt_news_item(item) for item in news_list]


# ---- 内部辅助函数 ----


def _category_to_source_kind(category: str) -> str:
    """将 IndustryNews 分类映射到 Evidence source_kind。"""
    mapping = {
        "政策": "policy",
        "纪要": "policy",
        "研报": "news",
        "新闻": "news",
    }
    return mapping.get(category, "news")


_GOVERNMENT_KEYWORDS = {
    "国务院", "工信部", "发改委", "科技部", "财政部", "住建部", "公安部",
    "交通运输部", "自然资源部", "工业和信息化部", "国家发展改革委",
    "交通运输厅", "政府", "部委", "中共中央",
}


def _classify_news_quality(publisher: str, category: str) -> str:
    """根据发布方和分类评估资讯质量层级。"""
    if category == "政策":
        return "official"
    for keyword in _GOVERNMENT_KEYWORDS:
        if keyword in publisher:
            return "official"
    if category == "研报":
        return "secondary"
    return "unknown"


def _infer_news_license(publisher: str, category: str) -> str:
    """推断资讯使用条款。"""
    if category == "政策":
        return "政府公开信息，可引用需注明来源"
    for keyword in _GOVERNMENT_KEYWORDS:
        if keyword in publisher:
            return "政府公开信息，可引用需注明来源"
    return "not_assessed"
