from datetime import datetime, timezone

from src.shared.logging import get_logger
from src.modules.collection.domain.entities import FailedTask
from src.shared.domain.repositories import FailedTaskRepository
from src.modules.intelligence.application.events import AnalysisFailedEvent


logger = get_logger(__name__)


class AnalysisFailedHandler:
    """Persists a FailedTask record when LLM analysis fails."""

    def __init__(self, failed_task_repository: FailedTaskRepository) -> None:
        self._repo = failed_task_repository

    def handle(self, event: AnalysisFailedEvent) -> None:
        """Save a FailedTask from the analysis failure event."""
        task = FailedTask(
            task_type="analyze",
            article_id=event.article_id,
            article_url=event.article_url,
            exception_type=event.exception_type,
            exception_message=event.exception_message,
            failed_at=datetime.now(timezone.utc),
        )
        try:
            self._repo.save(task)
            logger.info(
                "analysis_failure_recorded",
                article_id=str(event.article_id),
                exception_type=event.exception_type,
            )
        except Exception as e:
            logger.error(
                "failed_task_save_error",
                article_id=str(event.article_id),
                error=str(e),
            )
