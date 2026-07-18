"""Bailian qwen3-rerank client shared by retrieval and chat paths."""

from __future__ import annotations

import os
from typing import Sequence

from openai import OpenAI


def rerank_scores(
    query: str,
    documents: Sequence[str],
    fallback_scores: Sequence[float] | None = None,
) -> list[float]:
    """Return scores in original document order, preserving fallbacks on failure."""
    fallbacks = (
        [float(score) for score in fallback_scores]
        if fallback_scores is not None
        else [0.0] * len(documents)
    )
    if len(fallbacks) != len(documents):
        raise ValueError("fallback_scores 与 documents 数量不一致")
    if not documents:
        return []
    if os.getenv("RERANK_ENABLED", "false").lower() not in {"1", "true", "yes", "on"}:
        return fallbacks

    api_key = (
        os.getenv("RERANK_API_KEY")
        or os.getenv("DASHSCOPE_API_KEY")
        or os.getenv("EMBEDDING_API_KEY")
    )
    if not api_key:
        return fallbacks

    try:
        max_chars = max(1, int(os.getenv("RERANK_MAX_DOCUMENT_CHARS", "12000")))
        texts = [str(document)[:max_chars] for document in documents]
        client = OpenAI(
            api_key=api_key,
            base_url=os.getenv(
                "RERANK_BASE_URL",
                "https://dashscope.aliyuncs.com/compatible-api/v1",
            ),
            timeout=float(os.getenv("RERANK_TIMEOUT_SECONDS", "30")),
        )
        response = client.post(
            "/reranks",
            body={
                "model": os.getenv("RERANK_MODEL", "qwen3-rerank"),
                "query": query,
                "documents": texts,
                "top_n": len(texts),
                "instruct": os.getenv(
                    "RERANK_INSTRUCT",
                    "Given a web search query, retrieve relevant passages that answer the query.",
                ),
            },
            cast_to=object,
        )
        payload = response if isinstance(response, dict) else response.model_dump()
        results = payload.get("results")
        if not isinstance(results, list):
            return fallbacks

        scores = list(fallbacks)
        for result in results:
            index = int(result["index"])
            score = float(result["relevance_score"])
            if 0 <= index < len(scores):
                scores[index] = max(0.0, min(1.0, score))
        return scores
    except Exception as exc:
        print(f"Rerank request failed, using fallback scores: {type(exc).__name__}")
        return fallbacks
