"""招投标信息服务 - 81API 招投标数据

P1-2：所有外部 HTTP 调用通过 ``core.provider_reliability`` 包装，
统一提供超时 / 有限重试 / 失败降级与 ``ProviderOutcome``。失败路径
不再编造结果 —— 服务返回 ``{"success": false, ..., "degraded": True,
"provider_code": "..."}`` 以便上层编排区分"零结果"和"采集失败"。
"""
import os
import json
import logging
import httpx
from typing import Dict, Any, Optional, List
from dataclasses import dataclass
from datetime import datetime
from urllib.parse import quote

from core.provider_reliability import (
    PROVIDER_NOT_CONFIGURED,
    PROVIDER_OK,
    ProviderOutcome,
    run_provider_async,
)

logger = logging.getLogger(__name__)


# 招投标 API 调用的默认超时与重试预算。
DEFAULT_BIDDING_TIMEOUT_SECONDS = float(
    os.getenv("BIDDING_PROVIDER_TIMEOUT_SECONDS", "10")
)
DEFAULT_BIDDING_MAX_ATTEMPTS = int(
    os.getenv("BIDDING_PROVIDER_MAX_ATTEMPTS", "2")
)


@dataclass
class BidInfo:
    """招投标信息"""
    id: str  # 项目ID (bid)
    title: str  # 项目标题
    notice_type: str  # 公告类型 (中标/招标/采购等)
    province: str  # 省份
    city: str  # 城市
    publish_time: str  # 发布时间
    source: str  # 来源

    @classmethod
    def from_dict(cls, data: Dict) -> "BidInfo":
        return cls(
            id=data.get("bid", ""),
            title=data.get("title", ""),
            notice_type=data.get("noticeType", ""),
            province=data.get("province", ""),
            city=data.get("city", "") or "",
            publish_time=data.get("publishTime", ""),
            source="81api",
        )

    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "title": self.title,
            "notice_type": self.notice_type,
            "province": self.province,
            "city": self.city,
            "publish_time": self.publish_time,
            "source": self.source,
        }

    def format_display(self) -> str:
        """格式化显示"""
        location = f"{self.province}"
        if self.city:
            location += f" {self.city}"
        return f"""
📋 {self.title}
━━━━━━━━━━━━━━━━━━━━━━━━
类型: {self.notice_type}
地区: {location}
发布时间: {self.publish_time}
ID: {self.id}
"""


