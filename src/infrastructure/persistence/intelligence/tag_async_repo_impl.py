from datetime import datetime, timezone
from typing import List, Optional, Tuple
from uuid import UUID

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from shared.domain.exceptions import NotFoundError, ValidationError
from src.infrastructure.persistence.intelligence.tag_repo_queries import (
    find_similar_tags_stmt, update_tag_embedding_stmt,
)
from src.modules.intelligence.domain.repositories.tag_repository import AsyncTagRepository, TagData
from src.modules.intelligence.domain.entities.tag_normalization_suggestion import TagNormalizationSuggestion
from src.shared.logging import get_logger

logger = get_logger(__name__)


class AsyncSqlAlchemyTagRepository(AsyncTagRepository):
    """024-async-pipeline-refactor: async sibling of SqlAlchemyTagRepository
    (untouched). Covers only find_similar/save/link_to_article/save_suggestion/
    commit — what NormalizeTagsUseCase calls; see AsyncTagRepository.

    link_to_article uses a direct INSERT into article_tags instead of the sync
    version's `article.tags.append(tag)` ORM-relationship pattern — appending
    to a lazily-loaded collection requires an implicit sync load, which raises
    under AsyncSession unless the relationship was eagerly loaded first. A
    direct upsert avoids needing to load the collection at all.
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def find_similar(
        self, embedding: List[float], group_name: str, topic_id: Optional[UUID], threshold: float
    ) -> List[Tuple[TagData, float]]:
        """Find tags with cosine similarity above threshold using pgvector nearest-neighbor search."""
        if topic_id is None:
            return []
        stmt, params = find_similar_tags_stmt(embedding, group_name, topic_id, threshold)
        result = await self._session.execute(stmt, params)
        rows = result.fetchall()

        return [
            (TagData(id=row[0], name=row[1], tag_group_name=row[2]), float(row[3]))
            for row in rows
        ]

    async def save(self, name: str, tag_group_name: str, embedding: List[float], topic_id: Optional[UUID]) -> TagData:
        """Create or update a tag with its embedding vector under the given group and topic.

        2026-09-10 incident: this used to be SELECT-then-INSERT (see git
        history) — a plain check-then-act race. Each article in the pipeline
        runs its own AsyncSession/transaction (TEXT_STAGE_CONCURRENCY
        concurrent per-article tasks, see CollectionPipeline docstring), so
        two articles normalizing the same brand-new tag name in the same
        group could both SELECT "not found" and both INSERT, and the loser
        blew up with a raw asyncpg UniqueViolationError on uq_tag_name_group
        instead of a handled outcome.
        Fixed with a single atomic `INSERT ... ON CONFLICT DO NOTHING` against
        that same unique index, rather than an app-level catch-IntegrityError-
        and-retry loop: Postgres itself blocks the losing INSERT until the
        winner's transaction resolves, then either proceeds (winner rolled
        back) or reports the conflict (winner committed) — so one re-SELECT
        on conflict is always enough, no retry/backoff loop needed. A retry
        loop would also have to wrap the failed statement in its own
        SAVEPOINT (`session.begin_nested()`) to avoid poisoning the rest of
        this session's transaction — NormalizeTagsUseCase.execute() commits
        once for the *whole* tag_groups batch, so letting IntegrityError
        propagate past a plain flush() would abort every other tag already
        flushed-but-uncommitted alongside it. ON CONFLICT DO NOTHING never
        raises, so none of that applies.
        """
        from models.tag import Tag
        from models.tag_group import TagGroupDefinition
        from sqlalchemy.dialects.postgresql import insert as pg_insert

        if topic_id is None:
            raise ValidationError("topic_id is required to save a tag")

        result = await self._session.execute(
            select(TagGroupDefinition).filter_by(name=tag_group_name, topic_id=topic_id)
        )
        group = result.scalars().first()
        if not group:
            raise NotFoundError(f"Tag group '{tag_group_name}' not found for topic {topic_id}")

        insert_stmt = (
            pg_insert(Tag)
            .values(name=name, tag_group_id=group.id)
            .on_conflict_do_nothing(
                index_elements=[Tag.name, Tag.tag_group_id],
                # Must match uq_tag_name_group's partial predicate exactly
                # (models/tag.py) for Postgres to pick it as the arbiter index.
                index_where=text("tag_group_id IS NOT NULL"),
            )
            .returning(Tag.id)
        )
        tag_id = (await self._session.execute(insert_stmt)).scalar_one_or_none()

        if tag_id is None:
            # Conflict: a concurrent task's insert of this exact
            # (name, tag_group_id) won the race and has already committed —
            # re-select it instead of retrying the insert.
            tag_id = (
                await self._session.execute(select(Tag.id).filter_by(name=name, tag_group_id=group.id))
            ).scalar_one()

        stmt, params = update_tag_embedding_stmt(tag_id, embedding)
        await self._session.execute(stmt, params)

        return TagData(id=tag_id, name=name, tag_group_name=tag_group_name, embedding=embedding)

    async def link_to_article(self, tag_id: UUID, article_id: UUID) -> None:
        """Associate a tag with an article if not already linked (direct upsert, see class docstring)."""
        await self._session.execute(text("""
            INSERT INTO article_tags (article_id, tag_id)
            VALUES (:article_id, :tag_id)
            ON CONFLICT DO NOTHING
        """), {"article_id": str(article_id), "tag_id": str(tag_id)})

    async def save_suggestion(self, suggestion: TagNormalizationSuggestion) -> TagNormalizationSuggestion:
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
        await self._session.flush()
        suggestion.id = row.id
        return suggestion

    async def commit(self) -> None:
        """Commit the current transaction, rolling back on failure."""
        try:
            await self._session.commit()
        except Exception:
            await self._session.rollback()
            raise

    async def rollback(self) -> None:
        """Roll back the current transaction (e.g. after a failure in _process
        that never reached commit())."""
        await self._session.rollback()
