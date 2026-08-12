from dataclasses import dataclass, field
from typing import Tuple

from src.shared.domain.value_objects.job_execution_meta import JobExecutionMeta


@dataclass(frozen=True)
class WeeklyReportJobCompletedEvent:
    """Event published when a weekly_report.py run finishes processing every due topic.

    Structurally identical in shape to PipelineCompletedEvent/MetricsRefreshCompletedEvent/
    RagBackfillCompletedEvent — a job-level operator summary — but distinct from the
    per-report email/telegram notifications GenerateWeeklyReportUseCase already sends to
    subscribers for each generated report. This event is the operator-facing "did the job
    itself run cleanly" signal; the per-report notifications are the reader-facing content."""
    total_topics: int
    generated: int
    failed: int
    execution: JobExecutionMeta
    # LLM provider_names that hit RateLimitExhausted this run (ResilientLLMService.
    # exhausted_providers) — without this, a run where summaries failed because the
    # LLM chain is rate-limited looks identical to "nothing was due".
    rate_limited_providers: Tuple[str, ...] = field(default_factory=tuple)
