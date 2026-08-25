import uuid
from typing import List
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.modules.intelligence.domain.repositories import AsyncTagTranslationRepository
from src.shared.logging import get_logger

logger = get_logger(__name__)


class AsyncSqlAlchemyTagTranslationRepository(AsyncTagTranslationRepository):
    """024-async-pipeline-refactor: async sibling of
    SqlAlchemyTagTranslationRepository (untouched)."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def save_tag_translation(self, tag_id: UUID, language: str, name: str) -> None:
        """Insert or update a tag's translated name for a given language.

        024-async-pipeline-refactor follow-up: uses an atomic DB upsert rather
        than select-then-insert — every article's downstream chain runs its own
        translate_tags() batch concurrently (analysis_completed_handler.py), so
        two tasks can both select "no row" for the same tag_id/language and both
        try to insert, hitting uq_tags_translation_tag_language. ON CONFLICT DO
        UPDATE makes the loser update instead of raising."""
        from models.tag_translation import TagsTranslation as TagsTranslationModel

        stmt = insert(TagsTranslationModel).values(
            id=uuid.uuid4(), tag_id=tag_id, language=language, name=name,
        ).on_conflict_do_update(
            index_elements=["tag_id", "language"],
            set_={"name": name},
        )

        try:
            await self._session.execute(stmt)
            await self._session.commit()
        except Exception:
            await self._session.rollback()
            raise

    async def find_tags_without_translation(
        self, language: str, limit: int
    ) -> List[dict]:
        """Return tags that lack a translation row for the specified language."""
        from models.tag import Tag as TagModel
        from models.tag_translation import TagsTranslation as TagsTranslationModel

        result = await self._session.execute(
            select(TagModel)
            .options(selectinload(TagModel.group_def))
            .filter(~TagModel.translations.any(TagsTranslationModel.language == language))
            .order_by(TagModel.name)
            .limit(limit)
        )
        rows = result.scalars().all()

        return [
            {"tag_id": row.id, "name": row.name, "tag_group_name": row.group_def.name if row.group_def else "ungrouped"}
            for row in rows
        ]

    async def save_group_translation(
        self, tag_group_definition_id: UUID, language: str, display_name: str, description: str | None = None
    ) -> None:
        """Insert or update a tag group's translated display name and description.

        024-async-pipeline-refactor follow-up: same atomic-upsert reasoning as
        save_tag_translation above — ON CONFLICT DO UPDATE against
        uq_tag_group_definitions_translation_group_language."""
        from models.tag_group_translation import TagGroupDefinitionsTranslation as TagGroupTranslationModel

        stmt = insert(TagGroupTranslationModel).values(
            id=uuid.uuid4(),
            tag_group_definition_id=tag_group_definition_id,
            language=language,
            display_name=display_name,
            description=description,
        ).on_conflict_do_update(
            index_elements=["tag_group_definition_id", "language"],
            set_={"display_name": display_name, "description": description},
        )

        try:
            await self._session.execute(stmt)
            await self._session.commit()
        except Exception:
            await self._session.rollback()
            raise

    async def find_groups_without_translation(
        self, language: str, limit: int
    ) -> List[dict]:
        """Return tag groups that lack a translation row for the specified language."""
        from models.tag_group import TagGroupDefinition as TagGroupDefinitionModel
        from models.tag_group_translation import TagGroupDefinitionsTranslation as TagGroupTranslationModel

        result = await self._session.execute(
            select(TagGroupDefinitionModel)
            .filter(~TagGroupDefinitionModel.translations.any(TagGroupTranslationModel.language == language))
            .order_by(TagGroupDefinitionModel.sort_order)
            .limit(limit)
        )
        rows = result.scalars().all()

        return [
            {"id": row.id, "name": row.name, "display_name": row.display_name, "description": row.description}
            for row in rows
        ]
