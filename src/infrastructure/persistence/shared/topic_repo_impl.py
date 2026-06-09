from typing import List, Optional
from uuid import UUID

from src.shared.domain.entities import Topic
from src.shared.domain.repositories import TopicRepository
from src.shared.domain.value_objects.tag_mode import TagMode
from src.shared.logging import get_logger

logger = get_logger(__name__)


class SqlAlchemyTopicRepository(TopicRepository):
    """SQLAlchemy implementation of the TopicRepository interface."""

    def __init__(self, session) -> None:
        self._session = session

    def list_active(self) -> List[Topic]:
        """Return all active topics ordered by sort_order."""
        from models.topic import Topic as TopicModel

        rows = (
            self._session.query(TopicModel)
            .filter_by(is_active=True)
            .order_by(TopicModel.sort_order)
            .all()
        )
        return [self._to_entity(r) for r in rows]

    def find_by_id(self, topic_id: UUID) -> Optional[Topic]:
        """Look up a topic by ID; returns None if not found."""
        from models.topic import Topic as TopicModel

        row = self._session.query(TopicModel).filter_by(id=topic_id).first()
        return self._to_entity(row) if row else None

    @staticmethod
    def _to_entity(row) -> Topic:
        """Convert an ORM Topic row to a domain Topic entity."""
        return Topic(
            id=row.id,
            name=row.name,
            display_name=row.display_name,
            description=row.description,
            color_hex=row.color_hex,
            prompt_override=row.prompt_override,
            sort_order=row.sort_order,
            is_active=row.is_active,
            tag_mode=TagMode(row.tag_mode),
            created_at=row.created_at,
        )
