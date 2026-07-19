"""股票资讯服务 - 聚合数据股票API

P1-2：所有外部 HTTP 调用通过 ``core.provider_reliability`` 包装，
统一提供超时 / 有限重试 / 失败降级与 ``ProviderOutcome``。失败路径
不再编造结果 —— 服务返回 ``{"success": False, "degraded": True,
"provider_code": "..."}`` 以便上层多源编排区分"零结果"与"采集失败"。
"""
import os
import json
import logging
import httpx
from datetime import datetime
from typing import Dict, Any, Optional, List
from dataclasses import dataclass
from enum import Enum

from core.provider_reliability import (
    PROVIDER_NOT_CONFIGURED,
    PROVIDER_OK,
    ProviderOutcome,
    run_provider_async,
)

logger = logging.getLogger(__name__)


DEFAULT_STOCK_TIMEOUT_SECONDS = float(
    os.getenv("STOCK_PROVIDER_TIMEOUT_SECONDS", "8")
)
DEFAULT_STOCK_MAX_ATTEMPTS = int(
    os.getenv("STOCK_PROVIDER_MAX_ATTEMPTS", "2")
)


class StockMarket(Enum):
    """股票市场"""
    SHANGHAI = "sh"  # 上海证券交易所
    SHENZHEN = "sz"  # 深圳证券交易所


@dataclass
class StockInfo:
    """股票信息"""
    gid: str  # 股票编号
    name: str  # 股票名称
    nowPri: str  # 当前价格
    increase: str  # 涨跌额
    increPer: str  # 涨跌幅
    todayStartPri: str  # 今日开盘价
    yestodEndPri: str  # 昨日收盘价
    todayMax: str  # 今日最高价
    todayMin: str  # 今日最低价
    traAmount: str  # 成交量
    traNumber: str  # 成交额

    @classmethod
    def from_dict(cls, data: Dict) -> "StockInfo":
        return cls(
            gid=data.get("gid", ""),
            name=data.get("name", ""),
            nowPri=data.get("nowPri", ""),
            increase=data.get("increase", ""),
            increPer=data.get("increPer", ""),
            todayStartPri=data.get("todayStartPri", ""),
            yestodEndPri=data.get("yestodEndPri", ""),
            todayMax=data.get("todayMax", ""),
            todayMin=data.get("todayMin", ""),
            traAmount=data.get("traAmount", ""),
            traNumber=data.get("traNumber", ""),
        )

    def to_dict(self) -> Dict:
        return {
            "gid": self.gid,
            "name": self.name,
            "nowPri": self.nowPri,
            "increase": self.increase,
            "increPer": self.increPer,
            "todayStartPri": self.todayStartPri,
            "yestodEndPri": self.yestodEndPri,
            "todayMax": self.todayMax,
            "todayMin": self.todayMin,
            "traAmount": self.traAmount,
            "traNumber": self.traNumber,
        }

    def format_display(self) -> str:
        """格式化显示"""
        return f"""
📈 {self.name} ({self.gid})
━━━━━━━━━━━━━━━━━━━━━━━━
当前价格: ¥{self.nowPri}
涨跌额: {self.increase} ({self.increPer})
今开: ¥{self.todayStartPri} | 昨收: ¥{self.yestodEndPri}
最高: ¥{self.todayMax} | 最低: ¥{self.todayMin}
成交量: {self.traAmount} | 成交额: ¥{self.traNumber}
"""


