from datetime import datetime, timezone
from typing import List, Optional, Tuple
from uuid import UUID

from sqlalchemy import text

from src.modules.intelligence.domain.repositories.tag_repository import TagRepository, TagData
from src.modules.intelligence.domain.entities.tag_normalization_suggestion import TagNormalizationSuggestion
from src.shared.logging import get_logger

logger = get_logger(__name__)


class SqlAlchemyTagRepository(TagRepository):

    def __init__(self, session) -> None:
        self._session = session

    def find_by_group(self, group_name: str) -> List[TagData]:
        from models.tag import Tag
        rows = self._session.query(Tag).filter_by(tag_group_name=group_name).all()
        return [
            TagData(id=r.id, name=r.name, tag_group_name=r.tag_group_name,
                    embedding=list(r.embedding) if r.embedding is not None else None)
            for r in rows
        ]

    def find_similar(
        self, embedding: List[float], group_name: str, threshold: float
    ) -> List[Tuple[TagData, float]]:
        vec_str = "[" + ",".join(str(x) for x in embedding) + "]"
        rows = self._session.execute(text("""
            SELECT id, name, tag_group_name,
                   1 - (embedding <=> CAST(:vec AS vector)) AS similarity
            FROM tags
            WHERE tag_group_name = :group_name
              AND embedding IS NOT NULL
              AND (1 - (embedding <=> CAST(:vec AS vector))) >= :threshold
            ORDER BY embedding <=> CAST(:vec AS vector)
            LIMIT 5
        """), {"vec": vec_str, "group_name": group_name, "threshold": threshold}).fetchall()

        return [
            (TagData(id=row[0], name=row[1], tag_group_name=row[2]), float(row[3]))
            for row in rows
        ]

    def save(self, name: str, tag_group_name: str, embedding: List[float]) -> TagData:
        from models.tag import Tag
        vec_str = "[" + ",".join(str(x) for x in embedding) + "]"

        tag = self._session.query(Tag).filter_by(
            name=name, tag_group_name=tag_group_name
        ).first()
        if not tag:
            tag = Tag(name=name, tag_group_name=tag_group_name)
            self._session.add(tag)
            self._session.flush()

        # Update embedding using raw SQL to avoid SQLAlchemy vector serialization issues
        self._session.execute(text(
            "UPDATE tags SET embedding = CAST(:vec AS vector) WHERE id = :id"
        ), {"vec": vec_str, "id": str(tag.id)})

        return TagData(id=tag.id, name=tag.name, tag_group_name=tag.tag_group_name,
                       embedding=embedding)

    def link_to_article(self, tag_id: UUID, article_id: UUID) -> None:
        from models.article import Article
        from models.tag import Tag
        article = self._session.query(Article).filter_by(id=article_id).first()
        tag = self._session.query(Tag).filter_by(id=tag_id).first()
        if article and tag and tag not in article.tags:
            article.tags.append(tag)

    def save_suggestion(self, suggestion: TagNormalizationSuggestion) -> TagNormalizationSuggestion:
        from models.tag_normalization_suggestion import TagNormalizationSuggestion as SuggestionModel
        row = SuggestionModel(
            new_tag_id=suggestion.new_tag_id,
            existing_tag_id=suggestion.existing_tag_id,
            similarity_score=suggestion.similarity_score,
            status=suggestion.status,
            article_id=suggestion.article_id,
            created_at=suggestion.created_at or datetime.now(timezone.utc),
        )
        self._session.add(row)
        self._session.flush()
        suggestion.id = row.id
        return suggestion

    def list_pending_suggestions(self) -> List[TagNormalizationSuggestion]:
        from models.tag_normalization_suggestion import TagNormalizationSuggestion as SuggestionModel
        rows = self._session.query(SuggestionModel).filter_by(status="pending").all()
        return [
            TagNormalizationSuggestion(
                id=r.id,
                new_tag_id=r.new_tag_id,
                existing_tag_id=r.existing_tag_id,
                similarity_score=r.similarity_score,
                article_id=r.article_id,
                status=r.status,
            )
            for r in rows
        ]

    def approve_suggestion(self, suggestion_id: UUID, resolved_by: UUID) -> None:
        from models.tag_normalization_suggestion import TagNormalizationSuggestion as SuggestionModel
        suggestion = self._session.query(SuggestionModel).filter_by(id=suggestion_id).first()
        if not suggestion:
            return

        new_tag_id = str(suggestion.new_tag_id)
        existing_tag_id = str(suggestion.existing_tag_id)

        # Re-point article_tags from new_tag to existing_tag.                                              
        # JOIN articles guards against orphaned article_tags rows (article deleted without                 
        # cleaning up the junction table) which would violate fk_at_article on insert.
        self._session.execute(text("""
            INSERT INTO article_tags (article_id, tag_id)
            SELECT at.article_id, :existing_id                                                             
            FROM article_tags at                                                                           
            INNER JOIN articles a ON a.id = at.article_id                                                  
            WHERE at.tag_id = :new_id
            ON CONFLICT DO NOTHING
        """), {"existing_id": existing_tag_id, "new_id": new_tag_id})

        # Remove old article_tags rows pointing to new_tag
        self._session.execute(text(
            "DELETE FROM article_tags WHERE tag_id = :new_id"
        ), {"new_id": new_tag_id})

        # Expunge the ORM object before deleting the tag.
        # tag_normalization_suggestions.new_tag_id has ondelete='CASCADE', so
        # DELETE on tags would also delete this suggestion row. If SQLAlchemy still
        # holds a reference it will try to UPDATE the deleted row → StaleDataError.
        self._session.expunge(suggestion)

        # Delete the new (duplicate) tag; CASCADE removes the suggestion row too
        self._session.execute(text(
            "DELETE FROM tags WHERE id = :new_id"
        ), {"new_id": new_tag_id})

        logger.info("tag_suggestion_approved", suggestion_id=str(suggestion_id),
                    resolved_by=str(resolved_by))

    def reject_suggestion(self, suggestion_id: UUID, resolved_by: UUID) -> None:
        from models.tag_normalization_suggestion import TagNormalizationSuggestion as SuggestionModel
        suggestion = self._session.query(SuggestionModel).filter_by(id=suggestion_id).first()
        if not suggestion:
            return
        suggestion.status = "rejected"
        suggestion.resolved_at = datetime.now(timezone.utc)
        suggestion.resolved_by = resolved_by
        logger.info("tag_suggestion_rejected", suggestion_id=str(suggestion_id))

    def commit(self) -> None:
        try:
            self._session.commit()
        except Exception:
            self._session.rollback()
            raise
