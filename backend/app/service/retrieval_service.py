"""
知识库检索服务 - 基于 Milvus

功能：
1. retrieve_content - 从指定集合检索内容
2. retrieve_from_knowledge_base - 从知识库检索内容
"""

import os
import re
from typing import List, Dict, Any, Optional
from service.milvus_service import get_milvus_service
from service.embedding_service import generate_embedding


ASCII_TOKEN_PATTERN = re.compile(r"[a-z0-9]+(?:[._/-][a-z0-9]+)*", re.IGNORECASE)
CHINESE_RUN_PATTERN = re.compile(r"[\u4e00-\u9fff]+")

# 公开半导体语料以英文为主，用小型、可审计的领域词表弥合中文问题与
# 英文原文之间的表达差异。这些词只用于检索改写，不会被当作回答事实。
DOMAIN_QUERY_GLOSSARY = (
    ("命令行", "command line"),
    ("覆盖默认值", "command line;environment variable"),
    ("默认值", "default value"),
    ("时序报告", "timing report"),
    ("布线问题", "DRC Viewer;detailed routing"),
    ("检查布局", "heat map"),
    ("时序", "timing report"),
    ("时钟周期", "clock period"),
    ("时钟树", "clock tree synthesis"),
    ("布图规划", "floorplan"),
    ("详细布线", "detailed routing"),
    ("全局布线", "global routing"),
    ("地址匹配", "Address Matching"),
    ("锁定机制", "Locking;Privilege Mode"),
    ("锁定", "Locking"),
    ("供应链", "supply chain"),
    ("地理集中", "geographic concentration"),
    ("基础设施", "infrastructure"),
    ("运营能力", "workforce;cybersecurity"),
    ("人才", "workforce"),
    ("劳动力", "workforce"),
    ("网络安全", "cybersecurity"),
    ("运营安全", "operational security"),
    ("安全能力", "cybersecurity;operational security"),
    ("参考材料", "reference materials"),
    ("材料纯度", "material purity"),
    ("纯度", "purity"),
    ("颗粒", "particles"),
    ("痕量杂质", "trace impurities"),
    ("供应商", "suppliers"),
    ("可追溯", "traceability;provenance"),
    ("计量", "metrology"),
    ("内部缺陷", "internal defects;voids"),
    ("缺陷", "defects"),
    ("污染物", "contaminants"),
    ("材料性能", "material properties"),
    ("在线计量", "in-line metrology"),
    ("在线量测", "in-line metrology"),
    ("吞吐量", "throughput"),
    ("灵敏度", "sensitivity"),
    ("准确度", "accuracy"),
    ("建模", "modeling"),
    ("仿真", "simulation"),
    ("验证", "validation"),
    ("反馈", "feedback"),
    ("高吞吐量", "high-throughput"),
    ("过程控制", "process control"),
    ("质量保证", "quality assurance"),
    ("互操作", "interoperable equipment and software"),
    ("数据交换", "data exchange"),
    ("制造自动化", "manufacturing automation"),
    ("三维", "3D structures"),
    ("界面", "interfaces"),
    ("低翘曲", "low warpage"),
    ("翘曲", "warpage"),
    ("供电", "power delivery"),
    ("热管理", "thermal management"),
    ("空洞", "voids"),
    ("应力", "stresses"),
    ("粘附", "adhesion"),
    ("内建测试", "built-in test"),
    ("保护芯片", "mechanically;thermally;environmentally"),
    ("连接系统", "inter-chip communication;power delivery"),
    ("芯片间通信", "inter-chip communication"),
    ("机械", "mechanically"),
    ("装配", "assembly"),
)


def _is_enabled(value: str) -> bool:
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _lexical_tokens(text: str) -> set[str]:
    """提取英文/数字术语和中文双字词，无需额外分词依赖。"""
    normalized = text.casefold()
    tokens = set(ASCII_TOKEN_PATTERN.findall(normalized))
    for run in CHINESE_RUN_PATTERN.findall(normalized):
        if len(run) == 1:
            tokens.add(run)
        else:
            tokens.update(run[index:index + 2] for index in range(len(run) - 1))
    return tokens


def _lexical_score(question: str, content: str) -> float:
    """使用查询术语覆盖率计算 0-1 关键词相关度。"""
    query_tokens = _lexical_tokens(question)
    if not query_tokens:
        return 0.0
    content_tokens = _lexical_tokens(content)
    return len(query_tokens & content_tokens) / len(query_tokens)


