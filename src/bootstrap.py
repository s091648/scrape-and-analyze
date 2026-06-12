"""
bootstrap.py — 依賴組裝入口點（取代舊有的 composition_root.py）

職責：
  - 從 DB（llm_providers 表）及環境變數讀取組態
  - 建立所有 infrastructure 物件（DB session、repositories、LLM providers）
  - 組裝 event bus 並完成 handler 訂閱
  - 回傳可執行的 CollectionPipeline

所有業務邏輯與框架細節的「黏合程式碼」集中於此，
讓 entrypoint（main.py）只負責 process-level 的初始化與生命週期管理。
"""
import os
from typing import List

from src.infrastructure.persistence.database import get_session, init_db
from src.shared.logging import get_logger

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# LLM 層: 從 DB provider config 建立 ResilientLLMService
# ---------------------------------------------------------------------------

def build_llm_service(session):
    """Build (ResilientLLMService, ResilientEmbeddingService) from DB provider config."""
    from shared.llm_provider import load_active_providers, load_active_embedding_providers
    from src.infrastructure.intelligence.llm.resilient_llm_service import (
        ResilientLLMService, ProviderHandler,
        ResilientEmbeddingService, EmbeddingProviderHandler
    )
    from src.infrastructure.intelligence.llm.embedding import GeminiEmbeddingProvider
    from src.infrastructure.intelligence.llm.providers import ClaudeProvider, GeminiProvider, OpenRouterProvider
    from src.infrastructure.intelligence.llm.rate_limit import SlidingWindowStrategy, NoOpStrategy

    def _make_strategy(cfg):
        """Instantiate a SlidingWindowStrategy or NoOpStrategy from a provider config dict."""
        s = cfg.get('strategy', {})
        if s.get('type') == 'sliding_window':
            return SlidingWindowStrategy(rpm=s['rpm'], tpm=s['tpm'], rpd=s['rpd'])
        return NoOpStrategy()

    handlers: List[ProviderHandler] = []
    for cfg in load_active_providers(session):
        name = cfg['name']
        api_key = os.environ.get(cfg['api_key_env'], '')
        if name == 'claude':
            provider = ClaudeProvider(api_key=api_key, model=cfg['model'])
        elif name == 'gemini':
            provider = GeminiProvider(api_key=api_key, model=cfg['model'])
        elif name == 'openrouter':
            provider = OpenRouterProvider(api_key=api_key, model=cfg['model'])
        else:
            logger.warning("unknown_provider_skipped", name=name)
            continue
        handlers.append(ProviderHandler(
            provider=provider,
            strategy=_make_strategy(cfg),
            priority=cfg['priority'],
            name=name,
        ))
        logger.info("llm_provider_loaded", name=name, model=cfg['model'], priority=cfg['priority'])

    if not handlers:
        raise ValueError("llm_providers table has no active LLM providers")

    emb_handlers: List[EmbeddingProviderHandler] = []
    for cfg in load_active_embedding_providers(session):
        name = cfg['name']
        api_key = os.environ.get(cfg['api_key_env'], '')
        if name == 'gemini':
            provider = GeminiEmbeddingProvider(api_key=api_key, model=cfg['model'])
        else:
            logger.warning("unknown_embedding_provider_skipped", name=name)
            continue
        emb_handlers.append(EmbeddingProviderHandler(
            provider=provider,
            strategy=_make_strategy(cfg),
            priority=cfg['priority'],
            name=name,
        ))

    if not emb_handlers:
        raise ValueError("llm_providers table has no active embedding providers")

    provider_names = [h.name for h in handlers]
    return ResilientLLMService(handlers=handlers), ResilientEmbeddingService(handlers=emb_handlers), provider_names


# ---------------------------------------------------------------------------
# 主組裝函式
# ---------------------------------------------------------------------------

