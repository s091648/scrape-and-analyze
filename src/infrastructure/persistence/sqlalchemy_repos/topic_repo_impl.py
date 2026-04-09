from typing import List, Optional
from uuid import UUID

from src.domain.entities.topic import TopicEntity
from src.domain.repositories.topic_repository import TopicRepository
from src.utils.logging import get_logger

logger = get_logger(__name__)


class SqlAlchemyTopicRepository(TopicRepository):

    def __init__(self, session) -> None:
        self._session = session

    def list_active(self) -> List[TopicEntity]:
        from models.topic import Topic
        rows = (
            self._session.query(Topic)
            .filter_by(is_active=True)
            .order_by(Topic.sort_order)
            .all()
        )
        return [self._to_entity(r) for r in rows]

    def find_by_id(self, topic_id: UUID) -> Optional[TopicEntity]:
        from models.topic import Topic
        row = self._session.query(Topic).filter_by(id=topic_id).first()
        return self._to_entity(row) if row else None

    @staticmethod
    def _to_entity(row) -> TopicEntity:
        return TopicEntity(
            id=row.id,
            name=row.name,
            display_name=row.display_name,
            description=row.description,
            color_hex=row.color_hex,
            prompt_override=row.prompt_override,
            sort_order=row.sort_order,
            is_active=row.is_active,
            created_at=row.created_at,
        )
