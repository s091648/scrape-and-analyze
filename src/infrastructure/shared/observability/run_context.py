"""
Run context — thread/async-safe ContextVar tracking for a single scraper run.
Pure Python, no infrastructure dependency.
"""
import uuid
from contextvars import ContextVar
from datetime import datetime, timezone

_run_id_var: ContextVar[str | None] = ContextVar("run_id", default=None)
_correlation_id_var: ContextVar[str | None] = ContextVar("correlation_id", default=None)
_start_time_var: ContextVar[datetime | None] = ContextVar("start_time", default=None)


def init_run_context() -> tuple[str, str]:
    """Initialise a new run and return (run_id, correlation_id)."""
    run_id = str(uuid.uuid4())
    correlation_id = str(uuid.uuid4())
    _run_id_var.set(run_id)
    _correlation_id_var.set(correlation_id)
    _start_time_var.set(datetime.now(timezone.utc))
    return run_id, correlation_id


def get_run_id() -> str | None:
    return _run_id_var.get()


def get_correlation_id() -> str | None:
    return _correlation_id_var.get()


def get_start_time() -> datetime | None:
    return _start_time_var.get()
