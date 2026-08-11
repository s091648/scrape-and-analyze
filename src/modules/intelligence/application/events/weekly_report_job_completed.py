from dataclasses import dataclass

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
