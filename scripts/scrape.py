#!/usr/bin/env python3
"""
Scrape (and optionally analyze) articles from a specific source.

Usage:
    python scripts/scrape.py --source rss [--no-analyze] [--limit N]
    python scripts/scrape.py --source blog [--no-analyze] [--limit N]
    python scripts/scrape.py --source arxiv [--no-analyze] [--limit N]

Source types:
    rss    — RSS feeds configured in the database (source_type='rss')
    blog   — Blog scrapers configured in the database (source_type='blog')
    arxiv  — arXiv API, config loaded from database (source_type='arxiv')

Bypasses frequency check — designed for manual one-off execution.
Provider selection and rate limiting are controlled by providers.toml.
"""
import argparse
import os
import sys

# Ensure project root is on sys.path when run directly
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.infrastructure.persistence.database import get_session, init_db
from src.infrastructure.shared.logging import bind_correlation_id
from src.shared.logging import get_logger

logger = get_logger(__name__)


def parse_args():
    parser = argparse.ArgumentParser(description="Scrape (and optionally analyze) articles.")
    parser.add_argument(
        "--source",
        choices=["rss", "blog", "arxiv"],
        required=True,
        help="Source type to scrape",
    )
    parser.add_argument(
        "--no-analyze",
        action="store_true",
        help="Skip LLM analysis — scrape only",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Maximum number of articles to process",
    )
    parser.add_argument(
        "--days-back",
        type=int,
        default=None,
        help="Number of days back to search (for arxiv). Use -1 for no filter.",
    )
    return parser.parse_args()


def _get_active_settings_by_type(session, source_type: str):
    """Return all active ScraperSettings of the given source_type (bypasses frequency check)."""
    from models.scraper_setting import ScraperSetting as ScraperSettingModel
    from models.topic import Topic as TopicModel
    from src.modules.collection.domain.entities import ScraperSetting

    rows = (
        session.query(ScraperSettingModel)
        .filter_by(is_active=True, source_type=source_type)
        .all()
    )

    settings = []
    for row in rows:
        prompt_override = None
        if row.topic_id:
            topic = session.query(TopicModel).filter_by(id=row.topic_id).first()
            if topic:
                prompt_override = topic.prompt_override

        settings.append(ScraperSetting(
            id=row.id,
            source=row.name,
            source_type=row.source_type,
            url=row.url,
            interval_hours=row.frequency,
            topic_id=row.topic_id,
            prompt_override=prompt_override,
            selector_config=row.selector_config or {},
            last_scraped_at=row.last_scraped_at,
            is_active=row.is_active,
        ))

    return settings


