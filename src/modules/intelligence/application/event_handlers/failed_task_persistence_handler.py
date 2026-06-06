from datetime import datetime, timezone

from opentelemetry import trace as _otel_trace
from opentelemetry.trace import StatusCode

from src.shared.logging import get_logger
from src.modules.collection.domain.entities import FailedTask
from src.shared.domain.repositories import FailedTaskRepository
from src.shared.application.events.failed_event import FailedEvent


logger = get_logger(__name__)


class FailedTaskPersistenceHandler:

    def __init__(self, failed_task_repository: FailedTaskRepository) -> None:
        self._repo = failed_task_repository

    def handle(self, event: FailedEvent) -> None:
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

        task = FailedTask(
            task_type=getattr(event, "task_type", "unknown"),
            article_id=getattr(event, "article_id", None),
            article_url=getattr(event, "article_url", None),
            analysis_id=getattr(event, "analysis_id", None),
            exception_type=getattr(event, "exception_type", None),
            exception_message=getattr(event, "exception_message", None),
            context=getattr(event, "context", None),
            traceback=getattr(event, "traceback", None),
            failed_at=datetime.now(timezone.utc),
        )
        try:
            self._repo.save(task)
            logger.info(
                "failed_task_persisted",
                task_type=task.task_type,
                article_id=str(task.article_id) if task.article_id else None,
            )
        except Exception as e:
            logger.error("failed_task_save_error", task_type=task.task_type, error=str(e))
