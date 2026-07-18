"""文档 RAG 检索结果 → 统一 Evidence 适配器。

将 retrieval_service 或 Milvus 返回的检索结果块转换为 Evidence 对象。
"""

from __future__ import annotations

from typing import Any

from service.evidence_contract import Evidence


def adapt_document_chunk(chunk: dict[str, Any]) -> Evidence:
    """将单个 RAG 检索块转换为 Evidence 对象。

    预期输入字段（部分可选）:
        content / content_with_weight: 证据文本
        document_name / source: 文档名称
        doc_id / document_id: 文档标识
        chunk_index: 块编号
        page: 页码 (可选)
        score / weight: 检索得分 (可选，仅用于元数据)
        kb_name / selected_kb: 知识库名称 (可选)
        source_url / url: 原始 URL (可选)
    """
    content_text = str(
        chunk.get("content_with_weight") or chunk.get("content") or ""
    )
    doc_name = str(
        chunk.get("document_name") or chunk.get("source") or chunk.get("title") or "未知文档"
    )
    publisher = _infer_publisher(doc_name, chunk)

    locator: dict[str, Any] = {}
    if chunk.get("page") is not None:
        locator["page"] = int(chunk["page"])
    if chunk.get("chunk_index") is not None:
        locator["chunk_index"] = int(chunk["chunk_index"])
    if chunk.get("doc_id") or chunk.get("document_id"):
        locator["doc_id"] = chunk.get("doc_id") or chunk.get("document_id")
    if chunk.get("kb_name") or chunk.get("selected_kb"):
        locator["kb_name"] = chunk.get("kb_name") or chunk.get("selected_kb")

    url = chunk.get("source_url") or chunk.get("url")

    quality_tier = "official" if _is_standards_body(publisher) else "primary"

    return Evidence.create(
        source_kind="document",
        title=doc_name,
        publisher=publisher,
        content=content_text,
        url=url if isinstance(url, str) and url.startswith(("http", "local://")) else None,
        locator=locator,
        quality_tier=quality_tier,
        license_or_terms=_infer_license(doc_name, chunk),
    )


def adapt_document_chunks(chunks: list[dict[str, Any]]) -> list[Evidence]:
    """批量转换 RAG 检索结果。"""
    return [adapt_document_chunk(chunk) for chunk in chunks]


# ---- 内部辅助函数 ----


def _infer_publisher(doc_name: str, chunk: dict[str, Any]) -> str:
    """从文档名或元数据推断发布方。"""
    publisher = str(chunk.get("publisher") or chunk.get("source") or "")
    if not publisher:
        # 尝试从 URL 推断
        url = chunk.get("source_url") or chunk.get("url") or ""
        if "semicon" in url.lower() or "ieee" in url.lower():
            publisher = "SEMI / IEEE"
        elif "jedec" in url.lower():
            publisher = "JEDEC"
        elif "nist" in url.lower():
            publisher = "NIST"
        elif "gov.cn" in url:
            publisher = "中国政府"
        else:
            publisher = doc_name
    return publisher


_STANDARDS_DOMAINS = {
    "semiconductor", "semicon", "ieee", "jedec", "nist", "iso", "iec",
    "ansi", "astm", "sematech", "roadmap",
}


def _is_standards_body(publisher: str) -> bool:
    """判断是否属于标准组织/官方机构来源。"""
    pub_lower = publisher.lower()
    return any(domain in pub_lower for domain in _STANDARDS_DOMAINS)


def _infer_license(doc_name: str, chunk: dict[str, Any]) -> str:
    """从可用元数据推断许可状态。"""
    explicit = str(chunk.get("license") or chunk.get("license_or_terms") or "")
    if explicit:
        return explicit
    # 默认保守判断
    return "not_assessed"
