from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass(frozen=True)
class JobExecutionMeta:
    """Wall-clock execution window + environment context, attached to every scheduled
    CLI job's completion event so notification messages render a consistent
    timestamp/environment/duration/jitter block (see JobCompletionMessageBuilder).
    jitter_seconds is only set for jobs that sleep a random startup delay to dodge
    bot detection (currently just main.py) — None for every other job."""

    started_at: datetime
    completed_at: datetime
    duration_seconds: float
    app_env: str
    jitter_seconds: Optional[float] = None
