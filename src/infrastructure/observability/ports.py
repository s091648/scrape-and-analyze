"""
Observability ports — abstract interfaces that any backend must satisfy.

Callers (domain, application, ingestion) import from here or from
src.utils.logging / src.infrastructure.observability.*.
Concrete implementations (OTel, Loki, structlog) live alongside this file.

Usage pattern:
    # Current code uses OTel directly — this is fine because OTel IS the
    # standard interface for metrics/tracing.  These Protocols formalise that
    # contract so future backends (Datadog, Prometheus, no-op) can be
    # dropped in without touching domain code.

Swapping a backend:
    1. Implement the relevant Protocol.
    2. Replace the module-level globals in otel_metrics.py / otel_tracing.py.
    3. No change needed in scrapers, use cases, or parsers.
"""
from contextlib import contextmanager
from typing import Any, Dict, Generator, Optional, runtime_checkable
from typing_extensions import Protocol


# ── Logger ────────────────────────────────────────────────────────────────────

class LoggerPort(Protocol):
    """
    Structured logger interface (satisfied by structlog BoundLogger).

    Note: structlog uses a lazy proxy before configure_logging() is called,
    so runtime isinstance() checks are unreliable.  Use this Protocol for
    static type hints (mypy/pyright) only.
    """

    def info(self, event: str, **kwargs: Any) -> None: ...
    def warning(self, event: str, **kwargs: Any) -> None: ...
    def error(self, event: str, **kwargs: Any) -> None: ...
    def debug(self, event: str, **kwargs: Any) -> None: ...


# ── Metrics ───────────────────────────────────────────────────────────────────

@runtime_checkable
class CounterPort(Protocol):
    """Monotonically-increasing counter (satisfied by OTel Counter and Dummy)."""

    def add(self, amount: float, attributes: Optional[Dict[str, Any]] = None) -> None: ...


@runtime_checkable
class HistogramPort(Protocol):
    """Value distribution recorder (satisfied by OTel Histogram and Dummy)."""

    def record(self, amount: float, attributes: Optional[Dict[str, Any]] = None) -> None: ...


# ── Tracing ───────────────────────────────────────────────────────────────────

@runtime_checkable
class TracerPort(Protocol):
    """
    Span factory interface (satisfied by opentelemetry.trace.Tracer).

    Usage::

        with tracer.start_as_current_span("my.operation") as span:
            span.set_attribute("key", "value")
    """

    def start_as_current_span(self, name: str, **kwargs: Any): ...
