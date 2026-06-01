"""
infrastructure/shared/logging.py — canonical structured-logging setup.

Responsibilities:
  - configure_logging(): called ONCE at process startup (entrypoint) to set
    output format (JSON) and attach optional sinks (Loki).
  - get_logger(name): returns a structlog bound logger; safe to call before
    configure_logging() — structlog defers configuration lazily.
  - bind_correlation_id(): stores a correlation ID in a ContextVar so every
    subsequent log line in the same thread/task carries it automatically.

Application and domain code should NOT import from here directly.
They should use src.shared.logging.get_logger(), which only exposes
get_logger() without pulling in any infrastructure dependency.
"""
import structlog
from contextvars import ContextVar
from typing import Any

_correlation_id_var: ContextVar[str] = ContextVar("correlation_id", default="")
_topic_id_var: ContextVar[str] = ContextVar("topic_id", default="")


def bind_correlation_id(correlation_id: str) -> None:
    _correlation_id_var.set(correlation_id)


def get_correlation_id() -> str:
    return _correlation_id_var.get()


def bind_topic_id(topic_id: str) -> None:
    _topic_id_var.set(topic_id)


def _add_correlation_id(logger: Any, method_name: str, event_dict: dict) -> dict:
    corr_id = _correlation_id_var.get()
    if corr_id:
        event_dict["correlation_id"] = corr_id
    return event_dict


def _add_topic_id(logger: Any, method_name: str, event_dict: dict) -> dict:
    tid = _topic_id_var.get()
    if tid:
        event_dict["topic_id"] = tid
    return event_dict


def configure_logging() -> None:
    """Configure structlog for JSON output and attach optional Loki sink.

    Must be called once at process startup before any log lines are emitted.
    Loki setup is optional — if GRAFANA_* env vars are absent the call is a no-op.
    """
    from src.infrastructure.shared.observability.loki_logging import configure_loki
    configure_loki()

    structlog.configure(
        processors=[
            structlog.stdlib.add_log_level,
            _add_correlation_id,
            _add_topic_id,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=False,
    )
