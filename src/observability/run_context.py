import uuid
from contextvars import ContextVar
from datetime import datetime, timezone


# Context variables (thread-safe)
_run_id_var: ContextVar[str | None] = ContextVar("run_id", default=None)
_correlation_id_var: ContextVar[str | None] = ContextVar("correlation_id", default=None)
_start_time_var: ContextVar[datetime | None] = ContextVar("start_time", default=None)


def init_run_context() -> tuple[str, str]:
    """
    Initialize run context for a single scraper execution.

    Returns:
        (run_id, correlation_id)
    """

    run_id = str(uuid.uuid4())
    correlation_id = str(uuid.uuid4())

    _run_id_var.set(run_id)
    _correlation_id_var.set(correlation_id)
    _start_time_var.set(datetime.now(timezone.utc))

    return run_id, correlation_id


def get_run_id() -> str | None:
    """Return current run_id"""
    return _run_id_var.get()


def get_correlation_id() -> str | None:
    """Return current correlation_id"""
    return _correlation_id_var.get()


def get_start_time() -> datetime | None:
    """Return run start time"""
    return _start_time_var.get()