def _technical_exact_score(question: str, content: str) -> Optional[float]:
    """计算查询中标识符/缩写的精确覆盖率；普通自然语言查询返回 None。"""
    raw_terms = ASCII_TOKEN_PATTERN.findall(question)
    technical_terms = {
        term.casefold()
        for term in raw_terms
        if "_" in term or (
            len(term) >= 2
            and any(character.isalpha() for character in term)
            and term.upper() == term
        )
    }
    if not technical_terms:
        return None
    normalized_content = content.casefold()
    matched = sum(term in normalized_content for term in technical_terms)
    return matched / len(technical_terms)


def _strict_identifier_score(question: str, content: str) -> Optional[float]:
    """计算 QFAB-X99 这类含分隔符和数字的型号精确覆盖率。"""
    identifiers = {
        term.casefold()
        for term in ASCII_TOKEN_PATTERN.findall(question)
        if term[0].isalpha()
        if any(character.isdigit() for character in term)
        and any(separator in term for separator in ("_", "-", "/"))
    }
    if not identifiers:
        return None
    normalized_content = content.casefold()
    matched = sum(term in normalized_content for term in identifiers)
    return matched / len(identifiers)


def _passes_strict_identifier_gate(identifier_score: Optional[float]) -> bool:
    """仅对具体型号做硬过滤，普通技术缩写仍只参与排序。"""
    if not _is_enabled(os.getenv("RAG_REQUIRE_ANY_STRICT_IDENTIFIER", "true")):
        return True
    return identifier_score is None or identifier_score > 0


def _matched_query_expansions(question: str) -> List[str]:
    """返回命中的英文领域词，并消除“低翘曲/翘曲”这类重叠命中。"""
    normalized = question.casefold()
    expansions: List[str] = []
    matched_chinese: List[str] = []
    for chinese, english in DOMAIN_QUERY_GLOSSARY:
        folded_chinese = chinese.casefold()
        if folded_chinese not in normalized:
            continue
        if any(folded_chinese in longer for longer in matched_chinese):
            continue
        matched_chinese.append(folded_chinese)
        for value in (part.strip() for part in english.split(";")):
            if value and value.casefold() not in {
                existing.casefold() for existing in expansions
            }:
                expansions.append(value)
    return expansions


def _build_query_plan(
    question: str,
    limit: Optional[int] = None,
) -> List[tuple[str, List[str]]]:
    """返回（查询文本，该查询要覆盖的精确概念）。"""
    effective_limit = limit if limit is not None else int(
        os.getenv("RAG_MULTI_QUERY_LIMIT", "6")
    )
    effective_limit = max(1, effective_limit)
    expansions = _matched_query_expansions(question)
    plan: List[tuple[str, List[str]]] = [(question.strip(), [])]
    strong_ascii_anchor = any(
        "_" in token
        or "-" in token
        or (len(token) >= 2 and token.upper() == token)
        for token in ASCII_TOKEN_PATTERN.findall(question)
    )
    if (
        not expansions
        or (len(expansions) < 2 and not strong_ascii_anchor)
        or effective_limit == 1
    ):
        return plan

    # 英文原问中的产品/标准名是很好的子查询锚点；若没有，保留枚举前的
    # 中文主题。子查询不再携带整句问话，避免精确术语被宽泛语义稀释。
    ascii_anchor = " ".join(dict.fromkeys(
        token
        for token in ASCII_TOKEN_PATTERN.findall(question)
        if len(token) >= 2
    ))
    chinese_anchor = re.split(r"[，,;；、]", question, maxsplit=1)[0].strip()
    anchor = ascii_anchor or chinese_anchor
    available_facet_slots = max(1, effective_limit - 1)
    group_count = min(available_facet_slots, len(expansions))
    base_size, larger_groups = divmod(len(expansions), group_count)
    groups: List[List[str]] = []
    cursor = 0
    for group_index in range(group_count):
        size = base_size + (1 if group_index < larger_groups else 0)
        groups.append(expansions[cursor:cursor + size])
        cursor += size
    for group in groups:
        plan.append((f"{anchor} {' '.join(group)}".strip(), group))

    # 只有概念少于子查询席位时，才用剩余席位加入完整扩展查询。
    # 否则优先保证每个概念有独立召回通道。
    if len(plan) < effective_limit:
        plan.append((
            f"{question.strip()} Technical terms: {'; '.join(expansions)}",
            expansions,
        ))

    deduplicated: List[tuple[str, List[str]]] = []
    seen = set()
    for variant, focus_terms in plan:
        folded = variant.casefold()
        if folded and folded not in seen:
            deduplicated.append((variant, focus_terms))
            seen.add(folded)
    return deduplicated[:effective_limit]


