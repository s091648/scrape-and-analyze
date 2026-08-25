import uuid
from datetime import datetime, timezone

from opentelemetry import trace as _otel_trace
from opentelemetry.trace import StatusCode

from src.shared.logging import get_logger
from src.modules.collection.domain.entities import FailedTask
from src.shared.domain.repositories import AsyncFailedTaskRepository
from src.shared.application.events.failed_event import FailedEvent
from src.infrastructure.shared.logging import get_correlation_id


logger = get_logger(__name__)


class FailedTaskPersistenceHandler:
    """Persists any FailedEvent as a FailedTask record with OTel error span.

    024-async-pipeline-refactor: converted to async in place — confirmed
    constructed only once, only inside build_collection_pipeline(). Callers
    may construct one per concurrent task (each with its own AsyncSession-
    bound AsyncFailedTaskRepository) so concurrently-failing articles never
    share mutable session state.
    """

    def __init__(self, failed_task_repository: AsyncFailedTaskRepository) -> None:
        self._repo = failed_task_repository

    async def handle(self, event: FailedEvent) -> None:
        """Extract failure details from the event and persist a FailedTask."""
        span = _otel_trace.get_current_span()
        span.set_attribute("task.type", getattr(event, "task_type", "unknown"))
        exception_type = getattr(event, "exception_type", "unknown") or "unknown"
        span.set_attribute("task.exception_type", exception_type)
        article_id = getattr(event, "article_id", None)
        if article_id:
            span.set_attribute("article.id", str(article_id))
        article_url = getattr(event, "article_url", None)
        if article_url:
            span.set_attribute("article.url", article_url)
        analysis_id = getattr(event, "analysis_id", None)
        if analysis_id:
            span.set_attribute("analysis.id", str(analysis_id))
        span.set_status(StatusCode.ERROR, exception_type)

        corr_id_str = getattr(event, "correlation_id", None) or get_correlation_id()
        try:
            corr_id = uuid.UUID(corr_id_str) if corr_id_str else None
        except (ValueError, AttributeError):
            corr_id = None

        task = FailedTask(
            task_type=getattr(event, "task_type", "unknown"),
            article_id=getattr(event, "article_id", None),
            article_url=getattr(event, "article_url", None),
            analysis_id=getattr(event, "analysis_id", None),
            exception_type=getattr(event, "exception_type", None),
            exception_message=getattr(event, "exception_message", None),
            context=getattr(event, "context", None),
            traceback=getattr(event, "traceback", None),
            correlation_id=corr_id,
            failed_at=datetime.now(timezone.utc),
        )
        try:
            await self._repo.save(task)
            logger.info(
                "failed_task_persisted",
                task_type=task.task_type,
                article_id=str(task.article_id) if task.article_id else None,
            )
        except Exception as e:
            logger.error("failed_task_save_error", task_type=task.task_type, error=str(e))
