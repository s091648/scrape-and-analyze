"""US3 (024-async-pipeline-refactor) tests for the completion report's accuracy.

T052: CollectionPipeline-level (no real DB needed, matches the pattern in
test_collection_pipeline_concurrency.py / test_pipeline_barriers.py) — a run
with one RAG failure and one LLM-rate-limit event on different articles still
produces one accurate PipelineCompletedEvent, sent only after RAG settles.

T054: real-DB integration (async_db_session) — a permanently-failing article
(LLM raises during analyze) gets a FailedTask recorded and does not prevent
another, successful article in the same run from being processed and
correctly indexable — failure isolation under the new per-article
asyncio.Task concurrency, not sequential blocking.
"""
import time
import uuid
import asyncio
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy import select

from src.infrastructure.collection.collection_pipeline import CollectionPipeline
from src.infrastructure.shared.events.in_memory_event_bus import AsyncInMemoryEventBus
from src.modules.collection.application.use_cases import PipelineStats, ArticleOutcome
from src.modules.collection.domain.value_objects import ScrapedArticle
from src.modules.collection.application.events import ArticleScrapedEvent, PipelineCompletedEvent


@asynccontextmanager
async def _fake_session():
    yield MagicMock()


# ---------------------------------------------------------------------------
# T052: accurate completion report, sent only after RAG settles
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_completion_notification_accurate_after_rag_failure_and_llm_rate_limit():
    RAG_DELAY = 0.2
    articles = [
        ScrapedArticle(title="RagFails", url="https://example.com/rag-fail", source="rss",
                        content="c1", published_at=None),
        ScrapedArticle(title="RateLimited", url="https://example.com/rate-limited", source="rss",
                        content="c2", published_at=None),
    ]
    setting = MagicMock(id="id-1", source_type="rss", url="https://example.com/feed")
    mock_setting_repo = MagicMock()
    mock_setting_repo.get_active_due.return_value = [setting]

    mock_executor = MagicMock()
    mock_executor.exhausted_hosts = []
    mock_executor.run_discover.return_value = [MagicMock(), MagicMock()]

    def fetch_all(fetch_tasks, on_result):
        for a in articles:
            on_result(a)
    mock_executor.run_fetch_only.side_effect = fetch_all

    mock_llm_service = MagicMock()
    mock_llm_service.exhausted_providers = ["gemini"]

    pipeline_stats = PipelineStats()

    async def _tracking_builder(session, bus, dispatch_rag):
        async def _on_scraped(event):
            if event.url.endswith("rate-limited"):
                # Simulates AnalyzeArticleUseCase recording a FAILED outcome
                # after ResilientLLMService's providers were all rate-limited.
                pipeline_stats.record("rss", ArticleOutcome.FAILED)
            else:
                pipeline_stats.record("rss", ArticleOutcome.NEW)
                await dispatch_rag(event)
        await bus.subscribe(ArticleScrapedEvent, _on_scraped)

    class _FailingRagHandler:
        async def handle(self, event):
            await asyncio.sleep(RAG_DELAY)
            raise RuntimeError("RAG ingestion failed")

    async def _rag_downstream_builder(rag_session):
        return _FailingRagHandler()

    mock_event_bus = AsyncMock()
    publish_events = []

    async def _record_publish(event):
        publish_events.append((event, time.monotonic()))
    mock_event_bus.publish.side_effect = _record_publish

    pipeline = CollectionPipeline(
        setting_repo=mock_setting_repo,
        scraper_factory=MagicMock(),
        event_bus=mock_event_bus,
        pipeline_stats=pipeline_stats,
        async_sessionmaker_factory=lambda: _fake_session(),
        article_downstream_builder=_tracking_builder,
        rag_downstream_builder=_rag_downstream_builder,
        event_bus_factory=AsyncInMemoryEventBus,
        executor=mock_executor,
        article_repo=None,
        llm_service=mock_llm_service,
    )

    t0 = time.monotonic()
    result = await pipeline.run()  # must not raise despite the RAG failure
    assert result == 2

    completed = [e for e, _ in publish_events if isinstance(e, PipelineCompletedEvent)]
    assert len(completed) == 1
    event, published_at = next((e, t) for e, t in publish_events if isinstance(e, PipelineCompletedEvent))

    # Sent only after the (failing) RAG task actually settled — RAG_DELAY had
    # to fully elapse first, proving Barrier 2 awaited it rather than racing ahead.
    assert published_at - t0 >= RAG_DELAY

    assert event.rate_limited_llm_providers == ("gemini",)
    stats_by_source = {s.source: s for s in event.stats}
    assert stats_by_source["rss"].new == 1
    assert stats_by_source["rss"].failed == 1