def _build_query_variants(question: str, limit: Optional[int] = None) -> List[str]:
    """生成可重现的多路检索查询。

    保留原问题，再使用命中的领域词表生成一个完整扩展查询和最多两个
    子主题查询。不调用 LLM，因此没有额外幻觉、成本或不可复现性。
    """
    return [variant for variant, _ in _build_query_plan(question, limit)]


def _focus_term_score(focus_terms: List[str], content: str) -> float:
    """计算人工可审计扩展词在证据块中的短语覆盖率。"""
    if not focus_terms:
        return 0.0
    normalized_content = re.sub(r"\s+", " ", content).casefold()
    return sum(
        re.sub(r"\s+", " ", term).casefold() in normalized_content
        for term in focus_terms
    ) / len(focus_terms)


def _expand_with_neighbor_chunks(
    seeds: List[Dict[str, Any]],
    available_chunks: List[Dict[str, Any]],
    window: int = 1,
    max_neighbors: int = 4,
) -> List[Dict[str, Any]]:
    """为高相关切片补同文档邻居，保留原始排序并严格隔离文档。"""
    if window <= 0 or max_neighbors <= 0 or not seeds:
        return seeds

    by_position = {
        (chunk.get("doc_id"), int(chunk.get("chunk_index", -1))): chunk
        for chunk in available_chunks
        if chunk.get("doc_id") is not None and chunk.get("chunk_index") is not None
    }
    seen_ids = {seed.get("id") for seed in seeds}
    neighbors: List[Dict[str, Any]] = []
    for seed in seeds:
        doc_id = seed.get("doc_id")
        chunk_index = seed.get("chunk_index")
        if doc_id is None or chunk_index is None:
            continue
        for offset in range(1, window + 1):
            for neighbor_index in (int(chunk_index) - offset, int(chunk_index) + offset):
                neighbor = by_position.get((doc_id, neighbor_index))
                if not neighbor or neighbor.get("id") in seen_ids:
                    continue
                neighbors.append({
                    **neighbor,
                    "score": float(seed.get("score", 0)) * 0.95,
                    "vector_score": float(neighbor.get("vector_score", 0)),
                    "lexical_score": float(neighbor.get("lexical_score", 0)),
                    "is_neighbor": True,
                    "neighbor_of": seed.get("id"),
                })
                seen_ids.add(neighbor.get("id"))
                if len(neighbors) >= max_neighbors:
                    return seeds + neighbors
    return seeds + neighbors


def _select_facet_diverse_results(
    results: List[Dict[str, Any]],
    query_count: int,
    top_k: int,
    max_chunks_per_document: int = 3,
) -> List[Dict[str, Any]]:
    """为每个子查询保留一个高相关证据席位，然后按总分补齐。"""
    if not results or top_k <= 0:
        return []

    selected: List[Dict[str, Any]] = []
    selected_ids = set()
    per_document: Dict[str, int] = {}

    def add(result: Dict[str, Any]) -> bool:
        result_id = result.get("id")
        doc_id = result.get("doc_id", "")
        if result_id in selected_ids:
            return False
        if per_document.get(doc_id, 0) >= max_chunks_per_document:
            return False
        selected.append(result)
        selected_ids.add(result_id)
        per_document[doc_id] = per_document.get(doc_id, 0) + 1
        return True

    if query_count > 1:
        for query_index in range(query_count):
            ranked = sorted(
                results,
                key=lambda item: (
                    item.get("query_relevance_scores", [0.0] * query_count)[query_index]
                    if query_index < len(item.get("query_relevance_scores", []))
                    else 0.0
                ),
                reverse=True,
            )
            for result in ranked:
                scores = result.get("query_relevance_scores", [])
                relevance = scores[query_index] if query_index < len(scores) else 0.0
                if relevance <= 0:
                    break
                if add(result):
                    break
            if len(selected) >= top_k:
                return selected[:top_k]

    for result in results:
        if len(selected) >= top_k:
            break
        add(result)
    return selected[:top_k]


