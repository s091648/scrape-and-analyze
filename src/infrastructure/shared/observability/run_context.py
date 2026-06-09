"""
Run context — thread/async-safe ContextVar tracking for a single scraper run.
Pure Python, no infrastructure dependency.
"""
import uuid
from contextvars import ContextVar

_run_id_var: ContextVar[str | None] = ContextVar("run_id", default=None)


def init_run_context() -> tuple[str, str]:
    """Initialise a new run and return (run_id, correlation_id)."""
    run_id = str(uuid.uuid4())
    correlation_id = str(uuid.uuid4())
    _run_id_var.set(run_id)
    return run_id, correlation_id


def get_run_id() -> str | None:
    """Retrieve the current scraper run ID from the context variable."""
    return _run_id_var.get()
