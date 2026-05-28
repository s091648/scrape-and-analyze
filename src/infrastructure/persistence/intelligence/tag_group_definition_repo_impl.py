from typing import List, Optional
from uuid import UUID

from src.modules.intelligence.domain.repositories.tag_group_definition_repository import (
    TagGroupDefinitionRepository,
    TagGroupDefinitionData,
)
from src.shared.logging import get_logger

logger = get_logger(__name__)


class SqlAlchemyTagGroupDefinitionRepository(TagGroupDefinitionRepository):

    def __init__(self, session) -> None:
        self._session = session

    def find_by_topic_id(self, topic_id: UUID) -> List[TagGroupDefinitionData]:
        from models.tag_group import TagGroupDefinition

        rows = (
            self._session.query(TagGroupDefinition)
            .filter_by(topic_id=topic_id)
            .order_by(TagGroupDefinition.sort_order, TagGroupDefinition.display_name)
            .all()
        )
        return [
            TagGroupDefinitionData(
                name=r.name,
                display_name=r.display_name,
                description=r.description,
            )
            for r in rows
        ]

    def upsert(
        self,
        name: str,
        display_name: str,
        topic_id: UUID,
        description: Optional[str] = None,
        embedding: Optional[List[float]] = None,
    ) -> None:
        from models.tag_group import TagGroupDefinition
        from sqlalchemy import text

        existing = (
            self._session.query(TagGroupDefinition)
            .filter_by(name=name, topic_id=topic_id)
            .first()
        )

        if existing:
            if embedding is not None and existing.embedding is None:
                vec_str = "[" + ",".join(str(x) for x in embedding) + "]"
                self._session.execute(
                    text(
                        "UPDATE tag_group_definitions SET embedding = CAST(:vec AS vector)"
                        " WHERE id = :id"
                    ),
                    {"vec": vec_str, "id": str(existing.id)},
                )
            return

        grp = TagGroupDefinition(
            name=name,
            display_name=display_name,
            topic_id=topic_id,
            description=description,
        )
        self._session.add(grp)
        self._session.flush()

        if embedding is not None:
            vec_str = "[" + ",".join(str(x) for x in embedding) + "]"
            self._session.execute(
                text(
                    "UPDATE tag_group_definitions SET embedding = CAST(:vec AS vector)"
                    " WHERE id = :id"
                ),
                {"vec": vec_str, "id": str(grp.id)},
            )
        logger.info("tag_group_definition_created", name=name, topic_id=str(topic_id))
