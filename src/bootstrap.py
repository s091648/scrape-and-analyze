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
# RAG 層: 從 env vars 建立 RagSdkIngestionService
# ---------------------------------------------------------------------------

def build_rag_ingestion_service():
    """Build RagSdkIngestionService from environment variables.

    Returns (rag_service, rag_config_failed_event).
    Either or both may be None when RAG is disabled or misconfigured.
    rag_config_failed_event must be published AFTER all event subscriptions are registered.
    """
    from src.modules.intelligence.application.events import RagConfigFailedEvent
    from src.config.settings import missing_rag_config
    from src.infrastructure.shared.logging import get_correlation_id

    _rag_missing = missing_rag_config()
    if _rag_missing:
        event = RagConfigFailedEvent(
            exception_type="MissingConfiguration",
            exception_message=f"RAG disabled — missing required vars: {', '.join(_rag_missing)}",
            context={"missing_vars": _rag_missing},
            correlation_id=get_correlation_id() or None,
        )
        logger.warning("rag_config_incomplete_rag_disabled", missing_vars=_rag_missing)
        return None, event

    try:
        from chatbot_plugin_sdk import (
            IngestProcessor,
            SyncPgBackend,
            DatabaseConfig,
            NotConfiguredError,
            build_dense_provider,
            build_sparse_provider,
        )
    except ModuleNotFoundError:
        logger.info("rag_disabled_sdk_not_installed")
        return None, None

    try:
        from src.config.settings import (
            VECTOR_DB_NAME, VECTOR_DB_USER, VECTOR_DB_PASSWORD,
            VECTOR_DB_HOST, VECTOR_DB_PORT, VECTOR_DB_SCHEMA,
            VECTOR_DB_ARTICLES_TABLE, VECTOR_DB_CHUNKS_TABLE,
            RAG_DENSE_PROVIDER, RAG_DENSE_MODEL, RAG_DENSE_DIMENSION,
            RAG_DENSE_API_KEY_ENV, RAG_DENSE_ENDPOINT_URL,
            RAG_DENSE_RPM, RAG_DENSE_TPM, RAG_DENSE_RPD,
            RAG_SPARSE_PROVIDER, RAG_SPARSE_MODEL, RAG_SPARSE_DIMENSION,
            RAG_SPARSE_ENDPOINT_URL, RAG_SPARSE_RPM, RAG_SPARSE_TPM, RAG_SPARSE_RPD,
            RAG_EMBED_BATCH_SIZE, RAG_CHUNK_SIZE, RAG_CHUNK_OVERLAP,
        )
        from src.infrastructure.intelligence.vector_store.rag_sdk_ingestion_impl import RagSdkIngestionService

        dense_provider = build_dense_provider({
            "provider_type": RAG_DENSE_PROVIDER,
            "model": RAG_DENSE_MODEL,
            "dimension": RAG_DENSE_DIMENSION,
            "api_key": os.environ.get(RAG_DENSE_API_KEY_ENV, "") if RAG_DENSE_API_KEY_ENV else "",
            "endpoint_url": RAG_DENSE_ENDPOINT_URL,
            "rpm": RAG_DENSE_RPM,
            "tpm": RAG_DENSE_TPM,
            "rpd": RAG_DENSE_RPD,
        }) if RAG_DENSE_PROVIDER else None

        sparse_provider = build_sparse_provider({
            "provider_type": RAG_SPARSE_PROVIDER,
            "model": RAG_SPARSE_MODEL,
            "dimension": RAG_SPARSE_DIMENSION,
            "endpoint_url": RAG_SPARSE_ENDPOINT_URL,
            "rpm": RAG_SPARSE_RPM,
            "tpm": RAG_SPARSE_TPM,
            "rpd": RAG_SPARSE_RPD,
        }) if RAG_SPARSE_PROVIDER else None

        backend = SyncPgBackend(DatabaseConfig(
            dbname=VECTOR_DB_NAME,
            user=VECTOR_DB_USER,
            password=VECTOR_DB_PASSWORD,
            host=VECTOR_DB_HOST,
            port=VECTOR_DB_PORT,
            schema=VECTOR_DB_SCHEMA,
            articles_table=VECTOR_DB_ARTICLES_TABLE,
            chunks_table=VECTOR_DB_CHUNKS_TABLE,
        ))
        processor = IngestProcessor()
        processor.configure(
            backend=backend,
            dense=dense_provider,
            sparse=sparse_provider,
            embed_batch_size=RAG_EMBED_BATCH_SIZE,
            chunk_size=RAG_CHUNK_SIZE,
            chunk_overlap=RAG_CHUNK_OVERLAP,
        )

        rag_service = RagSdkIngestionService(processor)
        logger.info(
            "rag_ingestion_initialized",
            dense=RAG_DENSE_PROVIDER or "disabled",
            sparse=RAG_SPARSE_PROVIDER or "disabled",
        )
        return rag_service, None

    except NotConfiguredError as exc:
        from src.modules.intelligence.application.events import RagConfigFailedEvent
        from src.infrastructure.shared.logging import get_correlation_id
        event = RagConfigFailedEvent(
            exception_type="NotConfiguredError",
            exception_message=str(exc),
            context={},
            correlation_id=get_correlation_id() or None,
        )
        logger.warning("rag_ingestion_not_configured_disabling", error=str(exc))
        return None, event

    except Exception:
        logger.exception("rag_ingestion_init_failed_disabling")
        return None, None


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
    from src.infrastructure.persistence.collection.scraper_setting_repo_impl import SqlAlchemyScraperSettingRepository
    from src.infrastructure.persistence.collection.article_metrics_repo_impl import SqlAlchemyArticleMetricsRepository
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
    from src.modules.intelligence.application.events import (
        AnalysisFailedEvent, AnalysisCompletedEvent,
        TagNormalizationCompletedEvent, TagNormalizationFailedEvent,
        TranslationFailedEvent, RagIngestionFailedEvent, RagConfigFailedEvent,
    )
    from src.shared.application.events import ArticleProcessedEvent
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
    topic_repo = SqlAlchemyTopicRepository(session=session)
    failed_task_repo = SqlAlchemyFailedTaskRepository(session=session)
    tag_repo = SqlAlchemyTagRepository(session=session)
    tag_group_def_repo = SqlAlchemyTagGroupDefinitionRepository(session=session)
    article_translation_repo = SqlAlchemyArticleTranslationRepository(session=session)
    article_metrics_repo = SqlAlchemyArticleMetricsRepository(session=session)

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
        article_metrics_repo=article_metrics_repo,
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

    # ── RAG Ingestion Setup ────────────────────────────────────────────────
    _rag_ingestion_service, _rag_config_failed_event = build_rag_ingestion_service()
    rag_ingestion_handler = None
    if _rag_ingestion_service is not None:
        from src.modules.intelligence.application.use_cases.ingest_article_for_rag import IngestArticleForRagUseCase
        from src.modules.intelligence.application.event_handlers.rag_ingestion_handler import RagIngestionHandler
        _ingest_for_rag_uc = IngestArticleForRagUseCase(_rag_ingestion_service)
        rag_ingestion_handler = RagIngestionHandler(_ingest_for_rag_uc, event_bus)

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

    if rag_ingestion_handler is not None:
        event_bus.subscribe(ArticleProcessedEvent, rag_ingestion_handler.handle)

    failed_task_handler = FailedTaskPersistenceHandler(failed_task_repository=failed_task_repo)
    event_bus.subscribe(AnalysisFailedEvent, with_span(
        SpanName.ANALYSIS_FAILED_HANDLE, failed_task_handler.handle, _tracer))
    event_bus.subscribe(TagNormalizationFailedEvent, with_span(
        SpanName.TAG_NORMALIZATION_FAILED_HANDLE, failed_task_handler.handle, _tracer))
    event_bus.subscribe(TranslationFailedEvent, with_span(
        SpanName.TRANSLATION_FAILED_HANDLE, failed_task_handler.handle, _tracer))
    event_bus.subscribe(RagIngestionFailedEvent, with_span(
        SpanName.RAG_INGESTION_FAILED_HANDLE, failed_task_handler.handle, _tracer))
    event_bus.subscribe(RagConfigFailedEvent, with_span(
        SpanName.RAG_CONFIG_FAILED_HANDLE, failed_task_handler.handle, _tracer))

    # Publish deferred startup failures after all subscriptions are registered
    if _rag_config_failed_event is not None:
        event_bus.publish(_rag_config_failed_event)

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
# Weekly Report Pipeline
# ---------------------------------------------------------------------------

