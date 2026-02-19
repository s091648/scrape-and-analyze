import argparse
import uuid
import time
import signal
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Optional
from datetime import datetime, timezone

from src.utils.logging import get_logger, bind_correlation_id, configure_logging
from src.config import RSS_SOURCES, BLOG_SOURCES, LLM_API_KEY, LLM_MODEL, SENTRY_DSN

# Initialize Sentry if configured
if SENTRY_DSN:
    import sentry_sdk
    sentry_sdk.init(
        dsn=SENTRY_DSN,
        traces_sample_rate=0.1,
    )
from src.database import get_session, has_analysis
from src.scrapers.rss_scraper import RssScraper
from src.scrapers.arxiv_scraper import ArxivScraper
from src.scrapers.blog_scraper import BlogScraper
from src.analyzers.claude import ClaudeProvider
from src.models.article import Article
from src.models.analysis import Analysis
from src.models.failed_task import FailedTask
from src.utils.sanitizer import generate_url_hash

logger = get_logger(__name__)

MAX_WORKERS = 3
MAX_EXECUTION_TIME = 50 * 60  # 50 minutes
BATCH_SIZE = 50

# Global flag for graceful shutdown
_shutdown_requested = False


def parse_args(args=None):
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(description='Digital Twins Scraper')
    parser.add_argument('command', choices=['daily', 'weekly', 'remediate'],
                        help='Execution mode: daily, weekly, or remediate')
    return parser.parse_args(args)


def signal_handler(signum, frame):
    """Handle shutdown signals gracefully"""
    global _shutdown_requested
    logger.warning("shutdown_signal_received", signal=signum)
    _shutdown_requested = True


def check_timeout(start_time: float) -> bool:
    """Check if execution has exceeded max time"""
    elapsed = time.time() - start_time
    if elapsed >= MAX_EXECUTION_TIME:
        logger.warning("execution_timeout_reached", elapsed_seconds=elapsed)
        return True
    return False


def load_prompt() -> str:
    """Load analysis prompt from file"""
    import os
    prompt_path = os.path.join(os.path.dirname(__file__), 'prompts', 'analysis.txt')
    with open(prompt_path, 'r') as f:
        return f.read()


def parse_date(date_str: Optional[str]) -> Optional[datetime]:
    """Parse date string to datetime"""
    if not date_str:
        return None
    try:
        return datetime.fromisoformat(date_str.replace('Z', '+00:00'))
    except ValueError:
        pass
    try:
        from email.utils import parsedate_to_datetime
        return parsedate_to_datetime(date_str)
    except (ValueError, TypeError):
        return None


def record_failure(session, task_type: str, url: Optional[str],
                   article_id, error: Exception):
    """Record a failed task"""
    failure = FailedTask(
        task_type=task_type,
        article_url=url,
        article_id=article_id,
        exception_type=type(error).__name__,
        exception_message=str(error)
    )
    session.add(failure)
    session.commit()
    logger.error("failure_recorded", task_type=task_type, url=url)


def analyze_article(session, article, analyzer, prompt: str, correlation_id: str) -> bool:
    """Analyze an article using LLM"""
    result = analyzer.analyze(article.content, prompt)

    if result is None:
        record_failure(session, 'analyze', article.url, article.id,
                       Exception("Analysis returned None"))
        return False

    analysis = Analysis(
        article_id=article.id,
        correlation_id=uuid.UUID(correlation_id),
        tags=result.tags,
        pain_points=result.pain_points,
        insights=result.insights,
        innovations=result.innovations,
        model_used=LLM_MODEL,
        input_tokens=result.input_tokens,
        output_tokens=result.output_tokens
    )

    session.add(analysis)
    logger.info("analysis_completed",
                article_id=str(article.id),
                input_tokens=result.input_tokens,
                output_tokens=result.output_tokens)

    return True


def process_article(session, scraped, analyzer, prompt: str, correlation_id: str) -> bool:
    """Process and analyze a single article within a transaction"""
    url_hash = generate_url_hash(scraped.url)

    existing = session.query(Article).filter_by(url_hash=url_hash).first()
    if existing:
        logger.info("article_already_exists", url=scraped.url)
        if not has_analysis(session, existing.id):
            return analyze_article(session, existing, analyzer, prompt, correlation_id)
        return False

    article = Article(
        url=scraped.url,
        url_hash=url_hash,
        source=scraped.source,
        title=scraped.title,
        content=scraped.content,
        published_at=parse_date(scraped.published_at),
        correlation_id=uuid.UUID(correlation_id),
        metadata_=scraped.metadata
    )

    session.add(article)
    session.flush()

    success = analyze_article(session, article, analyzer, prompt, correlation_id)
    session.commit()
    logger.info("article_processed", url=scraped.url, article_id=str(article.id))

    return success


