from typing import Dict, List
from uuid import UUID

from sqlalchemy.orm import Session
from sqlalchemy import text

from src.modules.translation.domain.repositories import TagTranslationRepository
from src.shared.logging import get_logger

logger = get_logger(__name__)


class SqlAlchemyTagTranslationRepository(TagTranslationRepository):
    """SQLAlchemy implementation of TagTranslationRepository."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def save_tag_translation(self, tag_id: UUID, language: str, name: str) -> None:
        from models.tag_translation import TagTranslation as TagTranslationModel

        existing = self._session.query(TagTranslationModel).filter_by(
            tag_id=tag_id, language=language,
        ).first()

        if existing:
            existing.name = name
        else:
            model = TagTranslationModel(tag_id=tag_id, language=language, name=name)
            self._session.add(model)

        self._session.commit()

    def find_tag_translations(
        self, tag_ids: List[UUID], language: str
    ) -> Dict[UUID, str]:
        from models.tag_translation import TagTranslation as TagTranslationModel

        if not tag_ids:
            return {}

        rows = self._session.query(TagTranslationModel).filter(
            TagTranslationModel.tag_id.in_(tag_ids),
            TagTranslationModel.language == language,
        ).all()

        return {row.tag_id: row.name for row in rows}

    def find_tags_without_translation(
        self, language: str, limit: int
    ) -> List[dict]:
        query = text("""
            SELECT t.id, t.name, t.tag_group_name
            FROM tags t
            WHERE NOT EXISTS (
                SELECT 1 FROM tag_translations tt
                WHERE tt.tag_id = t.id AND tt.language = :target_lang
            )
            ORDER BY t.name
            LIMIT :limit
        """)
        result = self._session.execute(query, {"target_lang": language, "limit": limit})
        rows = result.fetchall()

        return [
            {"tag_id": row[0], "name": row[1], "tag_group_name": row[2]}
            for row in rows
        ]

    def save_group_translation(
        self, tag_group_definition_id: UUID, language: str, display_name: str
    ) -> None:
        from models.tag_group_translation import TagGroupTranslation as TagGroupTranslationModel

        existing = self._session.query(TagGroupTranslationModel).filter_by(
            tag_group_definition_id=tag_group_definition_id, language=language,
        ).first()

        if existing:
            existing.display_name = display_name
        else:
            model = TagGroupTranslationModel(
                tag_group_definition_id=tag_group_definition_id,
                language=language,
                display_name=display_name,
            )
            self._session.add(model)

        self._session.commit()

    def find_group_translations(
        self, group_ids: List[UUID], language: str
    ) -> Dict[UUID, str]:
        from models.tag_group_translation import TagGroupTranslation as TagGroupTranslationModel

        if not group_ids:
            return {}

        rows = self._session.query(TagGroupTranslationModel).filter(
            TagGroupTranslationModel.tag_group_definition_id.in_(group_ids),
            TagGroupTranslationModel.language == language,
        ).all()

        return {row.tag_group_definition_id: row.display_name for row in rows}

    def find_groups_without_translation(
        self, language: str, limit: int
    ) -> List[dict]:
        query = text("""
            SELECT tgd.id, tgd.name, tgd.display_name
            FROM tag_group_definitions tgd
            WHERE NOT EXISTS (
                SELECT 1 FROM tag_group_translations tgt
                WHERE tgt.tag_group_definition_id = tgd.id AND tgt.language = :target_lang
            )
            ORDER BY tgd.sort_order
            LIMIT :limit
        """)
        result = self._session.execute(query, {"target_lang": language, "limit": limit})
        rows = result.fetchall()

        return [
            {"id": row[0], "name": row[1], "display_name": row[2]}
            for row in rows
        ]
