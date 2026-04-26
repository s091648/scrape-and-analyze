from typing import List, Optional
from uuid import UUID

from src.shared.domain.entities import Topic
from src.shared.domain.repositories import TopicRepository
from src.shared.logging import get_logger

logger = get_logger(__name__)


class SqlAlchemyTopicRepository(TopicRepository):

    def __init__(self, session) -> None:
        self._session = session

    def list_active(self) -> List[Topic]:
        from models.topic import Topic as TopicModel

        rows = (
            self._session.query(TopicModel)
            .filter_by(is_active=True)
            .order_by(TopicModel.sort_order)
            .all()
        )
        return [self._to_entity(r) for r in rows]

    def find_by_id(self, topic_id: UUID) -> Optional[Topic]:
        from models.topic import Topic as TopicModel

        row = self._session.query(TopicModel).filter_by(id=topic_id).first()
        return self._to_entity(row) if row else None

    @staticmethod
    def _to_entity(row) -> Topic:
        return Topic(
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
