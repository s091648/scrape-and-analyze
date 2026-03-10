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
from src.scrapers.scrapers.rss_scraper import RssScraper
from src.scrapers.scrapers.arxiv_scraper import ArxivScraper
from src.scrapers.scrapers.blog_scraper import BlogScraper
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


def _scrape(source: str) -> list:
    """Collect raw articles for the given source type."""
    articles = []

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
            batch = scraper.scrape()
            articles.extend(batch)
            logger.info("source_scraped", source=src["source"], count=len(batch))

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
        articles = scraper.scrape()
        logger.info("source_scraped", source="arxiv", count=len(articles))

    return articles


def main():
    args = parse_args()

    if not os.environ.get("DATABASE_URL"):
        print("ERROR: DATABASE_URL environment variable is required", file=sys.stderr)
        sys.exit(1)

    init_db()

    correlation_id = str(uuid.uuid4())
    bind_correlation_id(correlation_id)

    articles = _scrape(args.source)

    if args.limit:
        articles = articles[: args.limit]

    logger.info("scrape_completed", source=args.source, total=len(articles))

    if args.no_analyze:
        logger.info("analysis_skipped")
        return

    from src.main import build_analyzer, load_prompt, process_article_safe

    analyzer = build_analyzer()
    prompt = load_prompt()

    success = failed = 0
    for article in articles:
        if process_article_safe(article, analyzer, prompt, correlation_id):
            success += 1
        else:
            failed += 1

    logger.info(
        "run_completed",
        source=args.source,
        success=success,
        failed=failed,
        total=len(articles),
    )


if __name__ == "__main__":
    main()