def build_collection_pipeline():
    """
    組裝完整的 collection → intelligence pipeline。

    回傳 CollectionPipeline 實例，呼叫 .run() 即可執行一輪抓取與分析。

    Session 策略：
      使用單一 SQLAlchemy session 貫穿整個 pipeline 執行週期。
      若需要 per-article transaction 隔離，可改為在 handler 內部
      建立獨立 session（future work）。
    """
    from src.infrastructure.persistence.shared.article_repo_impl import SqlAlchemyArticleRepository
    from src.infrastructure.persistence.shared.topic_repo_impl import SqlAlchemyTopicRepository
    from src.infrastructure.persistence.shared.failed_task_repo_impl import SqlAlchemyFailedTaskRepository
    from src.infrastructure.persistence.intelligence.analysis_repo_impl import SqlAlchemyAnalysisRepository
    from src.infrastructure.persistence.intelligence import SqlAlchemyAnalysesTranslationRepository, SqlAlchemyTagTranslationRepository
    from src.infrastructure.persistence.intelligence.article_translation_repo_impl import SqlAlchemyArticleTranslationRepository
    from src.infrastructure.persistence.intelligence.tag_repo_impl import SqlAlchemyTagRepository
    from src.infrastructure.persistence.intelligence.tag_group_definition_repo_impl import SqlAlchemyTagGroupDefinitionRepository
    from src.infrastructure.intelligence.llm.rate_limit import SlidingWindowStrategy
    from src.infrastructure.persistence.collection.scraper_setting_repo_impl import SqlAlchemyScraperSettingRepository
    from src.infrastructure.persistence.collection.arxiv_metadata_repo_impl import SqlAlchemyArxivMetadataRepository
    from src.infrastructure.shared.events import InMemoryEventBus
    from src.infrastructure.collection.scrapers.scraper_factory import ConcreteScraperFactory
    from src.infrastructure.collection.collection_pipeline import CollectionPipeline
    from src.infrastructure.collection.handlers import OtelMetricsHandler
    from src.infrastructure.shared.notifications import build_notification_handler
    from src.infrastructure.shared.http import get_default_client
    from src.infrastructure.intelligence.prompt.prompt_factory import ConcretePromptFactory

    from src.modules.collection.domain.services import DedupService
    from src.modules.collection.application.use_cases import ProcessScrapedArticleUseCase, PipelineStats
    from src.modules.collection.application.events import ArticleScrapedEvent, PipelineCompletedEvent
    from src.modules.collection.application.event_handlers import ArticleScrapedHandler
    from src.modules.intelligence.application.use_cases import AnalyzeArticleUseCase, TranslateArticleUseCase, TranslateTagsUseCase, NormalizeTagsUseCase
    from src.modules.intelligence.application.event_handlers import ArticleProcessedHandler, AnalysisCompletedHandler
    from src.modules.intelligence.application.event_handlers.tag_normalization_handler import TagNormalizationHandler
    from src.modules.intelligence.application.event_handlers.failed_task_persistence_handler import FailedTaskPersistenceHandler
    from src.modules.intelligence.application.events import AnalysisFailedEvent, AnalysisCompletedEvent, TagNormalizationCompletedEvent, TagNormalizationFailedEvent, TranslationFailedEvent
    from src.shared.application.events import ArticleProcessedEvent
    from src.infrastructure.vector_store.rag_sdk_vector_store_impl import RagSdkVectorStoreService
    from src.infrastructure.vector_store.vectorize_handler import VectorizeHandler
    from src.config.settings import TRANSLATION_LANGUAGES
    

    # ── DB 初始化 ──────────────────────────────────────────────────────────
    init_db()
    session = get_session()

    # ── Repositories ───────────────────────────────────────────────────────
    article_repo = SqlAlchemyArticleRepository(session=session)
    analysis_repo = SqlAlchemyAnalysisRepository(session=session)
    analyses_translation_repo = SqlAlchemyAnalysesTranslationRepository(session=session)
    tag_translation_repo = SqlAlchemyTagTranslationRepository(session=session)
    setting_repo = SqlAlchemyScraperSettingRepository(session=session)
    arxiv_metadata_repo = SqlAlchemyArxivMetadataRepository(session=session)
    topic_repo = SqlAlchemyTopicRepository(session=session)
    failed_task_repo = SqlAlchemyFailedTaskRepository(session=session)
    tag_repo = SqlAlchemyTagRepository(session=session)
    tag_group_def_repo = SqlAlchemyTagGroupDefinitionRepository(session=session)
    article_translation_repo = SqlAlchemyArticleTranslationRepository(session=session)

    # ── Event Bus ──────────────────────────────────────────────────────────
    event_bus = InMemoryEventBus()

    # ── LLM Service ────────────────────────────────────────────────────────
    llm_service, embedding_service, llm_provider_names = build_llm_service(session)

    # ── Prompt Factory ────────────────────────────────────────────────────
    prompt_factory = ConcretePromptFactory()

    # ── Domain Services ────────────────────────────────────────────────────
    dedup_service = DedupService(article_repo=article_repo)
    pipeline_stats = PipelineStats()

    # ── Use Cases ──────────────────────────────────────────────────────────
    process_article_uc = ProcessScrapedArticleUseCase(
        article_repo=article_repo,
        dedup_service=dedup_service,
        arxiv_metadata_repo=arxiv_metadata_repo,
    )
    analyze_article_uc = AnalyzeArticleUseCase(
        llm_service=llm_service,
        analysis_repository=analysis_repo,
        topic_repository=topic_repo,
        tag_group_definition_repository=tag_group_def_repo,
        prompt=prompt_factory.analysis_prompt(),
        embedding_service=embedding_service,
    )
    translate_article_uc = TranslateArticleUseCase(
        llm_service=llm_service,
        translation_repository=analyses_translation_repo,
        prompt=prompt_factory.article_translation_prompt(),
    )
    translate_tags_uc = TranslateTagsUseCase(
        llm_service=llm_service,
        tag_translation_repository=tag_translation_repo,
        tag_prompt=prompt_factory.tag_translation_prompt(),
        group_prompt=prompt_factory.group_translation_prompt(),
    )
    from src.modules.intelligence.application.use_cases.translate_article_body import TranslateArticleBodyUseCase
    translate_body_uc = TranslateArticleBodyUseCase(
        llm_service=llm_service,
        translation_repository=article_translation_repo,
        prompt=prompt_factory.article_body_translation_prompt(),
    )

    # ── Normalize Tags Use Case ────────────────────────────────────────────
    normalize_tags_uc = NormalizeTagsUseCase(
        embedding_service=embedding_service,
        tag_repository=tag_repo,
    )

    # ── Tracing wrappers ───────────────────────────────────────────────────
    from opentelemetry.trace import StatusCode as _StatusCode
    from src.infrastructure.shared.observability import get_tracer as _get_tracer
    from src.infrastructure.shared.observability.span_wrappers import (
        with_span,
        with_span_deferred,
        with_article_pipeline_span,
    )
    from shared.enums.observability import SpanName

    _tracer = _get_tracer()

    # ── Vector Store ───────────────────────────────────────────────────────
    _rag_enabled = bool(os.environ.get("CHAT_SERVICE_URL"))
    if _rag_enabled:
        try:
            from chatbot_plugin_sdk import (
                IngestProcessor,
                SyncPgBackend,
                DatabaseConfig,
                EndpointProvider,
            )
            _embedding_dim = int(os.environ.get("EMBEDDING_DIM", "768"))
            backend = SyncPgBackend(DatabaseConfig(
                dbname=os.environ.get("VECTOR_DB_NAME", ""),
                user=os.environ.get("VECTOR_DB_USER", ""),
                password=os.environ.get("VECTOR_DB_PASSWORD", ""),
                host=os.environ.get("VECTOR_DB_HOST", "localhost"),
                port=int(os.environ.get("VECTOR_DB_PORT", "5432")),
            ))
            processor = IngestProcessor()
            processor.configure(
                backend=backend,
                dense=EndpointProvider(
                    url=os.environ.get("EMBEDDING_MODEL_API", ""),
                    dimension=_embedding_dim,
                ),
            )
            vector_store = RagSdkVectorStoreService(processor)
            vectorize_handler = VectorizeHandler(vector_store)
            logger.info("rag_vector_store_initialized")
        except Exception:
            logger.exception("rag_vector_store_init_failed_disabling")
            vectorize_handler = None
    else:
        vectorize_handler = None
        logger.info("rag_disabled_chat_service_url_not_set")

    # ── Event Handlers 訂閱 ────────────────────────────────────────────────
    article_scraped_handler = ArticleScrapedHandler(
        use_case=process_article_uc,
        pipeline_stats=pipeline_stats,
        event_bus=event_bus,
    )
    # ArticleScrapedEvent: create article.pipeline parent span, then article.scraped.handle child
    event_bus.subscribe(ArticleScrapedEvent, with_article_pipeline_span(
        article_scraped_handler.handle, event_bus, _tracer,
        SpanName.ARTICLE_PIPELINE, SpanName.ARTICLE_SCRAPED_HANDLE))

    # Subsequent handlers: use with_span_deferred only — they fire as deferred events
    # still within the article.pipeline span context, becoming its direct children.
    article_processed_handler = ArticleProcessedHandler(use_case=analyze_article_uc, event_bus=event_bus)
    event_bus.subscribe(ArticleProcessedEvent, with_span_deferred(
        SpanName.ARTICLE_PROCESSED_HANDLE, article_processed_handler.handle, event_bus, _tracer))

    if vectorize_handler is not None:
        event_bus.subscribe(ArticleProcessedEvent, vectorize_handler.handle)

    failed_task_handler = FailedTaskPersistenceHandler(failed_task_repository=failed_task_repo)
    event_bus.subscribe(AnalysisFailedEvent, with_span(
        SpanName.ANALYSIS_FAILED_HANDLE, failed_task_handler.handle, _tracer))
    event_bus.subscribe(TagNormalizationFailedEvent, with_span(
        SpanName.TAG_NORMALIZATION_FAILED_HANDLE, failed_task_handler.handle, _tracer))
    event_bus.subscribe(TranslationFailedEvent, with_span(
        SpanName.TRANSLATION_FAILED_HANDLE, failed_task_handler.handle, _tracer))

    tag_normalization_handler = TagNormalizationHandler(
        use_case=normalize_tags_uc,
        event_bus=event_bus,
        session=session,
    )
    event_bus.subscribe(AnalysisCompletedEvent, with_span_deferred(
        SpanName.TAG_NORMALIZATION_HANDLE, tag_normalization_handler.handle, event_bus, _tracer))

    analysis_completed_handler = AnalysisCompletedHandler(
        translate_article_uc=translate_article_uc,
        translate_tags_uc=translate_tags_uc,
        translate_body_uc=translate_body_uc,
        analyses_translation_repo=analyses_translation_repo,
        event_bus=event_bus,
        target_languages=TRANSLATION_LANGUAGES,
    )
    event_bus.subscribe(TagNormalizationCompletedEvent, with_span_deferred(
        SpanName.ANALYSIS_COMPLETED_HANDLE, analysis_completed_handler.handle, event_bus, _tracer))

    # ── Observability handlers — subscribe to PipelineCompletedEvent ────────
    otel_handler = OtelMetricsHandler()
    event_bus.subscribe(PipelineCompletedEvent, with_span(
        SpanName.PIPELINE_COMPLETED_HANDLE, otel_handler.handle, _tracer))

    notification_handler = build_notification_handler()
    event_bus.subscribe(PipelineCompletedEvent, with_span(
        SpanName.PIPELINE_COMPLETED_NOTIFY, notification_handler.handle, _tracer))

    # ── Collection Pipeline ─────────────────────────────────────────────────
    from datetime import datetime, timezone
    from src.infrastructure.collection.executor import ScrapeExecutor
    from src.modules.collection.domain.entities import FailedTask

    # TODO: once DiscoverFailedEvent + DiscoverFailedHandler are merged from the
    # feature branch, replace this direct repo.save() with:
    #   event_bus.publish(DiscoverFailedEvent(source=task.setting.source, ...))
    def _on_discover_failed(task, exc) -> None:
        """Record a discover-phase failure as a FailedTask and emit an OTel error span."""
        with _tracer.start_as_current_span("scraper.discover_failed") as span:
            span.set_attribute("task.type", "arxiv_discover")
            span.set_attribute("task.exception_type", type(exc).__name__)
            source = getattr(getattr(task, "setting", None), "source", "unknown")
            span.set_attribute("article.source", source)
            span.set_status(_StatusCode.ERROR, type(exc).__name__)
            failed = FailedTask(
                task_type="arxiv_discover",
                exception_type=type(exc).__name__,
                exception_message=str(exc),
                failed_at=datetime.now(timezone.utc),
            )
            try:
                failed_task_repo.save(failed)
                logger.info("arxiv_discover_failure_recorded", source=source)
            except Exception as e:
                logger.error("failed_task_save_error", source=source, error=str(e))

    executor = ScrapeExecutor(on_discover_failed=_on_discover_failed)

    scraper_factory = ConcreteScraperFactory(http_client=get_default_client())
    pipeline = CollectionPipeline(
        setting_repo=setting_repo,
        scraper_factory=scraper_factory,
        event_bus=event_bus,
        pipeline_stats=pipeline_stats,
        article_repo=article_repo,
        executor=executor,
    )

    logger.info(
        "bootstrap_complete",
        llm_providers=llm_provider_names,
        llm_provider_count=len(llm_provider_names),
        translation_languages=list(TRANSLATION_LANGUAGES) if TRANSLATION_LANGUAGES else [],
    )
    return pipeline, pipeline_stats


