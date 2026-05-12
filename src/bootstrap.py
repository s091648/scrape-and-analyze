"""
bootstrap.py — 依賴組裝入口點（取代舊有的 composition_root.py）

職責：
  - 從設定檔（providers.toml、環境變數）讀取組態
  - 建立所有 infrastructure 物件（DB session、repositories、LLM providers）
  - 組裝 event bus 並完成 handler 訂閱
  - 回傳可執行的 CollectionPipeline

所有業務邏輯與框架細節的「黏合程式碼」集中於此，
讓 entrypoint（main.py）只負責 process-level 的初始化與生命週期管理。
"""
import os
from typing import List

from src.shared.logging import get_logger

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# LLM 層：從 providers.toml 建立 ResilientLLMService
# ---------------------------------------------------------------------------

def build_llm_service():
    """
    Prompt 不在此處注入——每次 analyze() call 時由 AnalyzeArticleUseCase
    根據 article.topic_id 動態 render 後傳入。
    """
    from src.config.providers import load_providers
    from src.infrastructure.intelligence.llm.resilient_llm_service import (
        ResilientLLMService, ProviderHandler,
    )
    from src.infrastructure.intelligence.llm.providers import ClaudeProvider, GeminiProvider, OpenRouterProvider
    from src.infrastructure.intelligence.llm.rate_limit import SlidingWindowStrategy, NoOpStrategy

    handlers: List[ProviderHandler] = []

    for cfg in load_providers():
        name = cfg['name']
        model = cfg['model']
        api_key = os.environ.get(cfg['api_key_env'], '')

        if name == 'claude':
            provider = ClaudeProvider(api_key=api_key, model=model)
        elif name == 'gemini':
            provider = GeminiProvider(api_key=api_key, model=model)
        elif name == 'openrouter':
            provider = OpenRouterProvider(api_key=api_key, model=model)
        else:
            logger.warning("unknown_provider_skipped", name=name)
            continue

        s_cfg = cfg.get('strategy', {})
        if s_cfg.get('type') == 'sliding_window':
            strategy = SlidingWindowStrategy(
                rpm=s_cfg['rpm'],
                tpm=s_cfg['tpm'],
                rpd=s_cfg['rpd'],
            )
        else:
            strategy = NoOpStrategy()

        handlers.append(ProviderHandler(
            provider=provider,
            strategy=strategy,
            priority=cfg['priority'],
            name=name,
        ))

    if not handlers:
        raise ValueError("providers.toml 中未設定任何有效的 LLM provider")

    return ResilientLLMService(handlers=handlers)


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
    from src.infrastructure.persistence.database import get_session, init_db
    from src.infrastructure.persistence.shared.article_repo_impl import SqlAlchemyArticleRepository
    from src.infrastructure.persistence.shared.topic_repo_impl import SqlAlchemyTopicRepository
    from src.infrastructure.persistence.shared.failed_task_repo_impl import SqlAlchemyFailedTaskRepository
    from src.infrastructure.persistence.intelligence.analysis_repo_impl import SqlAlchemyAnalysisRepository
    from src.infrastructure.persistence.collection.scraper_setting_repo_impl import SqlAlchemyScraperSettingRepository
    from src.infrastructure.persistence.collection.arxiv_metadata_repo_impl import SqlAlchemyArxivMetadataRepository
    from src.infrastructure.shared.events import InMemoryEventBus
    from src.infrastructure.collection.scrapers.scraper_factory import ConcreteScraperFactory
    from src.infrastructure.collection.collection_pipeline import CollectionPipeline
    from src.infrastructure.collection.handlers import OtelMetricsHandler
    from src.infrastructure.shared.notifications import build_notification_handler
    from src.infrastructure.shared.http import get_default_client

    from src.modules.collection.domain.services import DedupService
    from src.modules.collection.application.use_cases import ProcessScrapedArticleUseCase, PipelineStats
    from src.modules.collection.application.events import ArticleScrapedEvent, PipelineCompletedEvent
    from src.modules.collection.application.event_handlers import ArticleScrapedHandler
    from src.modules.intelligence.application.use_cases import AnalyzeArticleUseCase, TranslateArticleUseCase, TranslateTagsUseCase
    from src.modules.intelligence.application.event_handlers import ArticleProcessedHandler, AnalysisFailedHandler, AnalysisCompletedHandler
    from src.modules.intelligence.domain.value_objects import AnalysisPrompt, ArticleTranslationPrompt, TagTranslationPrompt, GroupTranslationPrompt
    from src.modules.intelligence.application.events import AnalysisFailedEvent, AnalysisCompletedEvent

    from src.shared.application.events import ArticleProcessedEvent

    # ── DB 初始化 ──────────────────────────────────────────────────────────
    init_db()
    session = get_session()

    # ── Repositories ───────────────────────────────────────────────────────
    article_repo = SqlAlchemyArticleRepository(session=session)
    analysis_repo = SqlAlchemyAnalysisRepository(session=session)
    setting_repo = SqlAlchemyScraperSettingRepository(session=session)
    arxiv_metadata_repo = SqlAlchemyArxivMetadataRepository(session=session)
    topic_repo = SqlAlchemyTopicRepository(session=session)
    failed_task_repo = SqlAlchemyFailedTaskRepository(session=session)

    # ── Event Bus ──────────────────────────────────────────────────────────
    event_bus = InMemoryEventBus()

    # ── LLM Service ────────────────────────────────────────────────────────
    llm_service = build_llm_service()

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
        prompt=AnalysisPrompt(),
    )

    # ── Event Handlers 訂閱 ────────────────────────────────────────────────
    # collection 跨 context 事件：ArticleScrapedEvent → ProcessScrapedArticleUseCase
    article_scraped_handler = ArticleScrapedHandler(
        use_case=process_article_uc,
        pipeline_stats=pipeline_stats,
        event_bus=event_bus,
    )
    event_bus.subscribe(ArticleScrapedEvent, article_scraped_handler.handle)

    # 跨 context 整合事件：ArticleProcessedEvent → AnalyzeArticleUseCase
    article_processed_handler = ArticleProcessedHandler(use_case=analyze_article_uc, event_bus=event_bus)
    event_bus.subscribe(ArticleProcessedEvent, article_processed_handler.handle)

    # intelligence 失敗事件：AnalysisFailedEvent → AnalysisFailedHandler
    analysis_failed_handler = AnalysisFailedHandler(failed_task_repository=failed_task_repo)
    event_bus.subscribe(AnalysisFailedEvent, analysis_failed_handler.handle)

    # translation 事件：AnalysisCompletedEvent → auto-translate
    from src.infrastructure.persistence.intelligence import SqlAlchemyAnalysesTranslationRepository, SqlAlchemyTagTranslationRepository
    from src.config.settings import TRANSLATION_LANGUAGES

    analyses_translation_repo = SqlAlchemyAnalysesTranslationRepository(session=session)
    tag_translation_repo = SqlAlchemyTagTranslationRepository(session=session)
    translate_article_uc = TranslateArticleUseCase(
        llm_service=llm_service,
        translation_repository=analyses_translation_repo,
        prompt=ArticleTranslationPrompt(),
    )
    translate_tags_uc = TranslateTagsUseCase(
        llm_service=llm_service,
        tag_translation_repository=tag_translation_repo,
        tag_prompt=TagTranslationPrompt(),
        group_prompt=GroupTranslationPrompt(),
    )
    target_languages = TRANSLATION_LANGUAGES
    analysis_completed_handler = AnalysisCompletedHandler(
        translate_article_uc=translate_article_uc,
        translate_tags_uc=translate_tags_uc,
        analyses_translation_repo=analyses_translation_repo,
        target_languages=target_languages,
    )
    event_bus.subscribe(AnalysisCompletedEvent, analysis_completed_handler.handle)

    # ── Observability handlers — subscribe to PipelineCompletedEvent ────────
    otel_handler = OtelMetricsHandler()
    event_bus.subscribe(PipelineCompletedEvent, otel_handler.handle)

    notification_handler = build_notification_handler()
    event_bus.subscribe(PipelineCompletedEvent, notification_handler.handle)

    # ── Collection Pipeline ─────────────────────────────────────────────────
    scraper_factory = ConcreteScraperFactory(http_client=get_default_client())
    pipeline = CollectionPipeline(
        setting_repo=setting_repo,
        scraper_factory=scraper_factory,
        event_bus=event_bus,
        pipeline_stats=pipeline_stats,
        article_repo=article_repo,
    )

    logger.info("bootstrap_complete")
    return pipeline


