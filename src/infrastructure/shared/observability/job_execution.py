"""Generalizes the execution_started/execution_completed log convention (previously
only main.py and weekly_report.py) to every scheduled CLI job, and produces the
JobExecutionMeta each job embeds in its completion event for notification rendering.
"""
import time
from datetime import datetime, timezone
from typing import Any, Optional

from src.config.settings import APP_ENV
from src.shared.domain.value_objects.job_execution_meta import JobExecutionMeta


def log_execution_started(logger: Any, *, jitter_seconds: Optional[float] = None, **fields: Any) -> tuple[datetime, float]:
    """Emit the standard execution_started log line. Returns (started_at, t0) — pass both
    to log_execution_completed() at the end of the run. jitter_seconds is only meaningful
    for jobs that sleep a random startup delay to dodge bot detection (currently main.py);
    leave it unset for jobs that don't jitter."""
    started_at = datetime.now(timezone.utc)
    payload: dict[str, Any] = {"app_env": APP_ENV, **fields}
    if jitter_seconds is not None:
        payload["jitter_seconds"] = round(jitter_seconds, 2)
    logger.info("execution_started", **payload)
    return started_at, time.time()


def log_execution_completed(
    logger: Any,
    started_at: datetime,
    t0: float,
    *,
    jitter_seconds: Optional[float] = None,
    **fields: Any,
) -> JobExecutionMeta:
    """Emit the standard execution_completed log line and return the JobExecutionMeta to
    embed in this job's completion event, for jobs that publish one for notification."""
    completed_at = datetime.now(timezone.utc)
    duration_seconds = time.time() - t0
    logger.info("execution_completed", duration_seconds=round(duration_seconds, 2), **fields)
    return JobExecutionMeta(
        started_at=started_at,
        completed_at=completed_at,
        duration_seconds=duration_seconds,
        app_env=APP_ENV,
        jitter_seconds=jitter_seconds,
    )
