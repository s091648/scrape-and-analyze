from typing import Optional
from uuid import UUID

from src.shared.domain.entities import Article
from src.shared.domain.repositories import TopicRepository
from src.shared.application.ports import EventBus
from src.shared.logging import get_logger
from src.modules.intelligence.domain.entities import Analysis
from src.modules.intelligence.domain.repositories import AnalysisRepository
from src.modules.intelligence.domain.services import LLMService
from src.modules.intelligence.domain.value_objects import AnalysisPrompt, TagGroup
from src.modules.intelligence.application.events import AnalysisFailedEvent, AnalysisCompletedEvent

logger = get_logger(__name__)


class AnalyzeArticleUseCase:
    def __init__(
        self,
        llm_service: LLMService,
        analysis_repository: AnalysisRepository,
        topic_repository: TopicRepository,
        event_bus: Optional[EventBus] = None,
    ) -> None:
        self._llm_service = llm_service
        self._analysis_repository = analysis_repository
        self._topic_repository = topic_repository
        self._event_bus = event_bus

    def execute(self, article: Article) -> bool:
        content = article.get_analysis_content()
        prompt = self._build_prompt(article.topic_id)
        result = self._llm_service.analyze(content, prompt)

        if result is None:
            logger.error("llm_analysis_failed", article_id=str(article.id))
            self._publish_failure(article, exception_type="LLMAnalysisError",
                                  exception_message="All LLM providers returned None")
            return False

        analysis_content, analysis_metadata = result
        analysis = Analysis(
            article_id=article.id,
            analysis_content=analysis_content,
            analysis_metadata=analysis_metadata,
        )

        try:
            self._analysis_repository.save(analysis)
        except Exception as e:
            logger.error("analysis_save_failed", article_id=str(article.id), error=str(e))
            self._publish_failure(article, exception_type=type(e).__name__,
                                  exception_message=str(e))
            return False

        logger.info(
            "analysis_completed",
            article_id=str(article.id),
            model=analysis_metadata.model_used,
            input_tokens=analysis_metadata.input_tokens,
            output_tokens=analysis_metadata.output_tokens,
        )

        # Publish success event for downstream (e.g. translation)
        if self._event_bus is not None:
            self._event_bus.publish(AnalysisCompletedEvent(
                analysis_id=analysis.id,
                article_id=article.id,
            ))

        return True

    def _publish_failure(
        self,
        article: Article,
        exception_type: Optional[str],
        exception_message: Optional[str],
    ) -> None:
        if self._event_bus is None:
            return
        self._event_bus.publish(AnalysisFailedEvent(
            article_id=article.id,
            article_url=article.url,
            exception_type=exception_type,
            exception_message=exception_message,
        ))

    def _build_prompt(self, topic_id: Optional[UUID]) -> str:
        """
        Render an AnalysisPrompt for the article's topic.

        Priority:
          1. article has a topic_id → render with that single topic's context
          2. no topic_id → render with all active topics merged (broad context)
          3. no topics in DB → return unrendered template (best-effort)
        """
        if topic_id is not None:
            topic = self._topic_repository.find_by_id(topic_id)
            if topic is not None:
                tag_groups = [TagGroup(
                    display_name=topic.display_name,
                    description=topic.description or "",
                )]
                return AnalysisPrompt().render(
                    topic=topic.display_name,
                    tag_groups=tag_groups,
                ).content

        # fallback: merge all active topics
        topics = self._topic_repository.list_active()
        if not topics:
            logger.warning("no_active_topics_using_unrendered_prompt")
            return AnalysisPrompt().content

        topic_str = ", ".join(t.display_name for t in topics)
        tag_groups = [
            TagGroup(display_name=t.display_name, description=t.description or "")
            for t in topics
        ]
        return AnalysisPrompt().render(topic=topic_str, tag_groups=tag_groups).content
