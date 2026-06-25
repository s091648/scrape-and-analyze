from datetime import datetime, timedelta, timezone

from src.modules.collection.domain.entities import FailedTask
from src.shared.domain.repositories import FailedTaskRepository
from src.shared.logging import get_logger

logger = get_logger(__name__)


class SqlAlchemyFailedTaskRepository(FailedTaskRepository):
    """SQLAlchemy implementation of the FailedTaskRepository interface."""

    def __init__(self, session) -> None:
        self._session = session

    def save(self, task: FailedTask) -> None:
        """Persist a failed task record and commit immediately."""
        from models.failed_task import FailedTask as FailedTaskModel

        row = FailedTaskModel(
            id=task.id,
            task_type=task.task_type,
            article_url=task.article_url,
            article_id=task.article_id,
            analysis_id=task.analysis_id,
            exception_type=task.exception_type,
            exception_message=task.exception_message,
            context=task.context,
            traceback=task.traceback,
            failed_at=task.failed_at,
            correlation_id=task.correlation_id,
        )
        self._session.add(row)
        try:
            self._session.commit()
        except Exception:
            self._session.rollback()
            raise
        logger.info("failed_task_saved", task_type=task.task_type,
                    article_id=str(task.article_id) if task.article_id else None)

    def find_recent_failures(self, hours: int = 24):
        """Return unresolved failures observed within the last `hours` hours."""
        from models.failed_task import FailedTask as FailedTaskModel

        cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
        return self._session.query(FailedTaskModel).filter(
            FailedTaskModel.failed_at >= cutoff,
            FailedTaskModel.resolved == False
        ).all()
