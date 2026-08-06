from typing import List, Optional
from uuid import UUID

from src.shared.domain.entities import Article
from src.shared.domain.repositories import TopicRepository
from src.shared.domain.value_objects.tag_mode import TagMode
from src.shared.logging import get_logger
from src.modules.intelligence.domain.entities import Analysis
from src.modules.intelligence.domain.repositories import (
    AnalysisRepository,
    TagGroupDefinitionRepository,
)
from src.modules.intelligence.domain.services import LLMService, EmbeddingService
from src.modules.intelligence.domain.value_objects import AnalysisPrompt, TagGroup, AnalysisTagGroup
from .analysis_result import AnalysisResult

logger = get_logger(__name__)


class AnalyzeArticleUseCase:
    """Orchestrates LLM analysis of an article including prompt rendering and persistence."""

    def __init__(
        self,
        llm_service: LLMService,
        analysis_repository: AnalysisRepository,
        topic_repository: TopicRepository,
        tag_group_definition_repository: TagGroupDefinitionRepository,
        prompt: AnalysisPrompt,
        embedding_service: Optional[EmbeddingService] = None,
    ) -> None:
        self._llm_service = llm_service
        self._analysis_repository = analysis_repository
        self._topic_repository = topic_repository
        self._tag_group_definition_repository = tag_group_definition_repository
        self._prompt = prompt
        self._embedding_service = embedding_service

    def execute(self, article: Article) -> AnalysisResult:
        """Analyze the article via LLM, persist the result, and return an AnalysisResult."""
        content = article.get_analysis_content()
        topic_display_name: Optional[str] = None
        if article.topic_id is not None:
            _topic = self._topic_repository.find_by_id(article.topic_id)
            if _topic is not None:
                topic_display_name = _topic.display_name
        prompt = self._build_prompt(article.topic_id)
        result = self._llm_service.analyze(content, prompt)

        if result is None:
            logger.error("llm_analysis_failed", article_id=str(article.id))
            return AnalysisResult(
                success=False,
                article_id=article.id,
                article_url=article.url,
                exception_type="LLMAnalysisError",
                exception_message="All LLM providers returned None",
                topic_display_name=topic_display_name,
            )

        analysis_content, analysis_metadata = result

        # In unsupervised + semi mode, persist any new tag groups the LLM
        # generated so that downstream tag saving (NormalizeTagsUseCase) always
        # has a matching TagGroupDefinition row. Supervised mode skips upsert
        # because all groups must be predefined.
        if article.topic_id is not None:
            topic = self._topic_repository.find_by_id(article.topic_id)
            if topic is not None and topic.tag_mode != TagMode.SUPERVISED:
                self._upsert_generated_tag_groups(
                    analysis_content.tag_groups or [],
                    article.topic_id,
                )

        analysis = Analysis(
            article_id=article.id,
            analysis_content=analysis_content,
            analysis_metadata=analysis_metadata,
        )

        try:
            self._analysis_repository.save(analysis)
        except Exception as e:
            logger.error("analysis_save_failed", article_id=str(article.id), error=str(e))
            return AnalysisResult(
                success=False,
                article_id=article.id,
                article_url=article.url,
                exception_type=type(e).__name__,
                exception_message=str(e),
                topic_display_name=topic_display_name,
            )

        logger.info(
            "analysis_completed",
            article_id=str(article.id),
            source=article.source,
            model=analysis_metadata.model_used,
            input_tokens=analysis_metadata.input_tokens,
            output_tokens=analysis_metadata.output_tokens,
        )

        return AnalysisResult(
            success=True,
            article_id=article.id,
            article_url=article.url,
            analysis=analysis,
            topic_display_name=topic_display_name,
        )

    # ── Private helpers ──────────────────────────────────────────────────────

    def _build_prompt(self, topic_id: Optional[UUID]) -> str:
        """
        Render an AnalysisPrompt for the article's topic.

        Priority:
          1. article has a topic_id + topic found in DB
               → supervised:      render_fixed (constrained to predefined groups)
               → semi_supervised: render_semi  (existing groups as hints, new allowed)
               → unsupervised:    render_auto  (LLM generates freely)
          2. no topic_id → render_auto with all active topics merged
          3. no topics in DB → return unrendered auto template
        """
        if topic_id is not None:
            topic = self._topic_repository.find_by_id(topic_id)
            if topic is not None:
                if topic.tag_mode == TagMode.SUPERVISED:
                    db_groups = self._tag_group_definition_repository.find_by_topic_id(topic_id)
                    if db_groups:
                        tag_groups = [
                            TagGroup(name=g.name, display_name=g.display_name, description=g.description or "")
                            for g in db_groups
                        ]
                        return self._prompt.render_fixed(
                            topic=topic.display_name,
                            tag_groups=tag_groups,
                        ).content
                    logger.warning(
                        "supervised_mode_no_groups_falling_back_to_auto",
                        topic_id=str(topic_id),
                    )

                elif topic.tag_mode == TagMode.SEMI_SUPERVISED:
                    db_groups = self._tag_group_definition_repository.find_by_topic_id(topic_id)
                    if db_groups:
                        tag_groups = [
                            TagGroup(name=g.name, display_name=g.display_name, description=g.description or "")
                            for g in db_groups
                        ]
                        return self._prompt.render_semi(
                            topic=topic.display_name,
                            tag_groups=tag_groups,
                        ).content

                return self._prompt.render_auto(topic=topic.display_name).content

        topics = self._topic_repository.list_active()
        if not topics:
            logger.warning("no_active_topics_using_unrendered_prompt")
            return self._prompt.content

        topic_str = ", ".join(t.display_name for t in topics)
        return self._prompt.render_auto(topic=topic_str).content

    def _upsert_generated_tag_groups(
        self,
        tag_groups: List[AnalysisTagGroup],
        topic_id: UUID,
    ) -> None:
        """Persist LLM-generated tag group keys as TagGroupDefinition rows (unsupervised + semi mode)."""
        valid = [(tg, tg.group_name) for tg in tag_groups if tg.group_name]
        if not valid:
            return

        # Batch-embed all group names for cosine similarity later
        embeddings: List[Optional[List[float]]] = [None] * len(valid)
        if self._embedding_service is not None:
            try:
                texts = [
                    f"{gk} - {gk.replace('_', ' ').title()}"
                    for _, gk in valid
                ]
                embeddings = self._embedding_service.embed_batch(texts)
            except Exception as e:
                logger.warning("tag_group_embedding_failed", error=str(e))

        for (tg, group_key), embedding in zip(valid, embeddings):
            display_name = group_key.replace("_", " ").title()
            try:
                self._tag_group_definition_repository.upsert(
                    name=group_key,
                    display_name=display_name,
                    topic_id=topic_id,
                    embedding=embedding,
                )
            except Exception as e:
                logger.warning(
                    "tag_group_definition_upsert_failed",
                    group=group_key,
                    topic_id=str(topic_id),
                    error=str(e),
                )
