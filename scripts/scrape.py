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
import uuid

# Ensure project root is on sys.path when run directly
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.config import get_sources
from src.database import get_session, init_db
from src.ingestion.scrapers.rss_scraper import RssScraper
from src.ingestion.scrapers.arxiv_scraper import ArxivScraper
from src.ingestion.scrapers.blog_scraper import BlogScraper
from src.utils.logging import get_logger, bind_correlation_id

logger = get_logger(__name__)


def parse_args():
    parser = argparse.ArgumentParser(description="Scrape (and optionally analyze) articles.")
    parser.add_argument(
        "--source",
        choices=["rss", "blog", "arxiv"],
        required=True,
        help="Source type: rss (feeds from DB), blog (blogs from DB), arxiv",
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
    return parser.parse_args()


def _discover_tasks(source: str) -> list:
    """Return ScrapeTask list for the given source type."""
    tasks = []

    if source in ("rss", "blog"):
        session = get_session()
        try:
            sources = get_sources(source, session)
        finally:
            session.close()

        for src in sources:
            if source == "rss":
                scraper = RssScraper(url=src["url"], source=src["source"])
            else:
                scraper = BlogScraper(
                    base_url=src["base_url"],
                    source=src["source"],
                    selectors=src["selectors"],
                )
            batch = scraper.discover()
            tasks.extend(batch)
            logger.info("source_discovered", source=src["source"], task_count=len(batch))

    elif source == "arxiv":
        session = get_session()
        try:
            arxiv_sources = get_sources("arxiv", session)
        finally:
            session.close()
        cfg = arxiv_sources[0].get("selector_config", {}) if arxiv_sources else {}
        scraper = ArxivScraper(
            max_results=cfg.get("max_results", 30),
            days_back=cfg.get("days_back", 1),
        )
        tasks = scraper.discover()
        logger.info("source_discovered", source="arxiv", task_count=len(tasks))

    return tasks


def main():
    args = parse_args()

    if not os.environ.get("DATABASE_URL"):
        print("ERROR: DATABASE_URL environment variable is required", file=sys.stderr)
        sys.exit(1)

    init_db()

    correlation_id = str(uuid.uuid4())
    bind_correlation_id(correlation_id)

    tasks = _discover_tasks(args.source)

    if args.limit:
        tasks = tasks[: args.limit]

    logger.info("scrape_tasks_total", source=args.source, total=len(tasks))

    if args.no_analyze:
        # Execute tasks to count articles without saving or analysing
        count = sum(1 for t in tasks if t.execute() is not None)
        logger.info("scrape_completed_no_analyze", source=args.source, scraped=count)
        return

    from src.app.composition_root import build_analyzer
    from src.app.use_cases.process_article import ProcessArticleUseCase
    from src.app.use_cases.analyze_article import AnalyzeArticleUseCase
    from src.infrastructure.persistence.sqlalchemy_repos.article_repo_impl import (
        SqlAlchemyArticleRepository,
    )
    from src.infrastructure.persistence.sqlalchemy_repos.analysis_repo_impl import (
        SqlAlchemyAnalysisRepository,
    )
    from src.domain.services.dedup_service import DedupService
    from src.main import load_prompt

    analyzer = build_analyzer()
    prompt = load_prompt()

    success = failed = 0
    for task in tasks:
        scraped = task.execute()
        if scraped is None:
            failed += 1
            continue

        session = get_session()
        try:
            article_repo = SqlAlchemyArticleRepository(session=session)
            analysis_repo = SqlAlchemyAnalysisRepository(session=session)
            dedup_svc = DedupService(article_repo=article_repo)
            analyze_uc = AnalyzeArticleUseCase(analyzer=analyzer, analysis_repo=analysis_repo)
            process_uc = ProcessArticleUseCase(
                article_repo=article_repo,
                dedup_service=dedup_svc,
                analyze_article_uc=analyze_uc,
            )
            if process_uc.execute(scraped, prompt, correlation_id):
                success += 1
            else:
                failed += 1
        except Exception as e:
            logger.error("process_article_failed", url=task.url, error=str(e))
            failed += 1
        finally:
            session.close()

    logger.info(
        "run_completed",
        source=args.source,
        success=success,
        failed=failed,
        total=len(tasks),
    )


if __name__ == "__main__":
    main()
