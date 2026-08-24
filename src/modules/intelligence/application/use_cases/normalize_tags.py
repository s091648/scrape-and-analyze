from dataclasses import dataclass
from typing import List, Optional, Tuple
from uuid import UUID

from shared.observability.traceback_filter import format_filtered_exc
from src.modules.intelligence.domain.repositories import AsyncTagRepository
from src.modules.intelligence.domain.entities import TagNormalizationSuggestion
from src.shared.logging import get_logger

logger = get_logger(__name__)


@dataclass(frozen=True)
class NormalizeTagsResult:
    """Outcome of tag normalization carrying success flag and optional error info."""
    success: bool
    analysis_id: UUID
    article_id: UUID
    exception_type: Optional[str] = None
    exception_message: Optional[str] = None
    traceback: Optional[str] = None


class NormalizeTagsUseCase:
    """Normalizes raw LLM tags via embedding similarity: auto-merges or suggests merges.

    024-async-pipeline-refactor: converted to async in place — confirmed
    constructed only once, only inside build_collection_pipeline(). Takes the
    async embedding service and AsyncTagRepository now.
    """

    def __init__(
        self,
        embedding_service,
        tag_repository: AsyncTagRepository,
        auto_merge_threshold: float = 0.95,
        suggest_threshold: float = 0.90,
    ) -> None:
        self._embedding_service = embedding_service
        self._tag_repository = tag_repository
        self._auto_merge_threshold = auto_merge_threshold
        self._suggest_threshold = suggest_threshold

    async def execute(
        self,
        analysis_id: UUID,
        article_id: UUID,
        tag_groups: List[Tuple[str, List[str]]],
        topic_id: Optional[UUID] = None,
    ) -> NormalizeTagsResult:
        """Embed and normalize all tags, auto-merge or create suggestions, then commit."""
        try:
            await self._process(analysis_id, article_id, tag_groups, topic_id)
            await self._tag_repository.commit()
            return NormalizeTagsResult(success=True, analysis_id=analysis_id, article_id=article_id)
        except Exception as e:
            logger.error("normalize_tags_failed", analysis_id=str(analysis_id), error=str(e))
            # The article_session is shared with FailedTaskPersistenceHandler
            # (same per-article downstream chain, see bootstrap.py's
            # article_downstream_builder) — if _process left the session with
            # an unflushed/failed transaction, that handler's later commit()
            # on the same session would fail too, silently losing the failure
            # record. Roll back here so the session is clean regardless of
            # where in _process the failure happened.
            try:
                await self._tag_repository.rollback()
            except Exception as rollback_error:
                logger.error(
                    "normalize_tags_rollback_failed",
                    analysis_id=str(analysis_id),
                    error=str(rollback_error),
                )
            return NormalizeTagsResult(
                success=False,
                analysis_id=analysis_id,
                article_id=article_id,
                exception_type=type(e).__name__,
                exception_message=str(e),
                traceback=format_filtered_exc(e),
            )

    async def _process(
        self,
        analysis_id: UUID,
        article_id: UUID,
        tag_groups: List[Tuple[str, List[str]]],
        topic_id: Optional[UUID],
    ) -> None:
        """Flatten tag groups, embed all tag names, and process each tag."""
        tagged: List[Tuple[str, str]] = []
        for group_name, tag_names in tag_groups:
            for tag_name in tag_names:
                if tag_name and tag_name.strip():
                    tagged.append((tag_name.strip(), group_name))

        if not tagged:
            return

        embeddings = await self._embedding_service.embed_batch([t for t, _ in tagged])

        for (tag_name, group_name), embedding in zip(tagged, embeddings):
            await self._process_tag(tag_name, group_name, article_id, embedding, topic_id)

    async def _process_tag(
        self,
        tag_name: str,
        group_name: str,
        article_id: UUID,
        embedding: List[float],
        topic_id: Optional[UUID],
    ) -> None:
        """Check embedding similarity and auto-merge, suggest, or create the tag."""
        similar = await self._tag_repository.find_similar(
            embedding, group_name, topic_id, self._suggest_threshold
        )

        if similar:
            best_tag, best_score = similar[0]

            if best_score >= self._auto_merge_threshold:
                await self._tag_repository.link_to_article(best_tag.id, article_id)
                logger.info("tag_auto_merged", tag=tag_name, merged_into=best_tag.name,
                            similarity=best_score)
                return

            if best_score >= self._suggest_threshold:
                new_tag = await self._tag_repository.save(tag_name, group_name, embedding, topic_id)
                await self._tag_repository.link_to_article(new_tag.id, article_id)
                suggestion = TagNormalizationSuggestion(
                    new_tag_id=new_tag.id,
                    existing_tag_id=best_tag.id,
                    similarity_score=best_score,
                    article_id=article_id,
                )
                await self._tag_repository.save_suggestion(suggestion)
                logger.info("tag_suggestion_created", tag=tag_name, similar_to=best_tag.name,
                            similarity=best_score)
                return

        new_tag = await self._tag_repository.save(tag_name, group_name, embedding, topic_id)
        await self._tag_repository.link_to_article(new_tag.id, article_id)
        logger.info("tag_created", tag=tag_name, group=group_name)