def _build_pipeline(no_analyze: bool):
    """Wire up the event-driven use case pipeline, returning (event_bus, process_uc)."""
    from src.infrastructure.persistence.database import get_session
    from src.infrastructure.persistence.shared.article_repo_impl import SqlAlchemyArticleRepository
    from src.infrastructure.persistence.shared.topic_repo_impl import SqlAlchemyTopicRepository
    from src.infrastructure.persistence.intelligence.analysis_repo_impl import SqlAlchemyAnalysisRepository
    from src.infrastructure.persistence.shared.failed_task_repo_impl import SqlAlchemyFailedTaskRepository
    from src.infrastructure.shared.events import InMemoryEventBus
    from src.modules.collection.domain.services import DedupService
    from src.modules.collection.application.use_cases import ProcessScrapedArticleUseCase, PipelineStats
    from src.modules.collection.application.event_handlers import ArticleScrapedHandler
    from src.modules.collection.application.dtos import ScrapedArticleDTO
    from src.modules.intelligence.application.use_cases import AnalyzeArticleUseCase
    from src.modules.intelligence.application.event_handlers import ArticleProcessedHandler, AnalysisFailedHandler
    from src.modules.intelligence.application.events import AnalysisFailedEvent
    from src.shared.application.events import ArticleProcessedEvent

    session = get_session()
    article_repo = SqlAlchemyArticleRepository(session=session)
    topic_repo = SqlAlchemyTopicRepository(session=session)
    analysis_repo = SqlAlchemyAnalysisRepository(session=session)
    failed_task_repo = SqlAlchemyFailedTaskRepository(session=session)

    event_bus = InMemoryEventBus()
    dedup = DedupService(article_repo=article_repo)
    pipeline_stats = PipelineStats()

    process_uc = ProcessScrapedArticleUseCase(
        article_repo=article_repo,
        dedup_service=dedup,
        event_bus=event_bus,
    )
    event_bus.subscribe(ScrapedArticleDTO, ArticleScrapedHandler(use_case=process_uc, pipeline_stats=pipeline_stats).handle)

    if not no_analyze:
        from src.bootstrap import build_llm_service
        from src.modules.intelligence.application.events import AnalysisCompletedEvent
        from src.modules.intelligence.application.use_cases import TranslateArticleUseCase, TranslateTagsUseCase
        from src.modules.intelligence.application.event_handlers import AnalysisCompletedHandler
        from src.infrastructure.persistence.intelligence import SqlAlchemyTranslationRepository, SqlAlchemyTagTranslationRepository
        from src.config.settings import TRANSLATION_LANGUAGES

        llm_service = build_llm_service()
        analyze_uc = AnalyzeArticleUseCase(
            llm_service=llm_service,
            analysis_repository=analysis_repo,
            topic_repository=topic_repo,
            event_bus=event_bus,
        )
        event_bus.subscribe(ArticleProcessedEvent, ArticleProcessedHandler(use_case=analyze_uc).handle)
        event_bus.subscribe(AnalysisFailedEvent, AnalysisFailedHandler(failed_task_repository=failed_task_repo).handle)

        # Auto-translate after analysis
        translation_repo = SqlAlchemyTranslationRepository(session=session)
        tag_translation_repo = SqlAlchemyTagTranslationRepository(session=session)
        translate_article_uc = TranslateArticleUseCase(
            llm_service=llm_service,
            translation_repository=translation_repo,
        )
        translate_tags_uc = TranslateTagsUseCase(
            llm_service=llm_service,
            tag_translation_repository=tag_translation_repo,
        )
        target_languages = [lang.strip() for lang in TRANSLATION_LANGUAGES.split(",") if lang.strip()]
        analysis_completed_handler = AnalysisCompletedHandler(
            translate_article_uc=translate_article_uc,
            translate_tags_uc=translate_tags_uc,
            target_languages=target_languages,
            session_rollback_fn=session.rollback,
        )
        event_bus.subscribe(AnalysisCompletedEvent, analysis_completed_handler.handle)

    return event_bus, process_uc


def main():
    args = parse_args()

    if not os.environ.get("DATABASE_URL"):
        print("ERROR: DATABASE_URL environment variable is required", file=sys.stderr)
        sys.exit(1)

    import uuid
    bind_correlation_id(str(uuid.uuid4()))
    init_db()

    from src.infrastructure.collection.scrapers.scraper_factory import ConcreteScraperFactory
    from src.infrastructure.collection.executor.fetch_task import FetchTask
    from src.infrastructure.collection.executor.scrape_executor import ScrapeExecutor

    session = get_session()
    try:
        settings = _get_active_settings_by_type(session, args.source)
    finally:
        session.close()

    if not settings:
        print(f"No active {args.source!r} sources found in database.")
        return

    factory = ConcreteScraperFactory()
    tasks = []

    for setting in settings:
        try:
            scraper = factory.create_for(setting, days_back=args.days_back)
            jobs = scraper.discover()
        except Exception as e:
            logger.error("discover_failed", source=setting.source, error=str(e))
            continue

        logger.info("jobs_discovered", source=setting.source, count=len(jobs))
        for job in jobs:
            tasks.append(FetchTask(url=job.url, source=setting.source, job=job, scraper=scraper))

    if args.limit:
        tasks = tasks[:args.limit]

    logger.info("scrape_tasks_total", source=args.source, total=len(tasks))

    if not tasks:
        print("No tasks to run.")
        return

    from src.modules.collection.application.dtos import ScrapedArticleDTO

    event_bus, _ = _build_pipeline(no_analyze=args.no_analyze)
    published = [0]

    def on_result(article):
        dto = ScrapedArticleDTO.from_scraped_article(article)
        event_bus.publish(dto)
        published[0] += 1

    executor = ScrapeExecutor()
    executor.run(tasks, on_result=on_result)

    logger.info(
        "scrape_completed",
        source=args.source,
        published=published[0],
        total=len(tasks),
    )


if __name__ == "__main__":
    main()