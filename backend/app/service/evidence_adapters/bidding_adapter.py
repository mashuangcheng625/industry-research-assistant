"""招投标信息 → 统一 Evidence 适配器。

将 BiddingInfo 对象的 to_dict() 输出转换为 Evidence 对象。
"""

from __future__ import annotations

from typing import Any

from service.evidence_contract import Evidence


def adapt_bidding_item(bidding: dict[str, Any]) -> Evidence:
    """将单条招投标信息转换为 Evidence 对象。

    预期输入字段 (来自 BiddingInfo.to_dict()):
        id: 数据库主键
        bid_id: 招投标项目 ID
        title: 项目标题
        notice_type: 公告类型 (招标/中标/采购 等)
        province: 省份
        city: 城市
        content: 详细内容 (可选)
        publish_time: 发布时间 (ISO-8601 字符串)
        source: 数据来源 (如 "81api")
        collected_at: 采集时间 (ISO-8601 字符串)
    """
    title = str(bidding.get("title") or "无标题")
    content_text = str(bidding.get("content") or bidding.get("title") or "")
    notice_type = str(bidding.get("notice_type") or "")
    province = str(bidding.get("province") or "")
    city = str(bidding.get("city") or "")
    bid_id = str(bidding.get("bid_id") or "")
    source = str(bidding.get("source") or "81api")

    # 构建发布方描述
    location = f"{province}{city}".strip() if province or city else ""
    publisher = f"{location} {notice_type}公告" if location else f"{notice_type}公告 (数据来源: {source})"

    locator: dict[str, Any] = {
        "notice_id": bid_id,
        "notice_type": notice_type,
        "province": province,
        "city": city,
    }

    return Evidence.create(
        source_kind="bidding",
        title=title,
        publisher=publisher.strip(),
        content=content_text,
        url=None,  # 招投标 API 通常不返回公开 URL
        published_at=str(bidding.get("publish_time")) if bidding.get("publish_time") else None,
        retrieved_at=str(bidding.get("collected_at")) if bidding.get("collected_at") else None,
        locator=locator,
        quality_tier=_classify_bidding_quality(source, notice_type),
        license_or_terms="招投标公告，可引用需注明来源和公告编号",
    )


def adapt_bidding_items(bidding_list: list[dict[str, Any]]) -> list[Evidence]:
    """批量转换招投标信息。"""
    return [adapt_bidding_item(item) for item in bidding_list]


# ---- 内部辅助函数 ----


def _classify_bidding_quality(source: str, notice_type: str) -> str:
    """评估招投标来源质量层级。"""
    # 中标公告来源于官方采购系统，视为一手资料
    if "中标" in notice_type:
        return "primary"
    # 招标公告也是官方发布
    return "primary"