# ---------------------------------------------------------------------------
# Translation Pipeline：翻譯流程的依賴組裝
# ---------------------------------------------------------------------------

def build_translation_pipeline():
    """
    組裝翻譯 pipeline。

    回傳翻譯相關服務，可用於定時翻譯任務。
    """
    from src.infrastructure.persistence.intelligence import SqlAlchemyAnalysesTranslationRepository, SqlAlchemyTagTranslationRepository
    from src.infrastructure.persistence.intelligence.article_translation_repo_impl import SqlAlchemyArticleTranslationRepository
    from src.modules.intelligence.application.use_cases import TranslateArticleUseCase, TranslateTagsUseCase
    from src.modules.intelligence.application.use_cases.translate_article_body import TranslateArticleBodyUseCase
    from src.infrastructure.intelligence.prompt.prompt_factory import ConcretePromptFactory

    # ── DB 初始化 ──────────────────────────────────────────────────────────
    init_db()
    session = get_session()

    # ── Repositories ───────────────────────────────────────────────────────
    analyses_translation_repo = SqlAlchemyAnalysesTranslationRepository(session=session)
    tag_translation_repo = SqlAlchemyTagTranslationRepository(session=session)
    article_translation_repo = SqlAlchemyArticleTranslationRepository(session=session)

    # ── LLM Service ────────────────────────────────────────────────────────
    llm_service, _, _provider_names = build_llm_service(session)

    # ── Prompt Factory ────────────────────────────────────────────────────
    prompt_factory = ConcretePromptFactory()

    # ── Use Cases ──────────────────────────────────────────────────────────
    translate_article_uc = TranslateArticleUseCase(
        llm_service=llm_service,
        translation_repository=analyses_translation_repo,
        prompt=prompt_factory.article_translation_prompt(),
    )
    translate_tags_uc = TranslateTagsUseCase(
        llm_service=llm_service,
        tag_translation_repository=tag_translation_repo,
        tag_prompt=prompt_factory.tag_translation_prompt(),
        group_prompt=prompt_factory.group_translation_prompt(),
    )
    translate_body_uc = TranslateArticleBodyUseCase(
        llm_service=llm_service,
        translation_repository=article_translation_repo,
        prompt=prompt_factory.article_body_translation_prompt(),
    )

    logger.info("translation_bootstrap_complete")
    return {
        "use_case": translate_article_uc,
        "tag_use_case": translate_tags_uc,
        "body_use_case": translate_body_uc,
        "session": session,
        "analyses_translation_repository": analyses_translation_repo,
        "tag_translation_repository": tag_translation_repo,
        "article_translation_repository": article_translation_repo,
    }