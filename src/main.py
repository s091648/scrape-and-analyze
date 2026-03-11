import uuid
import time
import signal
import os
from typing import Optional
from datetime import datetime, timezone
from sqlalchemy import text

from src.utils.logging import get_logger, bind_correlation_id, configure_logging
from src.config import load_providers, SENTRY_DSN
from src.analyzers.providers.gemini import GeminiProvider
from src.analyzers.providers.openrouter import OpenRouterProvider

# Initialize Sentry if configured
if SENTRY_DSN:
    import sentry_sdk
    sentry_sdk.init(
        dsn=SENTRY_DSN,
        traces_sample_rate=0.1,
    )
from src.database import get_session, has_analysis, init_db
from src.scrapers.scrapers.rss_scraper import RssScraper
from src.scrapers.scrapers.arxiv_scraper import ArxivScraper
from src.scrapers.scrapers.blog_scraper import BlogScraper
from models.article import Article
from models.analysis import Analysis
from models.failed_task import FailedTask
from src.utils.sanitizer import generate_url_hash
from src.scrapers.content_parsers import prepare_content_for_analysis

logger = get_logger(__name__)

MAX_WORKERS = 3
MAX_EXECUTION_TIME = 50 * 60  # 50 minutes
BATCH_SIZE = 50

# Global flag for graceful shutdown
_shutdown_requested = False


def build_analyzer():
    """Build a ProviderChain from providers.toml (lazy imports per provider SDK)."""
    from src.analyzers.provider_chain import ProviderChain, ProviderHandler
    from src.analyzers.strategies.leaky_bucket_strategy import LeakyBucketStrategy
    from src.analyzers.strategies.no_op_strategy import NoOpStrategy

    handlers = []
    for cfg in load_providers():
        name = cfg['name']
        model = cfg['model']
        api_key = os.environ.get(cfg['api_key_env'], '')

        # Instantiate provider
        if name == 'gemini':
            provider = GeminiProvider(api_key=api_key, model=model)
        elif name == 'openrouter':
            provider = OpenRouterProvider(api_key=api_key, model=model)
        else:
            logger.warning("unknown_provider_skipped", name=name)
            continue

        # Instantiate strategy
        s_cfg = cfg.get('strategy', {})
        if s_cfg.get('type') == 'leaky_bucket':
            strategy = LeakyBucketStrategy(
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
        raise ValueError("No valid providers configured in providers.toml")

    return ProviderChain(handlers=handlers)


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
    from models.tag import Tag

    llm_content = prepare_content_for_analysis(article)
    result = analyzer.analyze(llm_content, prompt)

    if result is None:
        record_failure(session, 'analyze', article.url, article.id,
                       Exception("Analysis returned None"))
        return False

    analysis = Analysis(
        article_id=article.id,
        correlation_id=uuid.UUID(correlation_id),
        pain_points=result.pain_points,
        insights=result.insights,
        innovations=result.innovations,
        model_used=result.model_used,
        input_tokens=result.input_tokens,
        output_tokens=result.output_tokens
    )
    session.add(analysis)

    for tg in (result.tag_groups or []):
        group_name = tg.get('group', '')
        for tag_name in tg.get('tags', []):
            if not tag_name or not group_name:
                continue
            tag = session.query(Tag).filter_by(
                name=tag_name, tag_group_name=group_name
            ).first()
            if not tag:
                tag = Tag(name=tag_name, tag_group_name=group_name)
                session.add(tag)
                session.flush()
            if tag not in article.tags:
                article.tags.append(tag)

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


def run_scrape_cycle(sources: list, analyzer, prompt: str, correlation_id: str) -> None:
    """Scrape and analyze all provided sources, update last_scraped_at per source."""
    for source in sources:
        source_type = source['source_type']
        logger.info("scrape_source_start", source=source['source'], source_type=source_type)

        try:
            if source_type == 'rss':
                scraper = RssScraper(url=source['url'], source=source['source'])
            elif source_type == 'blog':
                scraper = BlogScraper(
                    base_url=source['base_url'],
                    source=source['source'],
                    selectors=source['selectors'],
                )
            elif source_type == 'arxiv':
                cfg = source.get('selector_config', {})
                scraper = ArxivScraper(
                    max_results=cfg.get('max_results', 30),
                    days_back=cfg.get('days_back', 1),
                )
            else:
                logger.warning("unknown_source_type_skipped", source_type=source_type)
                continue

            articles = scraper.scrape()
            logger.info("source_scraped", source=source['source'], count=len(articles))

            for article in articles:
                if _shutdown_requested or check_timeout(time.time()):
                    return
                process_article_safe(article, analyzer, prompt, correlation_id)

        except Exception as e:
            logger.error("source_scrape_failed", source=source['source'], error=str(e))
            continue

        # Update last_scraped_at
        session = get_session()
        try:
            session.execute(
                text("UPDATE scraper_settings SET last_scraped_at = NOW() WHERE id = :id"),
                {"id": source['id']}
            )
            session.commit()
        finally:
            session.close()


def run_remediate():
    """Retry all unresolved failures"""
    correlation_id = str(uuid.uuid4())
    bind_correlation_id(correlation_id)

    session = get_session()

    failures = session.query(FailedTask).filter_by(resolved=False).all()

    if not failures:
        logger.info("no_failures_to_remediate")
        return

    analyzer = build_analyzer()
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


def main() -> None:
    """Main entry point — frequency-based scrape dispatch."""
    configure_logging()

    correlation_id = str(uuid.uuid4())
    bind_correlation_id(correlation_id)

    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)

    logger.info("execution_started", correlation_id=correlation_id)

    init_db()

    start_time = time.time()

    try:
        from src.config import get_sources_due
        sources_due = get_sources_due()

        if not sources_due:
            logger.info("no_sources_due")
            return

        logger.info("sources_due_count", count=len(sources_due))

        analyzer = build_analyzer()
        prompt = load_prompt()

        run_scrape_cycle(sources_due, analyzer, prompt, correlation_id)

    except Exception as e:
        logger.error("execution_failed", error=str(e))
        raise
    finally:
        duration = time.time() - start_time
        logger.info("execution_completed", duration_seconds=duration)


if __name__ == '__main__':
    main()