def retrieve_content(
    indexNames: str,
    question: str,
    top_k: int = 5,
    kb_id: Optional[str] = None,
    min_score: Optional[float] = None,
) -> List[Dict[str, Any]]:
    """
    检索相关内容

    Args:
        indexNames: 集合名称（知识库索引）
        question: 查询问题
        top_k: 返回结果数量
        kb_id: 知识库ID（可选过滤）

    Returns:
        检索结果列表
    """
    try:
        # 1. 生成原问题和领域子查询的向量。批量调用只产生一次 HTTP 往返。
        multi_query_enabled = _is_enabled(os.getenv("RAG_MULTI_QUERY_ENABLED", "true"))
        query_plan = (
            _build_query_plan(question)
            if multi_query_enabled
            else [(question, [])]
        )
        query_variants = [variant for variant, _ in query_plan]
        query_focus_terms = [focus_terms for _, focus_terms in query_plan]
        query_vectors = generate_embedding(query_variants)
        if not query_vectors or len(query_vectors) == 0:
            print("生成查询向量失败")
            return []

        # 2. 执行向量搜索；混合模式使用更大的候选集。
        milvus = get_milvus_service()
        hybrid_enabled = _is_enabled(os.getenv("RAG_HYBRID_ENABLED", "false"))
        candidate_k = max(top_k * 4, 20) if hybrid_enabled else top_k
        vector_results_by_id: Dict[str, Dict[str, Any]] = {}
        for query_index, query_vector in enumerate(query_vectors):
            query_results = milvus.search(
                collection_name=indexNames,
                query_vector=query_vector,
                top_k=candidate_k,
                kb_id=kb_id,
            )
            for rank, result in enumerate(query_results, start=1):
                chunk_id = result.get("id")
                if not chunk_id:
                    continue
                existing = vector_results_by_id.get(chunk_id, {})
                vector_scores = dict(existing.get("query_vector_scores", {}))
                vector_scores[query_index] = float(result.get("score", 0))
                best_score = max(
                    float(existing.get("score", 0)),
                    float(result.get("score", 0)),
                )
                vector_results_by_id[chunk_id] = {
                    **existing,
                    **result,
                    "score": best_score,
                    "query_vector_scores": vector_scores,
                    "rrf_score": float(existing.get("rrf_score", 0))
                    + 1.0 / (60 + rank),
                }
        vector_results = list(vector_results_by_id.values())

        if hybrid_enabled:
            scan_limit = int(os.getenv("RAG_LEXICAL_SCAN_LIMIT", "10000"))
            all_chunks = milvus.list_chunks(indexNames, limit=scan_limit)
            merged_results: Dict[str, Dict[str, Any]] = {}

            for chunk in all_chunks:
                chunk_id = chunk.get("id")
                if not chunk_id:
                    continue
                query_lexical_scores = [
                    _lexical_score(variant, chunk.get("content", ""))
                    for variant in query_variants
                ]
                query_focus_scores = [
                    _focus_term_score(focus_terms, chunk.get("content", ""))
                    for focus_terms in query_focus_terms
                ]
                merged_results[chunk_id] = {
                    **chunk,
                    "vector_score": 0.0,
                    "query_vector_scores": {},
                    "rrf_score": 0.0,
                    "query_lexical_scores": query_lexical_scores,
                    "query_focus_scores": query_focus_scores,
                    "lexical_score": max(query_lexical_scores, default=0.0),
                    "exact_term_score": _technical_exact_score(
                        question,
                        chunk.get("content", ""),
                    ),
                    "strict_identifier_score": _strict_identifier_score(
                        question,
                        chunk.get("content", ""),
                    ),
                }

            for result in vector_results:
                chunk_id = result.get("id")
                if not chunk_id:
                    continue
                existing = merged_results.get(chunk_id, {})
                merged_results[chunk_id] = {
                    **result,
                    "lexical_score": existing.get(
                        "lexical_score",
                        _lexical_score(question, result.get("content", "")),
                    ),
                    "exact_term_score": existing.get(
                        "exact_term_score",
                        _technical_exact_score(question, result.get("content", "")),
                    ),
                    "strict_identifier_score": existing.get(
                        "strict_identifier_score",
                        _strict_identifier_score(question, result.get("content", "")),
                    ),
                    "vector_score": float(result.get("score", 0)),
                    "query_vector_scores": result.get("query_vector_scores", {}),
                    "rrf_score": result.get("rrf_score", 0.0),
                    "query_lexical_scores": existing.get("query_lexical_scores", []),
                    "query_focus_scores": existing.get("query_focus_scores", []),
                }

            vector_weight = float(os.getenv("RAG_VECTOR_WEIGHT", "0.75"))
            lexical_weight = float(os.getenv("RAG_LEXICAL_WEIGHT", "0.25"))
            results = []
            for result in merged_results.values():
                query_vector_scores = result.get("query_vector_scores", {})
                query_lexical_scores = result.get("query_lexical_scores", [])
                query_focus_scores = result.get("query_focus_scores", [])
                focus_weight = min(
                    0.80,
                    max(0.0, float(os.getenv("RAG_QUERY_FOCUS_WEIGHT", "0.55"))),
                )
                result["query_relevance_scores"] = [
                    (
                        vector_weight * float(query_vector_scores.get(index, 0))
                        + lexical_weight * float(
                            query_lexical_scores[index]
                            if index < len(query_lexical_scores)
                            else 0
                        )
                        if not query_focus_terms[index]
                        else (
                            (1 - focus_weight) * (
                                vector_weight * float(query_vector_scores.get(index, 0))
                                + lexical_weight * float(
                                    query_lexical_scores[index]
                                    if index < len(query_lexical_scores)
                                    else 0
                                )
                            )
                            + focus_weight * float(
                                query_focus_scores[index]
                                if index < len(query_focus_scores)
                                else 0
                            )
                        )
                    )
                    for index in range(len(query_variants))
                ]
                base_score = (
                    vector_weight * float(result.get("vector_score", 0))
                    + lexical_weight * float(result.get("lexical_score", 0))
                )
                exact_term_score = result.get("exact_term_score")
                if exact_term_score is None:
                    result["score"] = base_score
                else:
                    exact_weight = min(
                        0.5,
                        max(0.0, float(os.getenv("RAG_EXACT_TERM_WEIGHT", "0.20"))),
                    )
                    result["score"] = (
                        (1 - exact_weight) * base_score
                        + exact_weight * float(exact_term_score)
                    )
                results.append(result)
        else:
            results = [
                {
                    **result,
                    "vector_score": float(result.get("score", 0)),
                    "lexical_score": 0.0,
                    "query_lexical_scores": [],
                    "query_relevance_scores": [
                        float(result.get("query_vector_scores", {}).get(index, 0))
                        for index in range(len(query_variants))
                    ],
                }
                for result in vector_results
            ]

        # 2.1 文档级覆盖度：复合问题的多个子查询若都指向同一文档，
        # 该文档应在切片精排时获得小幅加权。
        lexical_hit_threshold = float(os.getenv("RAG_QUERY_FACET_LEXICAL_SCORE", "0.20"))
        document_query_hits: Dict[str, set[int]] = {}
        for result in results:
            hits = set(int(index) for index in result.get("query_vector_scores", {}))
            hits.update(
                index
                for index, score in enumerate(result.get("query_lexical_scores", []))
                if float(score) >= lexical_hit_threshold
            )
            result["query_hits"] = hits
            document_query_hits.setdefault(result.get("doc_id", ""), set()).update(hits)

        coverage_weight = min(
            0.30,
            max(0.0, float(os.getenv("RAG_DOCUMENT_COVERAGE_WEIGHT", "0.12"))),
        )
        for result in results:
            coverage = len(document_query_hits.get(result.get("doc_id", ""), set())) / max(
                1,
                len(query_variants),
            )
            result["document_coverage_score"] = coverage
            if len(query_variants) > 1:
                result["score"] = (
                    (1 - coverage_weight) * float(result.get("score", 0))
                    + coverage_weight * coverage
                )
        results.sort(key=lambda item: item.get("score", 0), reverse=True)

        # 3. 过滤低相关度结果。默认值可由环境变量调整；
        # 显式传入 min_score 时优先使用调用方的值。
        effective_min_score = (
            min_score
            if min_score is not None
            else float(os.getenv("RAG_MIN_SCORE", "0"))
        )
        effective_min_lexical_score = float(os.getenv("RAG_MIN_LEXICAL_SCORE", "0.18"))
        # 按文档做准入，而不是逐切片硬截断：只要某文档至少一个
        # 切片达到阈值，就保留该文档本次 Top-K 中的其他证据切片。
        # 这可以避免将同一证据链的后半段因轻微分数差异误删。
        admitted_document_ids = {
            result.get("doc_id")
            for result in results
            if (
                _passes_strict_identifier_gate(result.get("strict_identifier_score"))
                and (
                    float(result.get("vector_score", result.get("score", 0))) >= effective_min_score
                    or (
                        hybrid_enabled
                        and float(result.get("lexical_score", 0)) >= effective_min_lexical_score
                    )
                )
            )
        }
        admitted_results = [
            result for result in results
            if result.get("doc_id") in admitted_document_ids
        ]

        # 复合查询优先覆盖各子问题；单查询仍按总分排序。单文档上限
        # 避免一部长规范占满 Top-K，但允许复合问题从同一规范取多段证据。
        # top_k=3 时，原问题会吃掉一个席位，4个facet中的后两个此前永远
        # 无法入选。复合问题可使用少量额外核心席位，单查询仍严格遵守 top_k。
        extra_facet_results = max(
            0, int(os.getenv("RAG_MULTI_QUERY_EXTRA_RESULTS", "3"))
        )
        selection_limit = top_k
        if len(query_variants) > 1:
            selection_limit = min(
                len(query_variants),
                top_k + extra_facet_results,
            )
        filtered_results = _select_facet_diverse_results(
            admitted_results,
            query_count=len(query_variants),
            top_k=selection_limit,
            max_chunks_per_document=max(
                min(len(query_variants), selection_limit),
                int(os.getenv("RAG_MAX_CHUNKS_PER_DOCUMENT", "3")),
            ),
        )

        if _is_enabled(os.getenv("RAG_NEIGHBOR_ENABLED", "true")) and filtered_results:
            neighbor_window = max(0, int(os.getenv("RAG_NEIGHBOR_WINDOW", "1")))
            max_neighbors = max(0, int(os.getenv("RAG_MAX_NEIGHBOR_CHUNKS", "4")))
            # 复合查询以 top_k+2 为目标总预算；facet核心证据优先，只有
            # 未填满预算时才补邻居。单查询仍保留原邻居配置。
            if len(query_variants) > 1:
                total_extra = max(
                    0, int(os.getenv("RAG_MULTI_QUERY_TOTAL_EXTRA_RESULTS", "2"))
                )
                max_neighbors = min(
                    max_neighbors,
                    max(0, top_k + total_extra - len(filtered_results)),
                )
            if hybrid_enabled:
                neighbor_pool = all_chunks
            else:
                neighbor_pool = []
                for seed in filtered_results:
                    index = int(seed.get("chunk_index", -1))
                    requested = [
                        index + offset
                        for offset in range(-neighbor_window, neighbor_window + 1)
                        if offset and index + offset >= 0
                    ]
                    neighbor_pool.extend(milvus.get_neighbor_chunks(
                        indexNames,
                        seed.get("doc_id", ""),
                        requested,
                        limit=len(requested),
                    ))
            filtered_results = _expand_with_neighbor_chunks(
                filtered_results,
                neighbor_pool,
                window=neighbor_window,
                max_neighbors=max_neighbors,
            )

        # 4. 格式化结果
        extracted_data = []
        for i, result in enumerate(filtered_results, start=1):
            message = {
                "id": i,
                "document_id": result.get("doc_id", "N/A"),
                "document_name": result.get("filename", "N/A"),
                "content_with_weight": result.get("content", ""),
                "score": result.get("score", 0),
                "vector_score": result.get("vector_score", result.get("score", 0)),
                "lexical_score": result.get("lexical_score", 0),
                "exact_term_score": result.get("exact_term_score"),
                "strict_identifier_score": result.get("strict_identifier_score"),
                "chunk_index": result.get("chunk_index"),
                "is_neighbor": result.get("is_neighbor", False),
                "neighbor_of": result.get("neighbor_of"),
                "query_hit_count": len(result.get("query_hits", set())),
                "document_coverage_score": result.get("document_coverage_score", 0.0),
                "query_variant_count": len(query_variants),
            }
            extracted_data.append(message)

        return extracted_data

    except Exception as e:
        print(f"检索错误: {str(e)}")
        import traceback
        traceback.print_exc()
        return []


def retrieve_from_knowledge_base(
    kb_name: str,
    question: str,
    top_k: int = 5,
    min_score: Optional[float] = None,
) -> List[Dict[str, Any]]:
    """
    从知识库检索内容

    Args:
        kb_name: 知识库名称
        question: 查询问题
        top_k: 返回结果数量

    Returns:
        检索结果列表
    """
    # 将知识库名称转换为集合名称
    collection_name = f"kb_{kb_name}".lower().replace(" ", "_")
    return retrieve_content(
        collection_name,
        question,
        top_k,
        min_score=min_score,
    )
