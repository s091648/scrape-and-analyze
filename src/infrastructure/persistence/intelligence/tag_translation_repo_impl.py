from typing import List
from uuid import UUID

from sqlalchemy.orm import Session

from src.modules.intelligence.domain.repositories import TagTranslationRepository
from src.shared.logging import get_logger

logger = get_logger(__name__)


class SqlAlchemyTagTranslationRepository(TagTranslationRepository):
    """SQLAlchemy implementation of TagTranslationRepository."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def save_tag_translation(self, tag_id: UUID, language: str, name: str) -> None:
        from models.tag_translation import TagsTranslation as TagsTranslationModel

        existing = self._session.query(TagsTranslationModel).filter_by(
            tag_id=tag_id, language=language,
        ).first()

        if existing:
            existing.name = name
        else:
            model = TagsTranslationModel(tag_id=tag_id, language=language, name=name)
            self._session.add(model)

        self._session.commit()

    def find_tags_without_translation(
        self, language: str, limit: int
    ) -> List[dict]:
        from models.tag import Tag as TagModel
        from models.tag_translation import TagsTranslation as TagsTranslationModel

        rows = (
            self._session.query(TagModel)
            .filter(~TagModel.translations.any(TagsTranslationModel.language == language))
            .order_by(TagModel.name)
            .limit(limit)
            .all()
        )

        return [
            {"tag_id": row.id, "name": row.name, "tag_group_name": row.tag_group_name}
            for row in rows
        ]

    def save_group_translation(
        self, tag_group_definition_id: UUID, language: str, display_name: str, description: str | None = None
    ) -> None:
        from models.tag_group_translation import TagGroupDefinitionsTranslation as TagGroupTranslationModel

        existing = self._session.query(TagGroupTranslationModel).filter_by(
            tag_group_definition_id=tag_group_definition_id, language=language,
        ).first()

        if existing:
            existing.display_name = display_name
            existing.description = description
        else:
            model = TagGroupTranslationModel(
                tag_group_definition_id=tag_group_definition_id,
                language=language,
                display_name=display_name,
                description=description,
            )
            self._session.add(model)

        self._session.commit()

    def find_groups_without_translation(
        self, language: str, limit: int
    ) -> List[dict]:
        from models.tag_group import TagGroupDefinition as TagGroupDefinitionModel
        from models.tag_group_translation import TagGroupDefinitionsTranslation as TagGroupTranslationModel

        rows = (
            self._session.query(TagGroupDefinitionModel)
            .filter(~TagGroupDefinitionModel.translations.any(TagGroupTranslationModel.language == language))
            .order_by(TagGroupDefinitionModel.sort_order)
            .limit(limit)
            .all()
        )

        return [
            {"id": row.id, "name": row.name, "display_name": row.display_name, "description": row.description}
            for row in rows
        ]
