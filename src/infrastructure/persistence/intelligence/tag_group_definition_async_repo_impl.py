from typing import List, Optional
from uuid import UUID

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from src.modules.intelligence.domain.repositories.tag_group_definition_repository import (
    AsyncTagGroupDefinitionRepository,
    TagGroupDefinitionData,
)
from src.shared.logging import get_logger

logger = get_logger(__name__)


class AsyncSqlAlchemyTagGroupDefinitionRepository(AsyncTagGroupDefinitionRepository):
    """024-async-pipeline-refactor: async sibling of
    SqlAlchemyTagGroupDefinitionRepository (untouched)."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def find_by_topic_id(self, topic_id: UUID) -> List[TagGroupDefinitionData]:
        """Return all tag group definitions for a given topic, ordered by sort_order."""
        from models.tag_group import TagGroupDefinition

        result = await self._session.execute(
            select(TagGroupDefinition)
            .filter_by(topic_id=topic_id)
            .order_by(TagGroupDefinition.sort_order, TagGroupDefinition.display_name)
        )
        rows = result.scalars().all()
        return [
            TagGroupDefinitionData(
                name=r.name,
                display_name=r.display_name,
                description=r.description,
            )
            for r in rows
        ]

    async def upsert(
        self,
        name: str,
        display_name: str,
        topic_id: UUID,
        description: Optional[str] = None,
        embedding: Optional[List[float]] = None,
    ) -> None:
        """Insert a new tag group or update its embedding if it already exists."""
        from models.tag_group import TagGroupDefinition

        result = await self._session.execute(
            select(TagGroupDefinition).filter_by(name=name, topic_id=topic_id)
        )
        existing = result.scalars().first()

        if existing:
            if embedding is not None and existing.embedding is None:
                vec_str = "[" + ",".join(str(x) for x in embedding) + "]"
                await self._session.execute(
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
        await self._session.flush()

        if embedding is not None:
            vec_str = "[" + ",".join(str(x) for x in embedding) + "]"
            await self._session.execute(
                text(
                    "UPDATE tag_group_definitions SET embedding = CAST(:vec AS vector)"
                    " WHERE id = :id"
                ),
                {"vec": vec_str, "id": str(grp.id)},
            )
        logger.info("tag_group_definition_created", name=name, topic_id=str(topic_id))
