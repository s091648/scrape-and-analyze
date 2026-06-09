from datetime import datetime, timezone
from typing import List, Optional, Tuple
from uuid import UUID

from sqlalchemy import text

from src.modules.intelligence.domain.repositories.tag_repository import TagRepository, TagData
from src.modules.intelligence.domain.entities.tag_normalization_suggestion import TagNormalizationSuggestion
from src.shared.logging import get_logger

logger = get_logger(__name__)


class SqlAlchemyTagRepository(TagRepository):
    """SQLAlchemy implementation of TagRepository for tag persistence and similarity search."""

    def __init__(self, session) -> None:
        self._session = session

    def find_by_group(self, group_name: str, topic_id: UUID) -> List[TagData]:
        """Return all tags belonging to a specific tag group and topic."""
        from models.tag import Tag
        from models.tag import Tag
        from models.tag_group import TagGroupDefinition
        rows = (
            self._session.query(Tag)
            .join(TagGroupDefinition, Tag.tag_group_id == TagGroupDefinition.id)
            .filter(TagGroupDefinition.name == group_name, TagGroupDefinition.topic_id == topic_id)
            .all()
        )
        return [
            TagData(id=r.id, name=r.name, tag_group_name=r.group_def.name,
                    embedding=list(r.embedding) if r.embedding is not None else None)
            for r in rows
        ]

    def find_similar(
        self, embedding: List[float], group_name: str, topic_id: Optional[UUID], threshold: float
    ) -> List[Tuple[TagData, float]]:
        """Find tags with cosine similarity above threshold using pgvector nearest-neighbor search."""
        if topic_id is None:
            return []
        vec_str = "[" + ",".join(str(x) for x in embedding) + "]"
        rows = self._session.execute(text("""
            SELECT t.id, t.name, tgd.name AS group_name,
                   1 - (t.embedding <=> CAST(:vec AS vector)) AS similarity
            FROM tags t
            JOIN tag_group_definitions tgd ON tgd.id = t.tag_group_id
            WHERE tgd.name = :group_name
              AND tgd.topic_id = :topic_id
              AND t.embedding IS NOT NULL
              AND (1 - (t.embedding <=> CAST(:vec AS vector))) >= :threshold
            ORDER BY t.embedding <=> CAST(:vec AS vector)
            LIMIT 5
        """), {
            "vec": vec_str,
            "group_name": group_name,
            "topic_id": str(topic_id),
            "threshold": threshold,
        }).fetchall()

        return [
            (TagData(id=row[0], name=row[1], tag_group_name=row[2]), float(row[3]))
            for row in rows
        ]

    def save(self, name: str, tag_group_name: str, embedding: List[float], topic_id: Optional[UUID]) -> TagData:
        """Create or update a tag with its embedding vector under the given group and topic."""
        from models.tag import Tag
        from models.tag_group import TagGroupDefinition
        vec_str = "[" + ",".join(str(x) for x in embedding) + "]"

        if topic_id is None:
            raise ValueError("topic_id is required to save a tag")

        group = self._session.query(TagGroupDefinition).filter_by(
            name=tag_group_name, topic_id=topic_id
        ).first()
        if not group:
            raise ValueError(f"Tag group '{tag_group_name}' not found for topic {topic_id}")

        tag = self._session.query(Tag).filter_by(
            name=name, tag_group_id=group.id
        ).first()
        if not tag:
            tag = Tag(name=name, tag_group_id=group.id)
            self._session.add(tag)
            self._session.flush()

        self._session.execute(text(
            "UPDATE tags SET embedding = CAST(:vec AS vector) WHERE id = :id"
        ), {"vec": vec_str, "id": str(tag.id)})

        return TagData(id=tag.id, name=tag.name, tag_group_name=tag_group_name, embedding=embedding)

    def link_to_article(self, tag_id: UUID, article_id: UUID) -> None:
        """Associate a tag with an article if not already linked."""
        from models.article import Article
        from models.tag import Tag
        article = self._session.query(Article).filter_by(id=article_id).first()
        tag = self._session.query(Tag).filter_by(id=tag_id).first()
        if article and tag and tag not in article.tags:
            article.tags.append(tag)

    def save_suggestion(self, suggestion: TagNormalizationSuggestion) -> TagNormalizationSuggestion:
        """Persist a tag normalization suggestion and backfill the generated ID."""
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
        """Return all tag normalization suggestions with status='pending'."""
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
        """Merge the new tag into the existing tag: reassign article links, delete the new tag."""
        from models.tag_normalization_suggestion import TagNormalizationSuggestion as SuggestionModel
        suggestion = self._session.query(SuggestionModel).filter_by(id=suggestion_id).first()
        if not suggestion:
            return

        new_tag_id = str(suggestion.new_tag_id)
        existing_tag_id = str(suggestion.existing_tag_id)

        self._session.execute(text("""
            INSERT INTO article_tags (article_id, tag_id)
            SELECT at.article_id, :existing_id
            FROM article_tags at
            INNER JOIN articles a ON a.id = at.article_id
            WHERE at.tag_id = :new_id
            ON CONFLICT DO NOTHING
        """), {"existing_id": existing_tag_id, "new_id": new_tag_id})

        self._session.execute(text(
            "DELETE FROM article_tags WHERE tag_id = :new_id"
        ), {"new_id": new_tag_id})

        self._session.expunge(suggestion)
        self._session.execute(text(
            "DELETE FROM tags WHERE id = :new_id"
        ), {"new_id": new_tag_id})

        logger.info("tag_suggestion_approved", suggestion_id=str(suggestion_id),
                    resolved_by=str(resolved_by))

    def reject_suggestion(self, suggestion_id: UUID, resolved_by: UUID) -> None:
        """Mark a normalization suggestion as rejected and record who resolved it."""
        from models.tag_normalization_suggestion import TagNormalizationSuggestion as SuggestionModel
        suggestion = self._session.query(SuggestionModel).filter_by(id=suggestion_id).first()
        if not suggestion:
            return
        suggestion.status = "rejected"
        suggestion.resolved_at = datetime.now(timezone.utc)
        suggestion.resolved_by = resolved_by
        logger.info("tag_suggestion_rejected", suggestion_id=str(suggestion_id))

    def commit(self) -> None:
        """Commit the current transaction, rolling back on failure."""
        try:
            self._session.commit()
        except Exception:
            self._session.rollback()
            raise
