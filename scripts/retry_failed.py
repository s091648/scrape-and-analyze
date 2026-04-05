#!/usr/bin/env python3
"""
Retry failed scrape/analyze tasks recorded in the failed_tasks table.

Usage:
    python scripts/retry_failed.py [--hours N] [--limit N] [--dry-run]

Options:
    --hours N    Look back N hours for failures (default: 72)
    --limit N    Max number of tasks to retry
    --dry-run    Print what would be retried without executing

DATABASE_URL must be set in the environment.
"""
import argparse
import os
import sys
import uuid

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.database import get_session, init_db, find_recent_failures
from src.utils.logging import get_logger, bind_correlation_id

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


def retry_analyze(session, failure, analyzer, prompt, correlation_id, dry_run) -> bool:
    """Re-run analysis on an existing article."""
    from models.article import Article
    from src.database import has_analysis
    from src.main import analyze_article

    if not failure.article_id:
        logger.warning("retry_analyze_no_article_id", failure_id=str(failure.id))
        return False

    article = session.query(Article).filter_by(id=failure.article_id).first()
    if not article:
        logger.warning("retry_analyze_article_not_found",
                       failure_id=str(failure.id), article_id=str(failure.article_id))
        return False

    if has_analysis(session, article.id):
        logger.info("retry_analyze_already_done", article_id=str(article.id))
        return True

    if dry_run:
        print(f"  [DRY RUN] Would re-analyze article {article.id} — {article.url}")
        return True

    return analyze_article(session, article, analyzer, prompt, correlation_id)


def retry_scrape(session, failure, analyzer, prompt, correlation_id, dry_run) -> bool:
    """Re-scrape a URL and process the article."""
    from src.main import process_article_safe
    from src.scrapers.content_parsers.html_parser import HtmlArticleParser
    from src.scrapers.scrapers.article import ScrapedArticle
    import requests

    url = failure.article_url
    if not url:
        logger.warning("retry_scrape_no_url", failure_id=str(failure.id))
        return False

    if dry_run:
        print(f"  [DRY RUN] Would re-scrape {url}")
        return True

    try:
        response = requests.get(url, timeout=30, headers={"User-Agent": "Mozilla/5.0"})
        response.raise_for_status()
        parser = HtmlArticleParser()
        content = parser.parse(response.text, url)
        scraped = ScrapedArticle(
            url=url,
            title=content.title or url,
            content=content.text or "",
            published_at=None,
            source=failure.article_url.split("/")[2] if url else "unknown",
        )
    except Exception as e:
        logger.error("retry_scrape_fetch_failed", url=url, error=str(e))
        return False

    return process_article_safe(scraped, analyzer, prompt, correlation_id)


def main():
    args = parse_args()

    if not os.environ.get("DATABASE_URL"):
        print("ERROR: DATABASE_URL environment variable is required", file=sys.stderr)
        sys.exit(1)

    init_db()

    correlation_id = str(uuid.uuid4())
    bind_correlation_id(correlation_id)

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
        failures = failures[: args.limit]

    if not failures:
        msg = f"the last {args.hours} hours" if args.hours else "all time"
        print(f"No unresolved failures found ({msg}).")
        return

    print(f"Found {len(failures)} unresolved failure(s) — retrying...\n")

    from src.main import build_analyzer, load_prompt

    analyzer = build_analyzer()
    prompt = load_prompt()

    success = failed = skipped = 0

    for failure in failures:
        logger.info("retry_start",
                    failure_id=str(failure.id),
                    task_type=failure.task_type,
                    url=failure.article_url)

        session = get_session()
        try:
            if failure.task_type == "analyze":
                ok = retry_analyze(session, failure, analyzer, prompt, correlation_id, args.dry_run)
            elif failure.task_type == "scrape":
                ok = retry_scrape(session, failure, analyzer, prompt, correlation_id, args.dry_run)
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
