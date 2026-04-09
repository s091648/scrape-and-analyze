"""
CompositionRoot — wires every dependency together and returns a ready-to-run
RunScraperUseCase.

Called once from main() so that main.py stays free of construction logic.

Session strategy: process_uc_factory opens a fresh SQLAlchemy session per
article, passes it into ProcessArticleUseCase, and closes it when done.
RunScraperUseCase calls the factory for every scraped article.
"""
import os

from src.utils.logging import get_logger

logger = get_logger(__name__)


def build_analyzer():
    """Build a ProviderChain from providers.toml."""
    from src.analysis.provider_chain import ProviderChain, ProviderHandler
    from src.analysis.strategies.leaky_bucket_strategy import LeakyBucketStrategy
    from src.analysis.strategies.no_op_strategy import NoOpStrategy
    from src.analysis.providers.gemini import GeminiProvider
    from src.analysis.providers.openrouter import OpenRouterProvider
    from src.config.providers import load_providers

    handlers = []
    for cfg in load_providers():
        name = cfg['name']
        model = cfg['model']
        api_key = os.environ.get(cfg['api_key_env'], '')

        if name == 'gemini':
            provider = GeminiProvider(api_key=api_key, model=model)
        elif name == 'openrouter':
            provider = OpenRouterProvider(api_key=api_key, model=model)
        else:
            logger.warning("unknown_provider_skipped", name=name)
            continue

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


def build_run_scraper_use_case(prompt: str, summary=None):
    """
    Instantiate and wire all dependencies. Returns a RunScraperUseCase.

    The process_uc_factory closure is called once per scraped article.
    It opens a fresh SQLAlchemy session for the full article+analysis
    pipeline and returns (ProcessArticleUseCase, session) so the caller
    can close the session after execute() returns.
    """
    from src.infrastructure.persistence.sqlalchemy_repos.scraper_setting_repo_impl import (
        SqlAlchemyScraperSettingRepository,
    )
    from src.infrastructure.persistence.sqlalchemy_repos.article_repo_impl import (
        SqlAlchemyArticleRepository,
    )
    from src.infrastructure.persistence.sqlalchemy_repos.analysis_repo_impl import (
        SqlAlchemyAnalysisRepository,
    )
    from src.domain.services.dedup_service import DedupService
    from src.app.use_cases.analyze_article import AnalyzeArticleUseCase
    from src.app.use_cases.process_article import ProcessArticleUseCase
    from src.app.use_cases.run_scraper import RunScraperUseCase
    from src.ingestion.services.scraper_service import ScraperService
    from src.pipeline.dispatcher import ScrapeDispatcher
    from src.database import get_session

    analyzer = build_analyzer()
    setting_repo = SqlAlchemyScraperSettingRepository()
    dispatcher = ScrapeDispatcher(num_workers=3, delay=5.0)
    scraper_svc = ScraperService(dispatcher=dispatcher)

    def process_uc_factory():
        session = get_session()
        from src.infrastructure.persistence.sqlalchemy_repos.arxiv_metadata_repo_impl import (
            SqlAlchemyArxivMetadataRepository,
        )
        article_repo = SqlAlchemyArticleRepository(session=session)
        analysis_repo = SqlAlchemyAnalysisRepository(session=session)
        arxiv_metadata_repo = SqlAlchemyArxivMetadataRepository(session=session)
        dedup_svc = DedupService(article_repo=article_repo)
        analyze_uc = AnalyzeArticleUseCase(
            analyzer=analyzer,
            analysis_repo=analysis_repo,
        )
        process_uc = ProcessArticleUseCase(
            article_repo=article_repo,
            dedup_service=dedup_svc,
            analyze_article_uc=analyze_uc,
            arxiv_metadata_repo=arxiv_metadata_repo,
        )
        return process_uc, session

    return RunScraperUseCase(
        scraper_setting_repo=setting_repo,
        scraper_service=scraper_svc,
        process_uc_factory=process_uc_factory,
        prompt=prompt,
    )
