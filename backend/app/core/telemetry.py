"""OpenTelemetry instrumentation (P1-13).

This module sets up a process-wide OpenTelemetry tracer and, when the
environment variable ``OTEL_ENABLED=true`` is set, instruments the
FastAPI application, HTTPX outbound calls, and SQLAlchemy queries.

The instrumentation is opt-in and entirely transparent when disabled:
no spans are created, no exporters are instantiated, and the import
cost is a single ``if`` check at FastAPI startup time.

By default traces are written to the console via
``ConsoleSpanExporter``. Set ``OTEL_EXPORTER_OTLP_ENDPOINT`` to route
them to a Jaeger / Grafana Tempo / Datadog endpoint instead.

Usage in ``app_main.py``::

    from core.telemetry import instrument_app
    instrument_app(app)

The function is idempotent — calling it multiple times against the
same app logs a warning on the second call and returns immediately.
"""

from __future__ import annotations

import logging
import os
from typing import Optional

logger = logging.getLogger("telemetry")

_INSTRUMENTED_APPS: set[int] = set()


def instrument_app(app) -> None:
    """Optionally instrument *app* with OpenTelemetry.

    Does nothing when ``OTEL_ENABLED`` is not truthy. Repeated calls
    against the same ``app`` object produce a warning and early return.
    """

    app_id = id(app)
    if app_id in _INSTRUMENTED_APPS:
        logger.warning("instrument_app called more than once for the same app; skipping.")
        return

    enabled = os.environ.get("OTEL_ENABLED", "").strip().lower()
    if enabled not in ("1", "true", "yes", "on"):
        return

    _INSTRUMENTED_APPS.add(app_id)
    _setup(app)


def _setup(app) -> None:
    import opentelemetry
    from opentelemetry import trace
    from opentelemetry.sdk.resources import SERVICE_NAME, Resource
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter
    from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

    service = os.environ.get("OTEL_SERVICE_NAME", "industry-research-assistant")
    resource = Resource.create({SERVICE_NAME: service})

    # Use OTLP if an endpoint is configured; otherwise fall back to
    # console so the developer always sees trace output.
    otlp_endpoint = os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT", "").strip()
    if otlp_endpoint:
        try:
            from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
            exporter = OTLPSpanExporter(endpoint=otlp_endpoint)
        except ImportError:  # pragma: no cover — otlp extra not installed
            logger.warning("OTLP exporter requested but otlp packages not installed; falling back to console.")
            exporter = ConsoleSpanExporter()
    else:
        exporter = ConsoleSpanExporter()

    provider = TracerProvider(resource=resource)
    provider.add_span_processor(BatchSpanProcessor(exporter))
    trace.set_tracer_provider(provider)

    # Instrument FastAPI
    FastAPIInstrumentor.instrument_app(app)

    # Instrument sqlalchemy (the engine is shared; we piggy-back on the
    # existing module-level engine import).
    try:
        from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
        from core.database import engine
        SQLAlchemyInstrumentor().instrument(engine=engine)
    except Exception as exc:  # noqa: BLE001
        logger.debug("sqlalchemy instrumentation skipped: %s", exc)

    # Instrument outbound httpx when possible.
    try:
        from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
        HTTPXClientInstrumentor().instrument()
    except Exception as exc:  # noqa: BLE001
        logger.debug("httpx instrumentation skipped: %s", exc)

    logger.info("OpenTelemetry tracing enabled — service=%s otlp=%s", service, bool(otlp_endpoint))


def get_tracer(name: str = __name__):
    """Return a no-op-compatible tracer.

    When OTel is not configured this returns a tracer whose ``start_span``
    returns a non-recording span, so callers never need branching logic.
    """

    from opentelemetry import trace
    return trace.get_tracer(name)


__all__ = ["instrument_app", "get_tracer"]