class BiddingService:
    """招投标信息服务 - 81API"""

    # 81API 招投标接口
    BASE_URL = "https://bid.81api.com"

    # API 端点
    ENDPOINTS = {
        "win_bid": "/queryWinBid",      # 中标查询
        "bid": "/queryBid",              # 招标查询
        "detail": "/queryBidDetail",     # 标书详情
    }

    def __init__(self):
        self.app_code = os.getenv("BID_APP_CODE", "")

        if not self.app_code:
            print("警告: BID_APP_CODE 环境变量未设置")

        # 最近一次外部调用的 ProviderOutcome；上层多源编排可通过
        # ``last_outcome`` 区分"零结果"和"采集失败"。
        self._outcomes: List[ProviderOutcome] = []

    def last_outcome(self) -> Optional[ProviderOutcome]:
        """Return the most recent provider outcome or ``None`` if no
        call has been made yet."""

        return self._outcomes[-1] if self._outcomes else None

    def record_outcome(self, outcome: ProviderOutcome) -> None:
        """Append an outcome to the rolling buffer (bounded to 32)."""

        self._outcomes.append(outcome)
        if len(self._outcomes) > 32:
            self._outcomes = self._outcomes[-32:]

    @staticmethod
    def _degraded_payload(error: str, code: str, **extra: Any) -> Dict[str, Any]:
        """Return a structured degraded payload used for failure paths.

        The shape is intentionally backwards-compatible with the
        pre-P1-2 contract (``success``, ``error``) but adds
        ``degraded`` and ``provider_code`` so the orchestrator can
        distinguish "no rows" from "the upstream failed".
        """

        payload: Dict[str, Any] = {
            "success": False,
            "error": error,
            "degraded": True,
            "provider_code": code,
            "results": [],
            "total": 0,
        }
        payload.update(extra)
        return payload

    async def search_win_bids(
        self,
        keyword: str,
        page: int = 1
    ) -> Dict[str, Any]:
        """
        搜索中标信息

        Args:
            keyword: 搜索关键词
            page: 页码 (从1开始)

        Returns:
            搜索结果
        """
        return await self._search(
            endpoint=self.ENDPOINTS["win_bid"],
            keyword=keyword,
            page=page
        )

    async def search_bids(
        self,
        keyword: str,
        category: Optional[str] = None,
        region: Optional[str] = None,
        page: int = 1,
        page_size: int = 10
    ) -> Dict[str, Any]:
        """
        搜索招投标信息 (统一接口)

        Args:
            keyword: 搜索关键词
            category: 项目类别 (招标/中标) - 决定使用哪个端点
            region: 地区 (暂不支持，API按省市返回)
            page: 页码
            page_size: 每页数量 (API固定返回10条)

        Returns:
            搜索结果
        """
        # 根据类别选择端点
        if category and "招标" in category:
            endpoint = self.ENDPOINTS["bid"]
        else:
            # 默认查询中标信息
            endpoint = self.ENDPOINTS["win_bid"]

        return await self._search(endpoint, keyword, page)

    async def search_bid_notices(
        self,
        keyword: str,
        page: int = 1
    ) -> Dict[str, Any]:
        """
        搜索招标公告

        Args:
            keyword: 搜索关键词
            page: 页码

        Returns:
            搜索结果
        """
        return await self._search(
            endpoint=self.ENDPOINTS["bid"],
            keyword=keyword,
            page=page
        )

    async def get_bid_detail(self, bid_id: str) -> Dict[str, Any]:
        """
        获取标书详情

        Args:
            bid_id: 标书ID

        Returns:
            标书详情。失败路径返回 ``{"success": False, "degraded": True,
            "provider_code": "..."}`` 字典，对调用方语义保持向后兼容。
        """
        if not self.app_code:
            outcome = ProviderOutcome(
                ok=False,
                data=None,
                fetched_at=datetime.utcnow().isoformat() + "Z",
                attempts=0,
                degraded=True,
                error_code=PROVIDER_NOT_CONFIGURED,
                latency_ms=0,
                last_error="BID_APP_CODE 未配置",
            )
            self.record_outcome(outcome)
            return {
                "success": False,
                "error": "招投标API未配置，请设置 BID_APP_CODE 环境变量",
                "data": None,
                "degraded": True,
                "provider_code": outcome.error_code,
            }

        url = f"{self.BASE_URL}{self.ENDPOINTS['detail']}/{bid_id}"
        headers = {"Authorization": f"APPCODE {self.app_code}"}

        async def _call() -> Dict[str, Any]:
            assert self.app_code
            async with httpx.AsyncClient(timeout=DEFAULT_BIDDING_TIMEOUT_SECONDS, verify=False) as client:
                response = await client.get(url, headers=headers)

                if response.status_code == 403:
                    msg = response.headers.get("x-ca-error-message", "")
                    if "quota exhausted" in msg.lower():
                        raise PermissionError("API 调用配额已用尽")
                if response.status_code >= 500:
                    raise httpx.HTTPStatusError(
                        f"server {response.status_code}",
                        request=response.request,
                        response=response,
                    )
                # non-200 still carries a body that we want to surface as
                # a soft failure rather than a hard retry.
                try:
                    payload = response.json()
                except json.JSONDecodeError as exc:
                    raise json.JSONDecodeError(
                        f"non-JSON body status={response.status_code}",
                        response.text,
                        0,
                    ) from exc
                return payload

        outcome: ProviderOutcome = await run_provider_async(
            _call,
            timeout_seconds=DEFAULT_BIDDING_TIMEOUT_SECONDS,
            max_attempts=DEFAULT_BIDDING_MAX_ATTEMPTS,
            backoff_seconds=0.3,
        )
        self.record_outcome(outcome)

        if outcome.ok:
            data = outcome.data or {}
            if data.get("status") == "200":
                return {
                    "success": True,
                    "data": data.get("data", {}),
                    "message": data.get("message", ""),
                    "provider_code": outcome.error_code,
                }
            return self._degraded_payload(
                data.get("message", "查询失败"),
                outcome.error_code,
                data=None,
            )
        return self._degraded_payload(
            outcome.last_error or "API请求失败",
            outcome.error_code,
            data=None,
        )

    async def _search(
        self,
        endpoint: str,
        keyword: str,
        page: int = 1
    ) -> Dict[str, Any]:
        """
        内部搜索方法

        Args:
            endpoint: API端点
            keyword: 搜索关键词
            page: 页码

        Returns:
            搜索结果。失败路径返回带 ``degraded`` 与 ``provider_code`` 的
            字典，便于上层多源编排区分"零结果"和"采集失败"。
        """
        if not self.app_code:
            outcome = ProviderOutcome(
                ok=False,
                data=None,
                fetched_at=datetime.utcnow().isoformat() + "Z",
                attempts=0,
                degraded=True,
                error_code=PROVIDER_NOT_CONFIGURED,
                latency_ms=0,
                last_error="BID_APP_CODE 未配置",
            )
            self.record_outcome(outcome)
            return self._degraded_payload(
                "招投标API未配置，请设置 BID_APP_CODE 环境变量",
                outcome.error_code,
            )

        if not keyword:
            return self._degraded_payload("请提供搜索关键词", PROVIDER_NOT_CONFIGURED)

        # 构建URL: /endpoint/keyword/page
        url = f"{self.BASE_URL}{endpoint}/{keyword}/{page}"
        headers = {"Authorization": f"APPCODE {self.app_code}"}

        async def _call() -> Dict[str, Any]:
            assert self.app_code
            # 注意：该API的SSL证书与域名不匹配，需要跳过验证
            async with httpx.AsyncClient(timeout=DEFAULT_BIDDING_TIMEOUT_SECONDS, verify=False) as client:
                response = await client.get(url, headers=headers)

                if response.status_code == 403:
                    error_msg = response.headers.get("x-ca-error-message", "")
                    if "quota exhausted" in error_msg.lower():
                        raise PermissionError("API 调用配额已用尽")
                if response.status_code >= 500:
                    raise httpx.HTTPStatusError(
                        f"server {response.status_code}",
                        request=response.request,
                        response=response,
                    )
                try:
                    payload = response.json()
                except json.JSONDecodeError as exc:
                    raise json.JSONDecodeError(
                        f"non-JSON body status={response.status_code}",
                        response.text,
                        0,
                    ) from exc
                return payload

        outcome: ProviderOutcome = await run_provider_async(
            _call,
            timeout_seconds=DEFAULT_BIDDING_TIMEOUT_SECONDS,
            max_attempts=DEFAULT_BIDDING_MAX_ATTEMPTS,
            backoff_seconds=0.3,
        )
        self.record_outcome(outcome)

        if outcome.ok:
            data = outcome.data or {}
            if data.get("status") == "200":
                result_data = data.get("data", {}) if isinstance(data, dict) else {}
                items = result_data.get("list", []) if isinstance(result_data, dict) else []
                total = result_data.get("total", 0) if isinstance(result_data, dict) else 0
                if not isinstance(items, list):
                    items = []
                results = [BidInfo.from_dict(item).to_dict() for item in items]
                return {
                    "success": True,
                    "results": results,
                    "total": total,
                    "page": page,
                    "count": len(results),
                    "message": data.get("message", "") if isinstance(data, dict) else "",
                    "provider_code": outcome.error_code,
                }
            return self._degraded_payload(
                (data.get("message") if isinstance(data, dict) else None) or "查询失败",
                outcome.error_code,
            )

        # degraded paths
        extra: Dict[str, Any] = {}
        if outcome.error_code == PROVIDER_NOT_CONFIGURED:
            pass
        elif "quota" in (outcome.last_error or "").lower():
            extra["quota_exhausted"] = True
        return self._degraded_payload(
            outcome.last_error or "API请求失败",
            outcome.error_code,
            **extra,
        )

    def format_results(self, results: List[Dict]) -> str:
        """格式化搜索结果为可读文本"""
        if not results:
            return "未找到相关招投标信息"

        output = []
        for i, item in enumerate(results, 1):
            location = item.get("province", "")
            if item.get("city"):
                location += f" {item['city']}"

            output.append(f"""
{i}. {item.get('title', '无标题')}
   类型: {item.get('notice_type', '-')} | 地区: {location}
   发布时间: {item.get('publish_time', '-')}
""")

        return "\n".join(output)


# 单例
_bidding_service: Optional[BiddingService] = None


def get_bidding_service() -> BiddingService:
    """获取招投标服务单例"""
    global _bidding_service
    if _bidding_service is None:
        _bidding_service = BiddingService()
    return _bidding_service