# ---------------------------------------------------------------------------
# T054: a permanently-failing article doesn't block another article's success
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_failing_article_records_failed_task_without_blocking_other_articles(async_db_session):
    from models.article import Article
    from src.infrastructure.persistence.shared.article_async_repo_impl import AsyncSqlAlchemyArticleRepository
    from src.infrastructure.persistence.intelligence.analysis_async_repo_impl import AsyncSqlAlchemyAnalysisRepository
    from src.infrastructure.persistence.shared.topic_async_repo_impl import AsyncSqlAlchemyTopicRepository
    from src.infrastructure.persistence.intelligence.tag_group_definition_async_repo_impl import AsyncSqlAlchemyTagGroupDefinitionRepository
    from src.infrastructure.persistence.shared.failed_task_async_repo_impl import AsyncSqlAlchemyFailedTaskRepository
    from src.infrastructure.shared.events.in_memory_event_bus import AsyncInMemoryEventBus
    from src.modules.collection.domain.services import AsyncDedupService
    from src.modules.collection.application.use_cases import ProcessScrapedArticleUseCase
    from src.modules.intelligence.application.use_cases import AnalyzeArticleUseCase
    from src.modules.intelligence.application.event_handlers import ArticleProcessedHandler
    from src.modules.intelligence.application.event_handlers.failed_task_persistence_handler import FailedTaskPersistenceHandler
    from src.modules.intelligence.application.events import AnalysisFailedEvent
    from src.modules.intelligence.domain.value_objects import AnalysisPrompt
    from src.modules.collection.application.event_handlers import ArticleScrapedHandler
    from src.shared.application.events import ArticleProcessedEvent
    from src.modules.intelligence.domain.value_objects import AnalysisContent, AnalysisMetadata

    article_repo = AsyncSqlAlchemyArticleRepository(session=async_db_session)
    analysis_repo = AsyncSqlAlchemyAnalysisRepository(session=async_db_session)
    topic_repo = AsyncSqlAlchemyTopicRepository(session=async_db_session)
    tag_group_def_repo = AsyncSqlAlchemyTagGroupDefinitionRepository(session=async_db_session)
    failed_task_repo = AsyncSqlAlchemyFailedTaskRepository(async_db_session)

    async def _wire(llm):
        bus = AsyncInMemoryEventBus()
        process_uc = ProcessScrapedArticleUseCase(
            article_repo=article_repo, dedup_service=AsyncDedupService(article_repo=article_repo),
        )
        analyze_uc = AnalyzeArticleUseCase(
            llm_service=llm, analysis_repository=analysis_repo, topic_repository=topic_repo,
            tag_group_definition_repository=tag_group_def_repo, prompt=AnalysisPrompt(),
        )
        scraped_handler = ArticleScrapedHandler(use_case=process_uc, pipeline_stats=PipelineStats(), event_bus=bus)
        processed_handler = ArticleProcessedHandler(use_case=analyze_uc, event_bus=bus)
        failed_handler = FailedTaskPersistenceHandler(failed_task_repository=failed_task_repo)
        await bus.subscribe(ArticleProcessedEvent, processed_handler.handle)
        await bus.subscribe(AnalysisFailedEvent, failed_handler.handle)
        return scraped_handler

    # ResilientLLMService.analyze() never raises — it catches every provider
    # exception internally and returns None once all providers are exhausted
    # (see resilient_llm_service.py); that's the real "permanently failing"
    # contract AnalyzeArticleUseCase.execute() is built to handle (LLMAnalysisError).
    failing_llm = AsyncMock()
    failing_llm.analyze.return_value = None
    ok_llm = AsyncMock()
    ok_llm.analyze.return_value = (
        AnalysisContent(tag_groups=[], pain_points="p", insights="i", innovations="n", summary="s"),
        AnalysisMetadata(model_used="test-model", input_tokens=10, output_tokens=5),
    )

    failing_event = ArticleScrapedEvent(
        url=f"https://example.com/{uuid.uuid4()}", title="Fails", content="body", source="rss",
    )
    ok_event = ArticleScrapedEvent(
        url=f"https://example.com/{uuid.uuid4()}", title="Succeeds", content="body", source="rss",
    )

    # Sequential on this shared async_db_session — AsyncSession forbids two
    # concurrent operations on the same instance (real per-article tasks each
    # get their own session, per T039); what matters here is DB-level
    # isolation between the two articles' outcomes, not literal timing.
    handler_failing = await _wire(failing_llm)
    handler_ok = await _wire(ok_llm)
    await handler_failing.handle(failing_event)
    await handler_ok.handle(ok_event)

    from models.failed_task import FailedTask as FailedTaskModel
    failed_tasks = (await async_db_session.execute(select(FailedTaskModel))).scalars().all()
    assert any(ft.exception_message == "All LLM providers returned None" for ft in failed_tasks)

    ok_article = (await async_db_session.execute(select(Article).filter_by(url=ok_event.url))).scalars().first()
    assert ok_article is not None
    from models.analysis import Analysis
    ok_analysis = (await async_db_session.execute(select(Analysis).filter_by(article_id=ok_article.id))).scalars().first()
    assert ok_analysis is not None

    failing_article = (await async_db_session.execute(select(Article).filter_by(url=failing_event.url))).scalars().first()
    assert failing_article is not None  # article row saved even though analysis failed
    failing_analysis = (await async_db_session.execute(select(Analysis).filter_by(article_id=failing_article.id))).scalars().first()
    assert failing_analysis is None
