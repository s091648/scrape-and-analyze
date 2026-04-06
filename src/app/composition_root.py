"""
CompositionRoot — wires every dependency together and returns a ready-to-run
RunScraperUseCase.

Called once from main() so that main.py stays free of construction logic.

Session strategy: each on_result callback opens one SQLAlchemy session that
spans the entire process_article → analyze_article pipeline, then commits
(in analysis_repo.save) and closes.
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

    Session-per-article strategy:
    ProcessArticleUseCase.execute() is called once per scraped article.
    We wrap it so that each call opens a fresh SQLAlchemy session, uses it
    for the full article+analysis pipeline, and closes it when done.
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

    def make_process_uc():
        """
        Build a ProcessArticleUseCase backed by a shared session.
        The session is committed inside SqlAlchemyAnalysisRepository.save()
        and must be closed by the caller after execute() returns.
        """
        session = get_session()
        article_repo = SqlAlchemyArticleRepository(session=session)
        analysis_repo = SqlAlchemyAnalysisRepository(session=session)
        dedup_svc = DedupService(article_repo=article_repo)
        analyze_uc = AnalyzeArticleUseCase(
            analyzer=analyzer,
            analysis_repo=analysis_repo,
        )
        return ProcessArticleUseCase(
            article_repo=article_repo,
            dedup_service=dedup_svc,
            analyze_article_uc=analyze_uc,
        ), session

    # Wrap RunScraperUseCase so each article gets its own session
    class _SessionPerArticleRunUseCase:
        def __init__(self):
            self._setting_repo = setting_repo
            self._scraper_svc = scraper_svc
            self._prompt = prompt

        def execute(self, correlation_id: str, summary=None) -> None:
            from src.utils.logging import get_logger as _gl
            _log = _gl(__name__)

            sources = self._setting_repo.get_sources_due()
            if not sources:
                _log.info("no_sources_due")
                return

            _log.info("sources_due", count=len(sources))

            def on_result(scraped) -> None:
                process_uc, session = make_process_uc()
                try:
                    process_uc.execute(scraped, self._prompt, correlation_id, summary)
                finally:
                    session.close()

            completed_sources = self._scraper_svc.run(sources, on_result)

            for source in completed_sources:
                try:
                    self._setting_repo.mark_scraped(source["id"])
                except Exception as e:
                    _log.warning("mark_scraped_failed",
                                 source_id=source["id"], error=str(e))

    return _SessionPerArticleRunUseCase()
