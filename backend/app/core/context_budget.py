"""Unified context budget enforcement (P1-15).

Before P1-15 the RAG pipeline only enforced a 6,000-token evidence
budget. System prompts, chat history, memory and output tokens were
not counted, meaning a long conversation or a verbose system prompt
could silently exceed the model's context window.

This module provides a single :class:`ContextBudget` calculator that
counts every token input the model sees — system prompt, user
question, chat history, embedded memories, evidence snippets, and
output tokens — and enforces a single global cap. The cap defaults to
32,768 tokens (a conservative value that fits in 32K-context models
with room for the LLM's internal overhead), and it can be overridden
via the ``CONTEXT_BUDGET_TOTAL_TOKENS`` environment variable.

All tokens are estimated using the tiktoken ``cl100k_base`` encoding
by default, which is a reasonable upper-bound proxy for Chinese/
English mixed prompts on the models used in this project
(deepseek-v4-*, qwen-*). Callers that need a more precise count can
pass their own encoding.

Usage::

    from core.context_budget import ContextBudget

    budget = ContextBudget()                # uses env or 32,768 default
    budget.add(system_prompt=1280, question=245, evidence=4100)
    assert budget.has_budget_for(500) is True   # output budget check
    print(budget.remaining)                     # tokens still available
    print(budget.summary())                     # dict for logs/metrics
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from typing import Callable, Dict, Optional

logger = logging.getLogger(__name__)

DEFAULT_TOTAL_TOKENS = 32_768
DEFAULT_ENCODING = "cl100k_base"

_encoding_cache: Dict[str, object] = {}


def _get_encoding(name: str):
    """Lazy-load a tiktoken encoding (cached per process)."""

    if name not in _encoding_cache:
        try:
            import tiktoken
            _encoding_cache[name] = tiktoken.get_encoding(name)
        except ImportError:
            logger.warning("tiktoken not installed — falling back to character-count estimate")
            _encoding_cache[name] = None
    return _encoding_cache[name]


def _estimate_tokens(text: str, encoding_name: str = DEFAULT_ENCODING) -> int:
    """Return a token-count estimate for ``text``.

    Uses tiktoken when available; falls back to ``len(text) // 3`` when
    the library is not installed (a rough heuristic for CJK+English
    mixed text where ~3 bytes per token is a common average).
    """

    if not text:
        return 0
    enc = _get_encoding(encoding_name)
    if enc is not None:
        try:
            return len(enc.encode(str(text)))
        except Exception:  # noqa: BLE001
            pass
    return max(1, len(str(text)) // 3)


@dataclass
class ContextBudget:
    """Track token usage across all input sources for a single request.

    Mutating methods return ``self`` so callers can chain::

        budget.add(system_prompt=x).add(question=y)
    """

    system_prompt_tokens: int = 0
    question_tokens: int = 0
    history_tokens: int = 0
    memory_tokens: int = 0
    evidence_tokens: int = 0
    output_tokens: int = 0

    total_cap: int = DEFAULT_TOTAL_TOKENS
    evidence_cap: int = 6_000  # legacy cap is preserved as a sub-budget

    @property
    def used(self) -> int:
        return (
            self.system_prompt_tokens
            + self.question_tokens
            + self.history_tokens
            + self.memory_tokens
            + self.evidence_tokens
        )

    @property
    def remaining(self) -> int:
        return max(0, self.total_cap - self.used)

    @property
    def remaining_output(self) -> int:
        return max(0, self.remaining - self.output_tokens)

    def add(self, **kw: int) -> "ContextBudget":
        """Add tokens to a named bucket. Unknown keys are ignored."""

        for name, tokens in kw.items():
            if not isinstance(tokens, int):
                continue
            if hasattr(self, name + "_tokens"):
                setattr(self, name + "_tokens", getattr(self, name + "_tokens") + tokens)
        return self

    def add_text(self, text: str, *, bucket: str) -> "ContextBudget":
        """Count and add the tokens in ``text`` to *bucket*.

        ``bucket`` must be one of ``system_prompt`` / ``question`` /
        ``history`` / ``memory`` / ``evidence`` / ``output``.
        """

        tokens = _estimate_tokens(text)
        return self.add(**{bucket: tokens})

    def has_budget_for(self, tokens: int) -> bool:
        """Return ``True`` when the remaining budget can absorb *tokens*."""

        return self.remaining >= tokens

    @staticmethod
    def from_texts(
        *,
        system_prompt: str = "",
        question: str = "",
        history: str = "",
        memory: str = "",
        evidence: str = "",
        total_cap: Optional[int] = None,
    ) -> "ContextBudget":
        """Factory that takes raw texts and returns a populated budget."""

        cap = total_cap or _env_total_cap()
        budget = ContextBudget(total_cap=cap)
        return (
            budget.add_text(system_prompt, bucket="system_prompt")
            .add_text(question, bucket="question")
            .add_text(history, bucket="history")
            .add_text(memory, bucket="memory")
            .add_text(evidence, bucket="evidence")
        )

    def summary(self) -> Dict[str, int]:
        """Return a dict suitable for logging and metrics."""

        return {
            "total_cap": self.total_cap,
            "used": self.used,
            "remaining": self.remaining,
            "system_prompt": self.system_prompt_tokens,
            "question": self.question_tokens,
            "history": self.history_tokens,
            "memory": self.memory_tokens,
            "evidence": self.evidence_tokens,
            "evidence_cap": self.evidence_cap,
            "evidence_over_cap": max(0, self.evidence_tokens - self.evidence_cap),
        }


def _env_total_cap() -> int:
    raw = os.environ.get("CONTEXT_BUDGET_TOTAL_TOKENS", str(DEFAULT_TOTAL_TOKENS)).strip()
    try:
        return max(1024, int(raw))
    except ValueError:
        logger.warning("CONTEXT_BUDGET_TOTAL_TOKENS=%r is not an integer; using %d", raw, DEFAULT_TOTAL_TOKENS)
        return DEFAULT_TOTAL_TOKENS


__all__ = ["ContextBudget", "DEFAULT_TOTAL_TOKENS"]