def build_weekly_pipeline():
    """Assemble WeeklyReportPipeline (topic resolution + GenerateWeeklyReportUseCase) from env vars and DB."""
    from src.infrastructure.persistence.database import get_session, init_db
    from src.infrastructure.persistence.intelligence.weekly_report_repo_impl import WeeklyReportRepoImpl
    from src.infrastructure.persistence.intelligence.weekly_report_translation_repo_impl import SqlAlchemyWeeklyReportTranslationRepository
    from src.infrastructure.persistence.shared.topic_repo_impl import SqlAlchemyTopicRepository
    from src.infrastructure.storage.r2_blob_storage import R2BlobStorageService
    from src.infrastructure.intelligence.notifications.weekly_report_email_notifier import WeeklyReportEmailNotifier
    from src.infrastructure.intelligence.notifications.weekly_report_telegram_notifier import WeeklyReportTelegramNotifier
    from src.infrastructure.intelligence.weekly_report_pipeline import WeeklyReportPipeline
    from src.infrastructure.intelligence.prompt.prompt_factory import ConcretePromptFactory
    from src.modules.intelligence.application.use_cases.generate_weekly_report import GenerateWeeklyReportUseCase

    init_db()
    session = get_session()

    llm_service, _, _ = build_llm_service(session)

    report_repo = WeeklyReportRepoImpl(session=session)
    weekly_report_translation_repo = SqlAlchemyWeeklyReportTranslationRepository(session=session)

    # Multimodal provider: requires an active 'multimodal' LlmProvider in DB.
    # Provider name selects between Gemini Imagen and HuggingFace (free-tier alternative).
    from shared.llm_provider import load_active_multimodal_provider
    multimodal_cfg = load_active_multimodal_provider(session)
    if not multimodal_cfg:
        raise ValueError("No active multimodal provider found in DB — add one via the admin UI")

    provider_name = multimodal_cfg["name"]
    api_key = os.environ.get(multimodal_cfg["api_key_env"], "")
    if provider_name == "huggingface":
        from src.infrastructure.intelligence.image.huggingface_image_provider import HuggingFaceImageProvider
        image_service = HuggingFaceImageProvider(model=multimodal_cfg["model"], api_key=api_key)
    else:
        from src.infrastructure.intelligence.image.gemini_imagen_provider import GeminiImagenProvider
        image_service = GeminiImagenProvider(model=multimodal_cfg["model"], api_key=api_key)

    blob_storage = R2BlobStorageService.from_env()

    from src.config.settings import FRONTEND_ORIGIN, RESEND_API_KEY, RESEND_FROM_EMAIL, TELEGRAM_BOT_TOKEN, TRANSLATION_LANGUAGES
    from src.shared.infrastructure.notifications import TelegramNotifierClient

    # Every notification CTA links back to FRONTEND_ORIGIN — without it (or with
    # the placeholder default), links go nowhere useful. Warn loudly at startup
    # rather than letting it fail silently in a sent message.
    if not FRONTEND_ORIGIN or FRONTEND_ORIGIN == "https://example.com":
        logger.warning("frontend_origin_not_configured", frontend_origin=FRONTEND_ORIGIN)

    resend_key = RESEND_API_KEY
    from_email = RESEND_FROM_EMAIL
    email_notifier = WeeklyReportEmailNotifier(session=session, api_key=resend_key, from_email=from_email, site_url=FRONTEND_ORIGIN) if resend_key else None

    telegram_notifier = None
    if TELEGRAM_BOT_TOKEN:
        telegram_client = TelegramNotifierClient(bot_token=TELEGRAM_BOT_TOKEN)
        telegram_notifier = WeeklyReportTelegramNotifier(session=session, notifier=telegram_client, site_url=FRONTEND_ORIGIN)

    # Weekly report i18n: title + summary_text are produced in English, then
    # translated into each language in TRANSLATION_LANGUAGES via the same
    # prompt factory path used by every other translation use case.
    prompt_factory = ConcretePromptFactory()

    generate_use_case = GenerateWeeklyReportUseCase(
        report_repo=report_repo,
        llm_service=llm_service,
        image_service=image_service,
        blob_storage=blob_storage,
        translation_repository=weekly_report_translation_repo,
        translation_prompt=prompt_factory.weekly_report_translation_prompt(),
        email_notifier=email_notifier,
        telegram_notifier=telegram_notifier,
        translation_languages=TRANSLATION_LANGUAGES,
    )
    topic_repository = SqlAlchemyTopicRepository(session=session)

    return WeeklyReportPipeline(topic_repository=topic_repository, generate_use_case=generate_use_case), session


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