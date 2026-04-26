#!/usr/bin/env python3
"""
Retry failed scrape/analyze tasks recorded in the failed_tasks table.

Usage:
    python scripts/retry_failed.py [--hours N] [--limit N] [--dry-run]

Options:
    --hours N    Look back N hours for failures (default: all unresolved)
    --limit N    Max number of tasks to retry
    --dry-run    Print what would be retried without executing

DATABASE_URL must be set in the environment.
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.infrastructure.persistence.database import get_session, init_db, find_recent_failures
from src.infrastructure.shared.logging import bind_correlation_id
from src.shared.logging import get_logger

logger = get_logger(__name__)


def parse_args():
    parser = argparse.ArgumentParser(description="Retry failed scrape/analyze tasks.")
    parser.add_argument(
        "--hours", type=int, default=None,
        help="Only retry failures from the last N hours (default: all unresolved)",
    )
    parser.add_argument(
        "--limit", type=int, default=None,
        help="Maximum number of tasks to retry",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Print tasks that would be retried without executing",
    )
    return parser.parse_args()


def mark_resolved(session, failure) -> None:
    from datetime import datetime, timezone
    failure.resolved = True
    failure.resolved_at = datetime.now(timezone.utc)
    session.commit()


def _build_article_entity(article_row):
    """Convert an ORM Article row into the domain Article entity."""
    from src.shared.domain.entities import Article
    return Article(
        id=article_row.id,
        url=article_row.url,
        url_hash=article_row.url_hash,
        source=article_row.source,
        title=article_row.title,
        content=article_row.content,
        published_at=article_row.published_at,
        scraped_at=article_row.scraped_at,
        metadata=article_row.metadata_ or {},
        topic_id=article_row.topic_id if hasattr(article_row, 'topic_id') else None,
    )


def retry_analyze(session, failure, llm_service, dry_run: bool) -> bool:
    """Re-run analysis on an existing article."""
    from models.article import Article as ArticleModel
    from src.infrastructure.persistence.database import has_analysis
    from src.infrastructure.persistence.intelligence.analysis_repo_impl import SqlAlchemyAnalysisRepository
    from src.infrastructure.persistence.shared.topic_repo_impl import SqlAlchemyTopicRepository
    from src.infrastructure.persistence.shared.failed_task_repo_impl import SqlAlchemyFailedTaskRepository
    from src.infrastructure.shared.events import InMemoryEventBus
    from src.modules.intelligence.application.use_cases import AnalyzeArticleUseCase
    from src.modules.intelligence.application.event_handlers import AnalysisFailedHandler
    from src.modules.intelligence.application.events import AnalysisFailedEvent

    if not failure.article_id:
        logger.warning("retry_analyze_no_article_id", failure_id=str(failure.id))
        return False

    article_row = session.query(ArticleModel).filter_by(id=failure.article_id).first()
    if not article_row:
        logger.warning("retry_analyze_article_not_found",
                       failure_id=str(failure.id), article_id=str(failure.article_id))
        return False

    if has_analysis(session, article_row.id):
        logger.info("retry_analyze_already_done", article_id=str(article_row.id))
        return True

    if dry_run:
        print(f"  [DRY RUN] Would re-analyze article {article_row.id} — {article_row.url}")
        return True

    article = _build_article_entity(article_row)
    analysis_repo = SqlAlchemyAnalysisRepository(session=session)
    topic_repo = SqlAlchemyTopicRepository(session=session)
    failed_task_repo = SqlAlchemyFailedTaskRepository(session=session)
    event_bus = InMemoryEventBus()
    event_bus.subscribe(
        AnalysisFailedEvent,
        AnalysisFailedHandler(failed_task_repository=failed_task_repo).handle,
    )

    uc = AnalyzeArticleUseCase(
        llm_service=llm_service,
        analysis_repository=analysis_repo,
        topic_repository=topic_repo,
        event_bus=event_bus,
    )
    return uc.execute(article)


def retry_scrape(session, failure, llm_service, dry_run: bool) -> bool:
    """Re-scrape a URL, process it, and trigger analysis."""
    import requests
    from src.infrastructure.collection.parsers.html_parser import HtmlArticleParser
    from src.infrastructure.persistence.shared.article_repo_impl import SqlAlchemyArticleRepository
    from src.infrastructure.persistence.shared.topic_repo_impl import SqlAlchemyTopicRepository
    from src.infrastructure.persistence.intelligence.analysis_repo_impl import SqlAlchemyAnalysisRepository
    from src.infrastructure.persistence.shared.failed_task_repo_impl import SqlAlchemyFailedTaskRepository
    from src.infrastructure.shared.events import InMemoryEventBus
    from src.modules.collection.domain.services import DedupService
    from src.modules.collection.application.use_cases import ProcessScrapedArticleUseCase
    from src.modules.collection.application.events import ArticleScrapedEvent
    from src.modules.intelligence.application.use_cases import AnalyzeArticleUseCase
    from src.modules.intelligence.application.event_handlers import ArticleProcessedHandler, AnalysisFailedHandler
    from src.modules.intelligence.application.events import AnalysisFailedEvent
    from src.shared.application.events import ArticleProcessedEvent

    url = failure.article_url
    if not url:
        logger.warning("retry_scrape_no_url", failure_id=str(failure.id))
        return False

    if dry_run:
        print(f"  [DRY RUN] Would re-scrape {url}")
        return True

    try:
        from bs4 import BeautifulSoup
        response = requests.get(url, timeout=30, headers={"User-Agent": "Mozilla/5.0"})
        response.raise_for_status()
        parser = HtmlArticleParser()
        content = parser.parse(response.text)
        soup = BeautifulSoup(response.text, "html.parser")
        title = soup.title.string.strip() if soup.title else url
    except Exception as e:
        logger.error("retry_scrape_fetch_failed", url=url, error=str(e))
        return False

    article_repo = SqlAlchemyArticleRepository(session=session)
    analysis_repo = SqlAlchemyAnalysisRepository(session=session)
    topic_repo = SqlAlchemyTopicRepository(session=session)
    failed_task_repo = SqlAlchemyFailedTaskRepository(session=session)

    event_bus = InMemoryEventBus()
    dedup = DedupService(article_repo=article_repo)

    process_uc = ProcessScrapedArticleUseCase(
        article_repo=article_repo,
        dedup_service=dedup,
        event_bus=event_bus,
    )
    analyze_uc = AnalyzeArticleUseCase(
        llm_service=llm_service,
        analysis_repository=analysis_repo,
        topic_repository=topic_repo,
        event_bus=event_bus,
    )
    event_bus.subscribe(ArticleProcessedEvent, ArticleProcessedHandler(use_case=analyze_uc).handle)
    event_bus.subscribe(AnalysisFailedEvent, AnalysisFailedHandler(failed_task_repository=failed_task_repo).handle)

    source = url.split("/")[2] if "/" in url else "unknown"
    scraped_event = ArticleScrapedEvent(
        url=url,
        title=title,
        content=content,
        source=source,
    )
    return process_uc.execute(scraped_event)


def main():
    args = parse_args()

    if not os.environ.get("DATABASE_URL"):
        print("ERROR: DATABASE_URL environment variable is required", file=sys.stderr)
        sys.exit(1)

    import uuid
    bind_correlation_id(str(uuid.uuid4()))
    init_db()

    session = get_session()
    try:
        if args.hours:
            failures = find_recent_failures(session, hours=args.hours)
        else:
            from models.failed_task import FailedTask
            failures = session.query(FailedTask).filter_by(resolved=False).all()
    finally:
        session.close()

    if args.limit:
        failures = failures[:args.limit]

    if not failures:
        msg = f"the last {args.hours} hours" if args.hours else "all time"
        print(f"No unresolved failures found ({msg}).")
        return

    print(f"Found {len(failures)} unresolved failure(s) — retrying...\n")

    from src.bootstrap import build_llm_service
    llm_service = build_llm_service()

    success = failed = skipped = 0

    for failure in failures:
        logger.info("retry_start",
                    failure_id=str(failure.id),
                    task_type=failure.task_type,
                    url=failure.article_url)

        session = get_session()
        try:
            if failure.task_type == "analyze":
                ok = retry_analyze(session, failure, llm_service, args.dry_run)
            elif failure.task_type == "scrape":
                ok = retry_scrape(session, failure, llm_service, args.dry_run)
            else:
                logger.warning("retry_unknown_task_type", task_type=failure.task_type)
                skipped += 1
                continue

            if ok:
                if not args.dry_run:
                    mark_resolved(session, failure)
                success += 1
                logger.info("retry_success", failure_id=str(failure.id))
            else:
                failed += 1
                logger.warning("retry_failed", failure_id=str(failure.id))

        except Exception as e:
            logger.error("retry_exception", failure_id=str(failure.id), error=str(e))
            failed += 1
        finally:
            session.close()

    prefix = "[DRY RUN] " if args.dry_run else ""
    print(
        f"\n{prefix}Retry complete: "
        f"{success} succeeded, {failed} failed, {skipped} skipped"
    )


if __name__ == "__main__":
    main()