def process_article_safe(scraped, analyzer, prompt: str, correlation_id: str) -> bool:
    """Process a single article with error handling"""
    session = get_session()
    try:
        return process_article(session, scraped, analyzer, prompt, correlation_id)
    except Exception as e:
        logger.error("article_processing_failed", url=scraped.url, error=str(e))
        record_failure(session, 'scrape', scraped.url, None, e)
        return False
    finally:
        session.close()


def run_daily_scrape(start_time: float):
    """Run daily scraping (RSS + arXiv)"""
    global _shutdown_requested

    correlation_id = str(uuid.uuid4())
    bind_correlation_id(correlation_id)

    analyzer = ClaudeProvider(api_key=LLM_API_KEY, model=LLM_MODEL)
    prompt = load_prompt()

    all_articles = []

    for source_config in RSS_SOURCES:
        if _shutdown_requested or check_timeout(start_time):
            break
        scraper = RssScraper(url=source_config['url'], source=source_config['source'])
        articles = scraper.scrape()
        all_articles.extend(articles)
        logger.info("source_scraped", source=source_config['source'], count=len(articles))

    if not _shutdown_requested and not check_timeout(start_time):
        arxiv_scraper = ArxivScraper()
        arxiv_articles = arxiv_scraper.scrape()
        all_articles.extend(arxiv_articles)
        logger.info("source_scraped", source="arxiv", count=len(arxiv_articles))

    if len(all_articles) > BATCH_SIZE:
        logger.warning("batch_size_exceeded", total=len(all_articles), limit=BATCH_SIZE)
        all_articles = all_articles[:BATCH_SIZE]

    success_count = 0
    failure_count = 0

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = {
            executor.submit(process_article_safe, article, analyzer, prompt, correlation_id): article
            for article in all_articles
        }

        for future in as_completed(futures):
            if _shutdown_requested or check_timeout(start_time):
                logger.warning("processing_interrupted")
                break
            try:
                if future.result():
                    success_count += 1
                else:
                    failure_count += 1
            except Exception as e:
                failure_count += 1
                logger.error("future_exception", error=str(e))

    logger.info("daily_scrape_completed",
                success=success_count,
                failures=failure_count,
                total=len(all_articles))


def run_weekly_scrape(start_time: float):
    """Run weekly scraping (blogs)"""
    global _shutdown_requested

    correlation_id = str(uuid.uuid4())
    bind_correlation_id(correlation_id)

    analyzer = ClaudeProvider(api_key=LLM_API_KEY, model=LLM_MODEL)
    prompt = load_prompt()

    all_articles = []

    for source_config in BLOG_SOURCES:
        if _shutdown_requested or check_timeout(start_time):
            break
        scraper = BlogScraper(
            base_url=source_config['base_url'],
            source=source_config['source'],
            selectors=source_config['selectors']
        )
        articles = scraper.scrape()
        all_articles.extend(articles)
        logger.info("source_scraped", source=source_config['source'], count=len(articles))

    if len(all_articles) > BATCH_SIZE:
        all_articles = all_articles[:BATCH_SIZE]

    success_count = 0
    failure_count = 0

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = {
            executor.submit(process_article_safe, article, analyzer, prompt, correlation_id): article
            for article in all_articles
        }

        for future in as_completed(futures):
            if _shutdown_requested or check_timeout(start_time):
                break
            try:
                if future.result():
                    success_count += 1
                else:
                    failure_count += 1
            except Exception:
                failure_count += 1

    logger.info("weekly_scrape_completed", success=success_count, failures=failure_count)


def run_remediate():
    """Retry all unresolved failures"""
    correlation_id = str(uuid.uuid4())
    bind_correlation_id(correlation_id)

    session = get_session()

    failures = session.query(FailedTask).filter_by(resolved=False).all()

    if not failures:
        logger.info("no_failures_to_remediate")
        return

    analyzer = ClaudeProvider(api_key=LLM_API_KEY, model=LLM_MODEL)
    prompt = load_prompt()

    remediated = 0
    for failure in failures:
        if failure.task_type == 'analyze' and failure.article_id:
            article = session.get(Article, failure.article_id)
            if article and not has_analysis(session, article.id):
                if analyze_article(session, article, analyzer, prompt, correlation_id):
                    failure.resolved = True
                    failure.resolved_at = datetime.now(timezone.utc)
                    session.commit()
                    remediated += 1

    logger.info("remediation_completed", remediated=remediated, total=len(failures))
    session.close()


def main():
    """Main entry point"""
    configure_logging()

    args = parse_args()

    correlation_id = str(uuid.uuid4())
    bind_correlation_id(correlation_id)

    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)

    logger.info("execution_started", command=args.command, correlation_id=correlation_id)

    start_time = time.time()

    try:
        if args.command == 'daily':
            run_daily_scrape(start_time)
        elif args.command == 'weekly':
            run_weekly_scrape(start_time)
        elif args.command == 'remediate':
            run_remediate()
    except Exception as e:
        logger.error("execution_failed", error=str(e))
        raise
    finally:
        duration = time.time() - start_time
        logger.info("execution_completed", duration_seconds=duration)


if __name__ == '__main__':
    main()
