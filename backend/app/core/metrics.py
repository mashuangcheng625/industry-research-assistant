"""Low-cardinality Prometheus metrics for the research execution path."""

from prometheus_client import Counter, Gauge, Histogram


RUNS = Counter(
    "industry_research_runs_total",
    "Research runs reaching a terminal observation outcome.",
    ("resume", "outcome"),
)
ACTIVE_RUNS = Gauge(
    "industry_research_active_runs",
    "Research SSE generators currently executing.",
)
RUN_DURATION = Histogram(
    "industry_research_run_duration_seconds",
    "End-to-end research generator duration.",
    ("resume", "outcome"),
    buckets=(1, 2.5, 5, 10, 20, 40, 80, 160, 320, 640),
)
PHASE_TRANSITIONS = Counter(
    "industry_research_phase_transitions_total",
    "Research phase events emitted by the state machine.",
    ("phase", "event"),
)
PHASE_DURATION = Histogram(
    "industry_research_phase_duration_seconds",
    "Time between emitted research phase transitions.",
    ("phase", "outcome"),
    buckets=(0.25, 0.5, 1, 2.5, 5, 10, 20, 40, 80, 160, 320),
)
AGENT_RUNS = Counter(
    "industry_research_agent_runs_total",
    "Agent process task outcomes.",
    ("agent", "outcome"),
)
AGENT_DURATION = Histogram(
    "industry_research_agent_duration_seconds",
    "Agent process task duration.",
    ("agent", "outcome"),
    buckets=(0.25, 0.5, 1, 2.5, 5, 10, 20, 40, 80, 160, 320),
)
AGENT_TIMEOUTS = Counter(
    "industry_research_agent_timeouts_total",
    "Agent tasks terminated by the graph-level timeout.",
    ("agent",),
)
LLM_CALLS = Counter(
    "industry_research_llm_calls_total",
    "Agent LLM call outcomes.",
    ("agent", "model", "outcome"),
)
LLM_DURATION = Histogram(
    "industry_research_llm_duration_seconds",
    "Agent LLM request duration as observed by the caller.",
    ("agent", "model", "outcome"),
    buckets=(0.25, 0.5, 1, 2.5, 5, 10, 20, 40, 80, 160),
)
LLM_TOKENS = Counter(
    "industry_research_llm_tokens_total",
    "Tokens reported by the OpenAI-compatible Agent endpoint.",
    ("agent", "model", "token_type"),
)
CHECKPOINT_OPERATIONS = Counter(
    "industry_research_checkpoint_operations_total",
    "Checkpoint persistence operations.",
    ("operation", "outcome"),
)
RUN_LOCK_OPERATIONS = Counter(
    "industry_research_run_lock_operations_total",
    "Cross-process research run-lock operations.",
    ("operation", "outcome"),
)
CANCEL_REQUESTS = Counter(
    "industry_research_cancel_requests_total",
    "Research cancellation API outcomes.",
    ("outcome",),
)
CANCELLATIONS = Counter(
    "industry_research_cancellations_total",
    "Cancellation events observed by the state machine.",
    ("phase",),
)
REVIEW_OUTCOMES = Counter(
    "industry_research_review_outcomes_total",
    "Terminal review outcomes.",
    ("status", "reason"),
)


def safe_phase(value: object) -> str:
    """Bound phase labels to the finite state-machine vocabulary."""
    phase = str(value or "unknown")
    allowed = {
        "init", "planning", "researching", "analyzing", "writing",
        "reviewing", "revising", "re_researching", "completed",
        "review_failed", "unknown",
    }
    return phase if phase in allowed else "unknown"


def safe_reason(value: object) -> str:
    """Bound review-reason labels; raw exception messages never become labels."""
    reason = str(value or "unknown")
    allowed = {
        "review_passed",
        "review_output_invalid",
        "max_iterations_with_unresolved_issues",
        "review_not_approved",
        "unknown",
    }
    return reason if reason in allowed else "unknown"