# ---------------------------------------------------------------------------
# Translation Pipeline：翻譯流程的依賴組裝
# ---------------------------------------------------------------------------

def build_translation_pipeline():
    """
    組裝翻譯 pipeline。

    回傳翻譯相關服務，可用於定時翻譯任務。
    """
    from src.infrastructure.persistence.database import get_session, init_db
    from src.infrastructure.persistence.intelligence import SqlAlchemyAnalysesTranslationRepository, SqlAlchemyTagTranslationRepository
    from src.modules.intelligence.application.use_cases import TranslateArticleUseCase, TranslateTagsUseCase
    from src.modules.intelligence.domain.value_objects import ArticleTranslationPrompt, TagTranslationPrompt, GroupTranslationPrompt

    # ── DB 初始化 ──────────────────────────────────────────────────────────
    init_db()
    session = get_session()

    # ── Repositories ───────────────────────────────────────────────────────
    analyses_translation_repo = SqlAlchemyAnalysesTranslationRepository(session=session)
    tag_translation_repo = SqlAlchemyTagTranslationRepository(session=session)

    # ── LLM Service ────────────────────────────────────────────────────────
    llm_service = build_llm_service()

    # ── Use Cases ──────────────────────────────────────────────────────────
    translate_article_uc = TranslateArticleUseCase(
        llm_service=llm_service,
        translation_repository=analyses_translation_repo,
        prompt=ArticleTranslationPrompt(),
    )
    translate_tags_uc = TranslateTagsUseCase(
        llm_service=llm_service,
        tag_translation_repository=tag_translation_repo,
        tag_prompt=TagTranslationPrompt(),
        group_prompt=GroupTranslationPrompt(),
    )

    logger.info("translation_bootstrap_complete")
    return {
        "use_case": translate_article_uc,
        "tag_use_case": translate_tags_uc,
        "session": session,
        "analyses_translation_repository": analyses_translation_repo,
        "tag_translation_repository": tag_translation_repo,
    }