class StockService:
    """股票资讯服务"""

    # 聚合数据股票API
    BASE_URL = "http://web.juhe.cn/finance/stock/hs"
    SHANGHAI_ALL_URL = "http://web.juhe.cn/finance/stock/shall"
    SHENZHEN_ALL_URL = "http://web.juhe.cn/finance/stock/szall"

    def __init__(self):
        self.api_key = os.getenv("JUHE_STOCK_API_KEY", "")
        if not self.api_key:
            print("警告: JUHE_STOCK_API_KEY 环境变量未设置")

        # 最近一次外部调用的 ProviderOutcome；上层编排可通过
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
            "data": None,
            "stocks": [],
        }
        payload.update(extra)
        return payload

    async def get_stock_by_code(self, stock_code: str) -> Dict[str, Any]:
        """
        根据股票代码查询股票信息

        Args:
            stock_code: 股票代码，如 "sh601009" (上证) 或 "sz000001" (深证)
                       也可以不带前缀，如 "601009"，会自动判断市场

        Returns:
            包含股票信息的字典。失败路径返回带 ``degraded`` 与
            ``provider_code`` 的失败字典。
        """
        gid = self._normalize_stock_code(stock_code)

        if not self.api_key:
            outcome = ProviderOutcome(
                ok=False,
                data=None,
                fetched_at=datetime.utcnow().isoformat() + "Z",
                attempts=0,
                degraded=True,
                error_code=PROVIDER_NOT_CONFIGURED,
                latency_ms=0,
                last_error="JUHE_STOCK_API_KEY 未配置",
            )
            self.record_outcome(outcome)
            return self._degraded_payload(
                "股票API未配置，请设置 JUHE_STOCK_API_KEY 环境变量",
                outcome.error_code,
            )

        async def _call() -> Dict[str, Any]:
            assert self.api_key
            async with httpx.AsyncClient(timeout=DEFAULT_STOCK_TIMEOUT_SECONDS) as client:
                response = await client.get(
                    self.BASE_URL,
                    params={"gid": gid, "key": self.api_key},
                )
                response.raise_for_status()
                return response.json()

        outcome: ProviderOutcome = await run_provider_async(
            _call,
            timeout_seconds=DEFAULT_STOCK_TIMEOUT_SECONDS,
            max_attempts=DEFAULT_STOCK_MAX_ATTEMPTS,
            backoff_seconds=0.3,
        )
        self.record_outcome(outcome)

        if outcome.ok:
            data = outcome.data or {}
            if data.get("resultcode") == "200":
                result = data.get("result", []) or []
                if result:
                    stock_data = result[0].get("data", {}) if isinstance(result[0], dict) else {}
                    stock_info = StockInfo.from_dict(stock_data)
                    return {
                        "success": True,
                        "data": stock_info.to_dict(),
                        "display": stock_info.format_display(),
                        "provider_code": outcome.error_code,
                    }
            return self._degraded_payload(
                (data.get("reason") if isinstance(data, dict) else None) or "查询失败",
                outcome.error_code,
            )

        return self._degraded_payload(
            outcome.last_error or "请求失败",
            outcome.error_code,
        )

    async def search_stock(self, keyword: str) -> Dict[str, Any]:
        """
        搜索股票（暂时通过遍历方式，后续可接入搜索API）

        Args:
            keyword: 股票名称或代码关键词

        Returns:
            匹配的股票列表
        """
        # 如果看起来像股票代码，直接查询
        if keyword.isdigit() or keyword.startswith(("sh", "sz", "SH", "SZ")):
            result = await self.get_stock_by_code(keyword)
            if result["success"]:
                return {
                    "success": True,
                    "results": [result["data"]],
                    "count": 1
                }

        # 否则尝试按代码查询（兼容纯数字代码）
        for prefix in ["sh", "sz"]:
            if keyword.isdigit():
                result = await self.get_stock_by_code(f"{prefix}{keyword}")
                if result["success"]:
                    return {
                        "success": True,
                        "results": [result["data"]],
                        "count": 1
                    }

        return {
            "success": False,
            "error": "未找到匹配的股票，请提供准确的股票代码（如 sh601009 或 sz000001）",
            "results": []
        }

    async def get_market_stocks(self, market: str = "shanghai", page: int = 1) -> Dict[str, Any]:
        """
        获取市场股票列表

        Args:
            market: 市场类型，"shanghai" 或 "shenzhen"
            page: 页码

        Returns:
            股票列表。失败路径返回带 ``degraded`` 与 ``provider_code`` 的字典。
        """
        url = self.SHANGHAI_ALL_URL if market == "shanghai" else self.SHENZHEN_ALL_URL

        if not self.api_key:
            outcome = ProviderOutcome(
                ok=False,
                data=None,
                fetched_at=datetime.utcnow().isoformat() + "Z",
                attempts=0,
                degraded=True,
                error_code=PROVIDER_NOT_CONFIGURED,
                latency_ms=0,
                last_error="JUHE_STOCK_API_KEY 未配置",
            )
            self.record_outcome(outcome)
            return self._degraded_payload(
                "股票API未配置，请设置 JUHE_STOCK_API_KEY 环境变量",
                outcome.error_code,
                market=market,
                page=page,
            )

        async def _call() -> Dict[str, Any]:
            assert self.api_key
            async with httpx.AsyncClient(timeout=DEFAULT_STOCK_TIMEOUT_SECONDS) as client:
                response = await client.get(
                    url,
                    params={"key": self.api_key, "page": page},
                )
                response.raise_for_status()
                return response.json()

        outcome: ProviderOutcome = await run_provider_async(
            _call,
            timeout_seconds=DEFAULT_STOCK_TIMEOUT_SECONDS,
            max_attempts=DEFAULT_STOCK_MAX_ATTEMPTS,
            backoff_seconds=0.3,
        )
        self.record_outcome(outcome)

        if outcome.ok:
            data = outcome.data or {}
            if data.get("resultcode") == "200":
                result = data.get("result", {}) if isinstance(data, dict) else {}
                stocks = result.get("data", []) if isinstance(result, dict) else []
                return {
                    "success": True,
                    "market": market,
                    "page": page,
                    "total_count": result.get("totalCount", 0) if isinstance(result, dict) else 0,
                    "stocks": [
                        StockInfo.from_dict(s.get("data", {}) if isinstance(s, dict) else {}).to_dict()
                        for s in stocks[:20]
                    ],
                    "provider_code": outcome.error_code,
                }
            return self._degraded_payload(
                (data.get("reason") if isinstance(data, dict) else None) or "查询失败",
                outcome.error_code,
                market=market,
                page=page,
            )

        return self._degraded_payload(
            outcome.last_error or "请求失败",
            outcome.error_code,
            market=market,
            page=page,
        )

    def _normalize_stock_code(self, code: str) -> str:
        """
        标准化股票代码

        Args:
            code: 原始股票代码

        Returns:
            标准化后的代码（如 sh601009）
        """
        code = code.strip().lower()

        # 如果已经有市场前缀
        if code.startswith(("sh", "sz")):
            return code

        # 根据股票代码判断市场
        if code.isdigit():
            # 6开头是上海，0/3开头是深圳
            if code.startswith("6"):
                return f"sh{code}"
            elif code.startswith(("0", "3")):
                return f"sz{code}"

        # 默认返回原始代码
        return code


# 单例
_stock_service: Optional[StockService] = None


def get_stock_service() -> StockService:
    """获取股票服务单例"""
    global _stock_service
    if _stock_service is None:
        _stock_service = StockService()
    return _stock_service
