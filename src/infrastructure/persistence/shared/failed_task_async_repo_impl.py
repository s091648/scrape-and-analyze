from sqlalchemy.ext.asyncio import AsyncSession

from src.modules.collection.domain.entities import FailedTask
from src.shared.domain.repositories import AsyncFailedTaskRepository
from src.shared.logging import get_logger

logger = get_logger(__name__)


class AsyncSqlAlchemyFailedTaskRepository(AsyncFailedTaskRepository):
    """024-async-pipeline-refactor: async sibling of SqlAlchemyFailedTaskRepository
    (untouched). Constructed with the failing task's own AsyncSession so a
    concurrently-failing article never shares mutable session state with
    another article's task."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def save(self, task: FailedTask) -> None:
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
            await self._session.commit()
        except Exception:
            await self._session.rollback()
            raise
        logger.info("failed_task_saved", task_type=task.task_type,
                    article_id=str(task.article_id) if task.article_id else None)
