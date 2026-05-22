import traceback as tb
from dataclasses import dataclass
from typing import List, Optional, Tuple
from uuid import UUID

from src.modules.intelligence.domain.services.embedding_service import EmbeddingService
from src.modules.intelligence.domain.repositories.tag_repository import TagRepository
from src.modules.intelligence.domain.entities.tag_normalization_suggestion import TagNormalizationSuggestion
from src.shared.logging import get_logger

logger = get_logger(__name__)


@dataclass(frozen=True)
class NormalizeTagsResult:
    success: bool
    analysis_id: UUID
    article_id: UUID
    exception_type: Optional[str] = None
    exception_message: Optional[str] = None
    traceback: Optional[str] = None


class NormalizeTagsUseCase:

    def __init__(
        self,
        embedding_service: EmbeddingService,
        tag_repository: TagRepository,
        auto_merge_threshold: float = 0.95,
        suggest_threshold: float = 0.90,
    ) -> None:
        self._embedding_service = embedding_service
        self._tag_repository = tag_repository
        self._auto_merge_threshold = auto_merge_threshold
        self._suggest_threshold = suggest_threshold

    def execute(
        self,
        analysis_id: UUID,
        article_id: UUID,
        tag_groups: List[Tuple[str, List[str]]],
    ) -> NormalizeTagsResult:
        try:
            self._process(analysis_id, article_id, tag_groups)
            self._tag_repository.commit()
            return NormalizeTagsResult(success=True, analysis_id=analysis_id, article_id=article_id)
        except Exception as e:
            logger.error("normalize_tags_failed", analysis_id=str(analysis_id), error=str(e))
            return NormalizeTagsResult(
                success=False,
                analysis_id=analysis_id,
                article_id=article_id,
                exception_type=type(e).__name__,
                exception_message=str(e),
                traceback=tb.format_exc(),
            )

    def _process(
        self,
        analysis_id: UUID,
        article_id: UUID,
        tag_groups: List[Tuple[str, List[str]]],
    ) -> None:
        for group_name, tag_names in tag_groups:
            for tag_name in tag_names:
                if not tag_name or not tag_name.strip():
                    continue
                self._process_tag(tag_name.strip(), group_name, article_id)

    def _process_tag(self, tag_name: str, group_name: str, article_id: UUID) -> None:
        embedding = self._embedding_service.embed(tag_name)
        similar = self._tag_repository.find_similar(embedding, group_name, self._suggest_threshold)

        if similar:
            best_tag, best_score = similar[0]

            if best_score >= self._auto_merge_threshold:
                # Auto-merge: reuse existing tag
                self._tag_repository.link_to_article(best_tag.id, article_id)
                logger.info("tag_auto_merged", tag=tag_name, merged_into=best_tag.name,
                            similarity=best_score)
                return

            # Mid-range: save new tag and create pending suggestion
            new_tag = self._tag_repository.save(tag_name, group_name, embedding)
            self._tag_repository.link_to_article(new_tag.id, article_id)
            suggestion = TagNormalizationSuggestion(
                new_tag_id=new_tag.id,
                existing_tag_id=best_tag.id,
                similarity_score=best_score,
                article_id=article_id,
            )
            self._tag_repository.save_suggestion(suggestion)
            logger.info("tag_suggestion_created", tag=tag_name, similar_to=best_tag.name,
                        similarity=best_score)
            return

        # No similar tag found: save as new
        new_tag = self._tag_repository.save(tag_name, group_name, embedding)
        self._tag_repository.link_to_article(new_tag.id, article_id)
        logger.info("tag_created", tag=tag_name, group=group_name)
