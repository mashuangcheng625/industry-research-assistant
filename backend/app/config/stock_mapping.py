"""
公司名称 -> 股票代码映射（已迁移至 ``core.data_governance.StockCodeResolver``）。

本模块保留作为公共 API 的 shim，向后兼容调用方。继续直接导入
``COMPANY_STOCK_MAP`` 的代码仍然可以工作（推荐改用
``get_stock_resolver().canonical_entities``）。后续若新增实体，调用
``get_stock_resolver().register(name, code)``；所有解析都会被记入
``audit_sink``（如果配置）以便排障。
"""
from typing import Dict, List, Optional, Tuple

from core.data_governance import (
    StockCodeResolver,
    find_company_in_query,
    get_stock_code,
)


_RESOLVER_SINGLETON: Optional[StockCodeResolver] = None


def get_stock_resolver() -> StockCodeResolver:
    """Return the process-wide :class:`StockCodeResolver` singleton."""

    global _RESOLVER_SINGLETON
    if _RESOLVER_SINGLETON is None:
        _RESOLVER_SINGLETON = StockCodeResolver()
    return _RESOLVER_SINGLETON


# Backwards-compatible alias for legacy callers that import the dict
# directly. New code should call ``get_stock_resolver().canonical_entities``
# so it sees runtime registrations as well.
def COMPANY_STOCK_MAP() -> Dict[str, str]:  # noqa: N802 - legacy name
    """Return a snapshot of the canonical entity -> stock-code map."""

    return dict(get_stock_resolver().canonical_entities)


__all__ = [
    "get_stock_code",
    "find_company_in_query",
    "get_stock_resolver",
    "COMPANY_STOCK_MAP",
]
