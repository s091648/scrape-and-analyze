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
# 024-async-pipeline-refactor: async sibling of build_llm_service(), not a
# replacement — build_llm_service() stays untouched, still shared with
# build_weekly_pipeline()/build_translation_pipeline() (out of scope; see
# specs/024-async-pipeline-refactor/research.md item 3).
#
# Deliberately a plain `def`, not `async def`: this only runs once, at
# pipeline-wiring time, before any per-article concurrency starts — the
# provider-config read (load_active_providers/load_active_embedding_providers)
# is a one-time synchronous DB read using the same sync `session`
# build_collection_pipeline() already has for its startup wiring. There is no
# concurrent contention to protect against yet at this point in the run, so
# reusing the existing sync config-loader functions as-is (rather than writing
# async siblings for them too) is safe and avoids needless duplication. Only
# the *objects this function constructs and returns* (providers, service) are
# async — construction itself is not.
# ---------------------------------------------------------------------------

def build_async_llm_service(session):
    """Build (AsyncResilientLLMService, AsyncResilientEmbeddingService) from
    the same DB provider config build_llm_service() reads, using the async
    provider/service classes instead."""
    from shared.domain.exceptions import ValidationError
    from shared.llm_provider import load_active_providers, load_active_embedding_providers
    from src.infrastructure.intelligence.llm.resilient_llm_service import (
        AsyncResilientLLMService, AsyncProviderHandler,
        AsyncResilientEmbeddingService, AsyncEmbeddingProviderHandler,
    )
    from src.infrastructure.intelligence.llm.embedding import AsyncGeminiEmbeddingProvider
    from src.infrastructure.intelligence.llm.providers import AsyncClaudeProvider, AsyncGeminiProvider, AsyncOpenRouterProvider
    from src.infrastructure.intelligence.llm.rate_limit import SlidingWindowStrategy, NoOpStrategy

    def _make_strategy(cfg):
        s = cfg.get('strategy', {})
        if s.get('type') == 'sliding_window':
            return SlidingWindowStrategy(rpm=s['rpm'], tpm=s['tpm'], rpd=s['rpd'])
        return NoOpStrategy()

    handlers: List[AsyncProviderHandler] = []
    for cfg in load_active_providers(session):
        name = cfg['name']
        api_key = os.environ.get(cfg['api_key_env'], '')
        if name == 'claude':
            provider = AsyncClaudeProvider(api_key=api_key, model=cfg['model'])
        elif name == 'gemini':
            provider = AsyncGeminiProvider(api_key=api_key, model=cfg['model'])
        elif name == 'openrouter':
            provider = AsyncOpenRouterProvider(api_key=api_key, model=cfg['model'])
        else:
            logger.warning("unknown_provider_skipped", name=name)
            continue
        handlers.append(AsyncProviderHandler(
            provider=provider,
            strategy=_make_strategy(cfg),
            priority=cfg['priority'],
            name=name,
        ))
        logger.info("async_llm_provider_loaded", name=name, model=cfg['model'], priority=cfg['priority'])

    if not handlers:
        raise ValidationError("llm_providers table has no active LLM providers")

    emb_handlers: List[AsyncEmbeddingProviderHandler] = []
    for cfg in load_active_embedding_providers(session):
        name = cfg['name']
        api_key = os.environ.get(cfg['api_key_env'], '')
        if name == 'gemini':
            provider = AsyncGeminiEmbeddingProvider(api_key=api_key, model=cfg['model'])
        else:
            logger.warning("unknown_embedding_provider_skipped", name=name)
            continue
        emb_handlers.append(AsyncEmbeddingProviderHandler(
            provider=provider,
            strategy=_make_strategy(cfg),
            priority=cfg['priority'],
            name=name,
        ))

    if not emb_handlers:
        raise ValidationError("llm_providers table has no active embedding providers")

    provider_names = [h.name for h in handlers]
    return AsyncResilientLLMService(handlers=handlers), AsyncResilientEmbeddingService(handlers=emb_handlers), provider_names


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
            RAG_DENSE_RPM, RAG_DENSE_TPM, RAG_DENSE_RPD, RAG_DENSE_SPLIT_BATCH_ON_TPM,
            RAG_SPARSE_PROVIDER, RAG_SPARSE_MODEL, RAG_SPARSE_DIMENSION,
            RAG_SPARSE_ENDPOINT_URL, RAG_SPARSE_RPM, RAG_SPARSE_TPM, RAG_SPARSE_RPD, RAG_SPARSE_TIMEOUT,
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
            "split_batch_on_tpm": RAG_DENSE_SPLIT_BATCH_ON_TPM,
        }) if RAG_DENSE_PROVIDER else None

        sparse_provider = build_sparse_provider({
            "provider_type": RAG_SPARSE_PROVIDER,
            "model": RAG_SPARSE_MODEL,
            "dimension": RAG_SPARSE_DIMENSION,
            "endpoint_url": RAG_SPARSE_ENDPOINT_URL,
            "rpm": RAG_SPARSE_RPM,
            "tpm": RAG_SPARSE_TPM,
            "rpd": RAG_SPARSE_RPD,
            "timeout": RAG_SPARSE_TIMEOUT,
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
# 024-async-pipeline-refactor: async sibling of build_rag_ingestion_service(),
# not a replacement — that function stays untouched, still used only by the
# out-of-scope build_rag_backfill_pipeline() (bootstrap.py:872). See
# specs/024-async-pipeline-refactor/research.md item 3.
# ---------------------------------------------------------------------------

def _build_rag_dense_sparse_providers():
    """Dense/sparse embedding-provider construction shared by
    build_rag_ingestion_service() and build_async_rag_ingestion_service() —
    identical either way, only the backend/service wiring around it differs
    between sync and async."""
    from chatbot_plugin_sdk import build_dense_provider, build_sparse_provider
    from src.config.settings import (
        RAG_DENSE_PROVIDER, RAG_DENSE_MODEL, RAG_DENSE_DIMENSION,
        RAG_DENSE_API_KEY_ENV, RAG_DENSE_ENDPOINT_URL,
        RAG_DENSE_RPM, RAG_DENSE_TPM, RAG_DENSE_RPD, RAG_DENSE_SPLIT_BATCH_ON_TPM,
        RAG_SPARSE_PROVIDER, RAG_SPARSE_MODEL, RAG_SPARSE_DIMENSION,
        RAG_SPARSE_ENDPOINT_URL, RAG_SPARSE_RPM, RAG_SPARSE_TPM, RAG_SPARSE_RPD, RAG_SPARSE_TIMEOUT,
    )

    dense_provider = build_dense_provider({
        "provider_type": RAG_DENSE_PROVIDER,
        "model": RAG_DENSE_MODEL,
        "dimension": RAG_DENSE_DIMENSION,
        "api_key": os.environ.get(RAG_DENSE_API_KEY_ENV, "") if RAG_DENSE_API_KEY_ENV else "",
        "endpoint_url": RAG_DENSE_ENDPOINT_URL,
        "rpm": RAG_DENSE_RPM,
        "tpm": RAG_DENSE_TPM,
        "rpd": RAG_DENSE_RPD,
        "split_batch_on_tpm": RAG_DENSE_SPLIT_BATCH_ON_TPM,
    }) if RAG_DENSE_PROVIDER else None

    sparse_provider = build_sparse_provider({
        "provider_type": RAG_SPARSE_PROVIDER,
        "model": RAG_SPARSE_MODEL,
        "dimension": RAG_SPARSE_DIMENSION,
        "endpoint_url": RAG_SPARSE_ENDPOINT_URL,
        "rpm": RAG_SPARSE_RPM,
        "tpm": RAG_SPARSE_TPM,
        "rpd": RAG_SPARSE_RPD,
        "timeout": RAG_SPARSE_TIMEOUT,
    }) if RAG_SPARSE_PROVIDER else None

    return dense_provider, sparse_provider


def build_async_rag_ingestion_service():
    """Async sibling of build_rag_ingestion_service() — same shape, using
    AsyncPgBackend + AsyncRagSdkIngestionService instead of SyncPgBackend +
    RagSdkIngestionService. Returns (async_rag_service, rag_config_failed_event),
    same contract as the sync version."""
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
            AsyncPgBackend,
            DatabaseConfig,
            NotConfiguredError,
        )
    except ModuleNotFoundError:
        logger.info("rag_disabled_sdk_not_installed")
        return None, None

    try:
        from src.config.settings import (
            VECTOR_DB_NAME, VECTOR_DB_USER, VECTOR_DB_PASSWORD,
            VECTOR_DB_HOST, VECTOR_DB_PORT, VECTOR_DB_SCHEMA,
            VECTOR_DB_ARTICLES_TABLE, VECTOR_DB_CHUNKS_TABLE,
            RAG_DENSE_PROVIDER, RAG_SPARSE_PROVIDER,
            RAG_EMBED_BATCH_SIZE, RAG_CHUNK_SIZE, RAG_CHUNK_OVERLAP,
        )
        from src.infrastructure.intelligence.vector_store.rag_sdk_ingestion_impl import AsyncRagSdkIngestionService

        dense_provider, sparse_provider = _build_rag_dense_sparse_providers()

        backend = AsyncPgBackend(DatabaseConfig(
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

        rag_service = AsyncRagSdkIngestionService(processor)
        logger.info(
            "async_rag_ingestion_initialized",
            dense=RAG_DENSE_PROVIDER or "disabled",
            sparse=RAG_SPARSE_PROVIDER or "disabled",
        )
        return rag_service, None

    except NotConfiguredError as exc:
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

async def build_collection_pipeline(jitter_seconds: float | None = None):
    """
    組裝完整的 collection → intelligence pipeline（024-async-pipeline-refactor:
    async def — awaited from main.py via asyncio.run()）。

    jitter_seconds: main.py's pre-run startup-jitter sleep duration (None if skipped via
    RUN_IMMEDIATELY) — carried into CollectionPipeline so its PipelineCompletedEvent's
    execution meta can report it alongside app_env (020-redis-caching-layer follow-up).

    回傳 CollectionPipeline 實例，呼叫 await .run() 即可執行一輪抓取與分析。

    Session 策略（024-async-pipeline-refactor):
      discover/fetch/batched-dedup 階段（FR-003，行為不變）與一次性的
      provider-config 讀取，仍然共用單一同步 session（`get_session()`）——
      這個階段本來就不併發，不需要 async session。從 publish 之後開始，
      每篇文章的 asyncio.Task 各自透過 `get_async_sessionmaker()` 開自己的
      AsyncSession（research.md item 2），從不跨 task 共用。
    """
    from src.infrastructure.persistence.database import get_async_sessionmaker
    from src.infrastructure.persistence.shared.article_repo_impl import SqlAlchemyArticleRepository
    from src.infrastructure.persistence.shared.failed_task_repo_impl import SqlAlchemyFailedTaskRepository
    from src.infrastructure.persistence.collection.scraper_setting_repo_impl import SqlAlchemyScraperSettingRepository
    from src.infrastructure.shared.events.in_memory_event_bus import AsyncInMemoryEventBus
    from src.infrastructure.collection.scrapers.scraper_factory import ConcreteScraperFactory
    from src.infrastructure.collection.collection_pipeline import CollectionPipeline
    from src.infrastructure.collection.handlers import OtelMetricsHandler
    from src.infrastructure.shared.notifications import build_async_notification_handler
    from src.infrastructure.collection.notifications import PipelineCompletedMessageBuilder
    from src.modules.collection.application.event_handlers import CacheInvalidationHandler, CacheWarmupHandler
    from shared.cache import RedisCacheGateway
    from src.config.settings import CACHE_REDIS_URL, APP_ENV
    from src.config.settings import SEARCH_INDEX_REDIS_URL, SEARCH_MIN_DOC_FREQ
    from shared.search_index import RedisSearchIndexGateway
    from src.infrastructure.persistence.intelligence import SqlAlchemySearchTermRepository
    from src.modules.search.application.use_cases import RebuildSearchIndexUseCase
    from src.modules.search.application.event_handlers import SearchIndexRebuildHandler
    from src.infrastructure.shared.http import get_default_client
    from src.infrastructure.intelligence.prompt.prompt_factory import ConcretePromptFactory

    # ── Async repository adapters (new siblings — research.md item 3) ──────
    from src.infrastructure.persistence.shared.article_async_repo_impl import AsyncSqlAlchemyArticleRepository
    from src.infrastructure.persistence.shared.topic_async_repo_impl import AsyncSqlAlchemyTopicRepository
    from src.infrastructure.persistence.shared.failed_task_async_repo_impl import AsyncSqlAlchemyFailedTaskRepository
    from src.infrastructure.persistence.intelligence.analysis_async_repo_impl import AsyncSqlAlchemyAnalysisRepository
    from src.infrastructure.persistence.intelligence.analyses_translation_async_repo_impl import AsyncSqlAlchemyAnalysesTranslationRepository
    from src.infrastructure.persistence.intelligence.tag_translation_async_repo_impl import AsyncSqlAlchemyTagTranslationRepository
    from src.infrastructure.persistence.intelligence.article_translation_async_repo_impl import AsyncSqlAlchemyArticleTranslationRepository
    from src.infrastructure.persistence.intelligence.tag_async_repo_impl import AsyncSqlAlchemyTagRepository
    from src.infrastructure.persistence.intelligence.tag_group_definition_async_repo_impl import AsyncSqlAlchemyTagGroupDefinitionRepository
    from src.infrastructure.persistence.collection.article_metrics_async_repo_impl import AsyncSqlAlchemyArticleMetricsRepository

    from src.modules.collection.domain.services import AsyncDedupService
    from src.modules.collection.application.use_cases import ProcessScrapedArticleUseCase, PipelineStats
    from src.modules.collection.application.events import ArticleScrapedEvent, PipelineCompletedEvent, TextPipelineCompletedEvent
    from src.modules.collection.application.event_handlers import ArticleScrapedHandler
    from src.modules.intelligence.application.use_cases import AnalyzeArticleUseCase, NormalizeTagsUseCase
    from src.modules.intelligence.application.use_cases.translate_article import AsyncTranslateArticleUseCase
    from src.modules.intelligence.application.use_cases.translate_tags import AsyncTranslateTagsUseCase
    from src.modules.intelligence.application.use_cases.translate_article_body import AsyncTranslateArticleBodyUseCase
    from src.modules.intelligence.application.event_handlers import ArticleProcessedHandler, AnalysisCompletedHandler
    from src.modules.intelligence.application.event_handlers.tag_normalization_handler import TagNormalizationHandler
    from src.modules.intelligence.application.event_handlers.failed_task_persistence_handler import FailedTaskPersistenceHandler
    from src.modules.intelligence.application.event_handlers.rag_ingestion_handler import AsyncRagIngestionHandler
    from src.modules.intelligence.application.use_cases.ingest_article_for_rag import AsyncIngestArticleForRagUseCase
    from src.modules.intelligence.application.events import (
        AnalysisFailedEvent, AnalysisCompletedEvent,
        TagNormalizationCompletedEvent, TagNormalizationFailedEvent,
        TranslationFailedEvent, RagIngestionFailedEvent,
    )
    from src.shared.application.events import ArticleProcessedEvent
    from src.config.settings import TRANSLATION_LANGUAGES

    # ── DB 初始化 ──────────────────────────────────────────────────────────
    init_db()
    session = get_session()
    async_sessionmaker_factory = get_async_sessionmaker()

    # ── Upstream (sync, still-batched — FR-003) repositories ────────────────
    article_repo = SqlAlchemyArticleRepository(session=session)  # find_analyzed_url_hashes only
    setting_repo = SqlAlchemyScraperSettingRepository(session=session)
    failed_task_repo_sync = SqlAlchemyFailedTaskRepository(session=session)  # discover-phase failures only

    # ── Shared, task-safe services (built once, reused by every article task) ──
    llm_service, embedding_service, llm_provider_names = build_async_llm_service(session)
    prompt_factory = ConcretePromptFactory()
    pipeline_stats = PipelineStats()

    # ── RAG (async) ──────────────────────────────────────────────────────────
    _rag_ingestion_service, _rag_config_failed_event = build_async_rag_ingestion_service()
    rag_enabled = _rag_ingestion_service is not None

    # ── Run-level event bus — ONLY the two barrier events are published here.
    # Every per-article event (ArticleScrapedEvent..TagNormalizationCompletedEvent)
    # goes through a fresh bus built by article_downstream_builder below, bound
    # to that article's own AsyncSession. ─────────────────────────────────────
    event_bus = AsyncInMemoryEventBus()

    if _rag_config_failed_event is not None:
        async with async_sessionmaker_factory() as startup_session:
            startup_failed_task_repo = AsyncSqlAlchemyFailedTaskRepository(startup_session)
            startup_failed_task_handler = FailedTaskPersistenceHandler(failed_task_repository=startup_failed_task_repo)
            await startup_failed_task_handler.handle(_rag_config_failed_event)

    # ── Per-article downstream wiring (closure over the shared services above) ──
    # Called once per article, given that article's own fresh AsyncSession and
    # fresh AsyncInMemoryEventBus — constructs and subscribes everything needed
    # for that one article's text-stage chain. dispatch_rag is
    # CollectionPipeline._dispatch_rag, subscribed here (not awaited) so RAG
    # never blocks this chain (FR-002).
    async def article_downstream_builder(article_session, bus, dispatch_rag) -> None:
        article_repo_a = AsyncSqlAlchemyArticleRepository(article_session)
        article_metrics_repo_a = AsyncSqlAlchemyArticleMetricsRepository(article_session)
        analysis_repo_a = AsyncSqlAlchemyAnalysisRepository(article_session)
        analyses_translation_repo_a = AsyncSqlAlchemyAnalysesTranslationRepository(article_session)
        tag_translation_repo_a = AsyncSqlAlchemyTagTranslationRepository(article_session)
        article_translation_repo_a = AsyncSqlAlchemyArticleTranslationRepository(article_session)
        tag_repo_a = AsyncSqlAlchemyTagRepository(article_session)
        tag_group_def_repo_a = AsyncSqlAlchemyTagGroupDefinitionRepository(article_session)
        topic_repo_a = AsyncSqlAlchemyTopicRepository(article_session)
        failed_task_repo_a = AsyncSqlAlchemyFailedTaskRepository(article_session)

        dedup_service_a = AsyncDedupService(article_repo=article_repo_a)
        process_article_uc = ProcessScrapedArticleUseCase(
            article_repo=article_repo_a,
            dedup_service=dedup_service_a,
            article_metrics_repo=article_metrics_repo_a,
        )
        analyze_article_uc = AnalyzeArticleUseCase(
            llm_service=llm_service,
            analysis_repository=analysis_repo_a,
            topic_repository=topic_repo_a,
            tag_group_definition_repository=tag_group_def_repo_a,
            prompt=prompt_factory.analysis_prompt(),
            embedding_service=embedding_service,
        )
        translate_article_uc = AsyncTranslateArticleUseCase(
            llm_service=llm_service,
            translation_repository=analyses_translation_repo_a,
            prompt=prompt_factory.article_translation_prompt(),
        )
        translate_tags_uc = AsyncTranslateTagsUseCase(
            llm_service=llm_service,
            tag_translation_repository=tag_translation_repo_a,
            tag_prompt=prompt_factory.tag_translation_prompt(),
            group_prompt=prompt_factory.group_translation_prompt(),
        )
        translate_body_uc = AsyncTranslateArticleBodyUseCase(
            llm_service=llm_service,
            translation_repository=article_translation_repo_a,
            prompt=prompt_factory.article_body_translation_prompt(),
        )
        normalize_tags_uc = NormalizeTagsUseCase(
            embedding_service=embedding_service,
            tag_repository=tag_repo_a,
        )

        article_scraped_handler = ArticleScrapedHandler(
            use_case=process_article_uc, pipeline_stats=pipeline_stats, event_bus=bus,
        )
        article_processed_handler = ArticleProcessedHandler(use_case=analyze_article_uc, event_bus=bus)
        tag_normalization_handler = TagNormalizationHandler(
            use_case=normalize_tags_uc, event_bus=bus, session=article_session,
        )
        analysis_completed_handler = AnalysisCompletedHandler(
            translate_article_uc=translate_article_uc,
            translate_tags_uc=translate_tags_uc,
            translate_body_uc=translate_body_uc,
            analyses_translation_repo=analyses_translation_repo_a,
            event_bus=bus,
            target_languages=TRANSLATION_LANGUAGES,
        )
        failed_task_handler = FailedTaskPersistenceHandler(failed_task_repository=failed_task_repo_a)

        await bus.subscribe(ArticleScrapedEvent, article_scraped_handler.handle)
        await bus.subscribe(ArticleProcessedEvent, article_processed_handler.handle)
        if rag_enabled:
            # Subscribed after article_processed_handler (subscribe-order
            # dispatch — contracts/event-bus-port.md) though order between
            # these two doesn't matter functionally, since dispatch_rag
            # returns near-instantly regardless of position.
            await bus.subscribe(ArticleProcessedEvent, dispatch_rag)
        await bus.subscribe(AnalysisCompletedEvent, tag_normalization_handler.handle)
        await bus.subscribe(TagNormalizationCompletedEvent, analysis_completed_handler.handle)
        await bus.subscribe(AnalysisFailedEvent, failed_task_handler.handle)
        await bus.subscribe(TagNormalizationFailedEvent, failed_task_handler.handle)
        await bus.subscribe(TranslationFailedEvent, failed_task_handler.handle)

    # ── RAG downstream wiring (closure) — only built if RAG is enabled ──────
    # Called once per detached RAG task, given that task's own fresh
    # AsyncSession (used only for recording a RagIngestionFailedEvent as a
    # FailedTask on error — RAG ingestion itself uses the SDK's own,
    # separate DB connection, not this session).
    rag_downstream_builder = None
    if rag_enabled:
        async def rag_downstream_builder(rag_session):
            failed_task_repo_r = AsyncSqlAlchemyFailedTaskRepository(rag_session)
            failed_task_handler_r = FailedTaskPersistenceHandler(failed_task_repository=failed_task_repo_r)
            rag_bus = AsyncInMemoryEventBus()
            await rag_bus.subscribe(RagIngestionFailedEvent, failed_task_handler_r.handle)
            use_case = AsyncIngestArticleForRagUseCase(_rag_ingestion_service)
            return AsyncRagIngestionHandler(use_case=use_case, event_bus=rag_bus)

    # ── Barrier 1 (TextPipelineCompletedEvent): search index + cache ────────
    # (023-article-search FR-008 / 020-redis-caching-layer US3) — these only
    # depend on article/analysis text content, not RAG vectors, so they fire
    # as soon as the text stage settles rather than waiting on RAG.
    search_index_gateway = RedisSearchIndexGateway(redis_url=SEARCH_INDEX_REDIS_URL)
    search_term_repo = SqlAlchemySearchTermRepository(session)
    rebuild_search_index_uc = RebuildSearchIndexUseCase(
        session=session,
        search_term_repo=search_term_repo,
        search_index_gateway=search_index_gateway,
        min_doc_freq=SEARCH_MIN_DOC_FREQ,
    )
    search_index_rebuild_handler = SearchIndexRebuildHandler(rebuild_search_index_uc)
    await event_bus.subscribe(TextPipelineCompletedEvent, search_index_rebuild_handler.handle)

    scraper_cache_gateway = RedisCacheGateway(redis_url=CACHE_REDIS_URL)
    cache_invalidation_handler = CacheInvalidationHandler(scraper_cache_gateway)
    await event_bus.subscribe(TextPipelineCompletedEvent, cache_invalidation_handler.handle)

    # Must subscribe strictly after cache_invalidation_handler above
    # (AsyncInMemoryEventBus dispatches subscribers of the same event in
    # subscribe()-call order — contracts/event-bus-port.md) — warming has to
    # write into the *new* namespace version, not the one about to be
    # orphaned by bump_version().
    cache_warmup_handler = CacheWarmupHandler(scraper_cache_gateway)
    await event_bus.subscribe(TextPipelineCompletedEvent, cache_warmup_handler.handle)

    # ── Barrier 2 (PipelineCompletedEvent, unchanged semantics): metrics + notify ──
    otel_handler = OtelMetricsHandler()
    await event_bus.subscribe(PipelineCompletedEvent, otel_handler.handle)

    notification_handler = build_async_notification_handler(PipelineCompletedMessageBuilder)
    await event_bus.subscribe(PipelineCompletedEvent, notification_handler.handle)

    # ── Collection Pipeline ─────────────────────────────────────────────────
    from datetime import datetime, timezone
    from src.infrastructure.collection.executor import ScrapeExecutor
    from src.modules.collection.domain.entities import FailedTask
    from src.infrastructure.shared.observability import get_tracer as _get_tracer
    from opentelemetry.trace import StatusCode as _StatusCode

    _tracer = _get_tracer()

    # TODO: once DiscoverFailedEvent + DiscoverFailedHandler are merged from the
    # feature branch, replace this direct repo.save() with:
    #   event_bus.publish(DiscoverFailedEvent(source=task.setting.source, ...))
    # Unchanged from the sync pipeline — still runs inside ScrapeExecutor's own
    # thread pool (invoked via asyncio.to_thread in CollectionPipeline.run()),
    # using the shared sync session, exactly as it always has (FR-003: the
    # discover/fetch phase's internal behavior is untouched by this feature).
    def _on_discover_failed(task, exc) -> None:
        """Record a discover-phase failure as a FailedTask and emit an OTel error span.

        task_type is derived from the actual source (not hardcoded) — this callback
        now fires for any provider's rate-limit abort (arxiv/openalex/semantic_scholar),
        not just arxiv, since ScrapeExecutor catches the shared ProviderRateLimitedError base.
        """
        source = getattr(getattr(task, "setting", None), "source", "unknown")
        task_type = f"{source}_discover"
        with _tracer.start_as_current_span("scraper.discover_failed") as span:
            span.set_attribute("task.type", task_type)
            span.set_attribute("task.exception_type", type(exc).__name__)
            span.set_attribute("article.source", source)
            span.set_status(_StatusCode.ERROR, type(exc).__name__)
            failed = FailedTask(
                task_type=task_type,
                exception_type=type(exc).__name__,
                exception_message=str(exc),
                failed_at=datetime.now(timezone.utc),
            )
            try:
                failed_task_repo_sync.save(failed)
                logger.info("discover_failure_recorded", source=source)
            except Exception as e:
                logger.error("failed_task_save_error", source=source, error=str(e))

    executor = ScrapeExecutor(on_discover_failed=_on_discover_failed)

    scraper_factory = ConcreteScraperFactory(http_client=get_default_client())
    pipeline = CollectionPipeline(
        setting_repo=setting_repo,
        scraper_factory=scraper_factory,
        event_bus=event_bus,
        pipeline_stats=pipeline_stats,
        async_sessionmaker_factory=async_sessionmaker_factory,
        article_downstream_builder=article_downstream_builder,
        rag_downstream_builder=rag_downstream_builder,
        event_bus_factory=AsyncInMemoryEventBus,
        article_repo=article_repo,
        executor=executor,
        app_env=APP_ENV,
        jitter_seconds=jitter_seconds,
        llm_service=llm_service,
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
    from src.infrastructure.shared.notifications import TelegramNotifierClient

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

    from shared.cache import RedisCacheGateway
    from src.config.settings import CACHE_REDIS_URL as _CACHE_REDIS_URL

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
        cache_gateway=RedisCacheGateway(redis_url=_CACHE_REDIS_URL),
    )
    topic_repository = SqlAlchemyTopicRepository(session=session)

    # 020-redis-caching-layer follow-up: job-level operator completion notification —
    # distinct from the per-report email/telegram notifications above, which go to
    # subscribers. event_bus carries a notification handler subscribed to
    # WeeklyReportJobCompletedEvent; publish that event from weekly_report.py after
    # pipeline.run() finishes.
    from src.infrastructure.shared.events import InMemoryEventBus
    from src.infrastructure.shared.notifications import build_notification_handler
    from src.infrastructure.intelligence.notifications import WeeklyReportJobCompletedMessageBuilder
    from src.modules.intelligence.application.events import WeeklyReportJobCompletedEvent

    event_bus = InMemoryEventBus()
    notification_handler = build_notification_handler(WeeklyReportJobCompletedMessageBuilder)
    event_bus.subscribe(WeeklyReportJobCompletedEvent, notification_handler.handle)

    # llm_service returned alongside the pipeline (not threaded into
    # WeeklyReportPipeline itself) so weekly_report.py can read
    # llm_service.exhausted_providers after pipeline.run() — mirrors
    # CollectionPipeline, but WeeklyReportJobCompletedEvent is built externally
    # in the CLI entrypoint, not inside the pipeline.
    return (
        WeeklyReportPipeline(topic_repository=topic_repository, generate_use_case=generate_use_case),
        session,
        event_bus,
        llm_service,
    )


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


# ---------------------------------------------------------------------------
# Metrics Refresh Pipeline：定期重抓 citation_count 等 catalog-defined metrics
# ---------------------------------------------------------------------------

def build_metrics_refresh_pipeline():
    """Assemble (ResilientMetricsService, ArticleMetricsRepository, session, event_bus) from
    the DB-configured metric_definitions catalog. Independent of build_llm_service
    and build_weekly_pipeline — no shared code path with the backend's view_count
    flush (research.md §9b). event_bus carries a notification handler subscribed to
    MetricsRefreshCompletedEvent (020-redis-caching-layer, US4) — publish that event
    after computing refresh stats to send the completion notification."""
    from shared.metric_definition import load_enabled_metric_definitions
    from src.infrastructure.collection.metrics.resilient_metrics_service import build_resilient_metrics_service
    from src.infrastructure.persistence.collection.article_metrics_repo_impl import SqlAlchemyArticleMetricsRepository
    from src.infrastructure.shared.events import InMemoryEventBus
    from src.infrastructure.shared.notifications import build_notification_handler
    from src.infrastructure.collection.notifications import MetricsRefreshMessageBuilder
    from src.modules.collection.application.events import MetricsRefreshCompletedEvent

    init_db()
    session = get_session()

    metric_definitions = load_enabled_metric_definitions(session)
    metrics_service = build_resilient_metrics_service(metric_definitions)
    metrics_repo = SqlAlchemyArticleMetricsRepository(session=session)

    event_bus = InMemoryEventBus()
    notification_handler = build_notification_handler(MetricsRefreshMessageBuilder)
    event_bus.subscribe(MetricsRefreshCompletedEvent, notification_handler.handle)

    logger.info("metrics_refresh_bootstrap_complete", metric_definitions_count=len(metric_definitions))
    return metrics_service, metrics_repo, session, event_bus


# ---------------------------------------------------------------------------
# Dedup Reconciliation Pipeline：偵測並合併 OpenAlex 事後才 dedup 完成的重複文章
# ---------------------------------------------------------------------------

def build_dedup_reconciliation_pipeline():
    """Assemble (OpenAlexClient, ArticleDedupRepository, session, event_bus) for the
    dedup-reconciliation cron job. Independent of build_collection_pipeline —
    this only re-checks work_ids OpenAlex previously assigned us, no scraping.
    event_bus carries a notification handler subscribed to DedupReconcileCompletedEvent
    (originally out of scope per 020-redis-caching-layer's spec.md, added on request when
    unifying notification format across every scheduled job) — publish that event after
    computing healed/merged/failed stats to send the completion notification."""
    from src.infrastructure.collection.clients.openalex_client import OpenAlexClient
    from src.infrastructure.persistence.collection.article_dedup_repo_impl import SqlAlchemyArticleDedupRepository
    from src.infrastructure.shared.events import InMemoryEventBus
    from src.infrastructure.shared.notifications import build_notification_handler
    from src.infrastructure.collection.notifications import DedupReconcileMessageBuilder
    from src.modules.collection.application.events import DedupReconcileCompletedEvent

    init_db()
    session = get_session()

    client = OpenAlexClient()
    dedup_repo = SqlAlchemyArticleDedupRepository(session=session)

    event_bus = InMemoryEventBus()
    notification_handler = build_notification_handler(DedupReconcileMessageBuilder)
    event_bus.subscribe(DedupReconcileCompletedEvent, notification_handler.handle)

    logger.info("dedup_reconciliation_bootstrap_complete")
    return client, dedup_repo, session, event_bus


# ---------------------------------------------------------------------------
# RAG Backfill Pipeline：為既有文章補做向量化，補齊 has_vectors = FALSE 的缺口
# ---------------------------------------------------------------------------

def build_rag_backfill_pipeline():
    """Assemble (IngestArticleForRagUseCase | None, RagBackfillRepository, session, event_bus)
    for the RAG-backfill cron job. Reuses build_rag_ingestion_service() — the
    same RagSdkIngestionService construction the live scrape pipeline uses via
    build_collection_pipeline() — so backfilled articles are chunked/embedded
    identically to freshly-scraped ones. The use_case is None (same contract
    as build_rag_ingestion_service()) when RAG is disabled or misconfigured;
    callers must check for that before use. event_bus carries a notification handler
    subscribed to RagBackfillCompletedEvent (020-redis-caching-layer, US4) — publish
    that event after computing backfill stats to send the completion notification."""
    from src.modules.intelligence.application.use_cases.ingest_article_for_rag import IngestArticleForRagUseCase
    from src.infrastructure.persistence.intelligence.rag_backfill_repo_impl import SqlAlchemyRagBackfillRepository
    from src.infrastructure.shared.events import InMemoryEventBus
    from src.infrastructure.shared.notifications import build_notification_handler
    from src.infrastructure.intelligence.notifications import RagBackfillMessageBuilder
    from src.modules.intelligence.application.events import RagBackfillCompletedEvent

    init_db()
    session = get_session()

    rag_service, _ = build_rag_ingestion_service()
    use_case = IngestArticleForRagUseCase(rag_service) if rag_service is not None else None
    backfill_repo = SqlAlchemyRagBackfillRepository(session=session)

    event_bus = InMemoryEventBus()
    notification_handler = build_notification_handler(RagBackfillMessageBuilder)
    event_bus.subscribe(RagBackfillCompletedEvent, notification_handler.handle)

    logger.info("rag_backfill_bootstrap_complete", rag_enabled=use_case is not None)
    return use_case, backfill_repo, session, event_bus