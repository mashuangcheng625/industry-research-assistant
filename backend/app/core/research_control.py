"""Research execution control primitives with no router dependency."""
from .redis_client import cache


CANCEL_KEY_PREFIX = "research:cancel:"


def request_research_cancel(session_id: str, expire: int = 300) -> bool:
    """Persist a cancellation request for a running research session."""
    return cache.set(
        f"{CANCEL_KEY_PREFIX}{session_id}",
        {"cancelled": True},
        expire=expire,
    )


def is_research_cancelled(session_id: str) -> bool:
    """Return whether cancellation has been requested."""
    result = cache.get(f"{CANCEL_KEY_PREFIX}{session_id}")
    return bool(result and result.get("cancelled"))


def clear_cancel_flag(session_id: str) -> bool:
    """Clear an old cancellation request before exposing a new start event."""
    return cache.delete(f"{CANCEL_KEY_PREFIX}{session_id}")
