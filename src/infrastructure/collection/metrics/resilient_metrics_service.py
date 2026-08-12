"""
ResilientMetricsService — mirrors ResilientLLMService (src/infrastructure/intelligence/llm/):
walks an ordered list of MetricExtractor handlers per metric_key (by priority),
falling back to the next provider on failure or a null result.
"""
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional

from src.shared.logging import get_logger
from src.modules.collection.domain.services import MetricExtractor
from src.infrastructure.collection.clients.rate_limit_errors import ProviderRateLimitedError
from src.infrastructure.collection.metrics.json_path_extractor import JsonPathMetricExtractor

logger = get_logger(__name__)


def build_provider_fetchers() -> Dict[str, Callable[[Dict[str, str]], Optional[dict]]]:
    """Fixed registry mapping provider_name -> a callable that fetches the raw
    response for one article, given its known identifiers. This is the only
    place a brand-new external provider needs to be registered in code — see
    research.md §9f. metric_definitions.provider_name selects an entry here,
    the same way LlmProvider.name selects a concrete provider class in
    src/bootstrap.py::build_llm_service.
    """
    from src.infrastructure.shared.http import get_default_client
    from src.infrastructure.collection.clients.openalex_client import OpenAlexClient
    from src.infrastructure.collection.clients.semantic_scholar_client import SemanticScholarClient

    # 429 from these APIs means a quota/pool limit, not a transient blip — retrying
    # only burns the run's wall-clock time (see scraper_factory.py's identical
    # with_skip_retry_status treatment for the same two providers at scrape time).
    no_429_retry_http = get_default_client().with_skip_retry_status(frozenset({429}))
    openalex_client = OpenAlexClient(http_client=no_429_retry_http)
    semantic_scholar_client = SemanticScholarClient(http_client=no_429_retry_http)

    return {
        "openalex": lambda ids: openalex_client.fetch_by_doi(ids["doi"]) if ids.get("doi") else None,
        "semantic_scholar": lambda ids: semantic_scholar_client.fetch_by_doi(ids["doi"]) if ids.get("doi") else None,
        # OpenAlex has no arXiv-ID lookup (only DOI/PMID/PMCID/MAG ID); Semantic Scholar does
        # (paper/ARXIV:<id>) — this is the only provider that can resolve a metric for arXiv
        # preprints that don't (yet) have a DOI. See alembic 23's semantic_scholar_arxiv seed row.
        "semantic_scholar_arxiv": lambda ids: semantic_scholar_client.fetch_by_arxiv_id(ids["arxiv_id"]) if ids.get("arxiv_id") else None,
    }


# Fixed registry for extractor_type='code' metric_definitions rows. The DB only
# ever selects a key here (metric_definitions.extractor_spec.key) — it never
# supplies executable code (FR-023). Empty today; populate when a metric needs
# genuinely custom fetch/extract logic beyond a JMESPath field lookup.
CODE_EXTRACTOR_REGISTRY: Dict[str, MetricExtractor] = {}


@dataclass
class MetricHandler:
    """Pairs one metric_definitions row (resolved to a MetricExtractor instance)
    with its priority within a metric_key's fallback chain."""
    metric_key: str
    provider_name: str
    priority: int
    extractor: MetricExtractor
    extractor_spec: Dict[str, Any]


class ResilientMetricsService:
    """Walks each metric_key's provider list in priority order, keeping the
    first non-null result. Metric keys are independent of each other."""

    def __init__(self, handlers: List[MetricHandler]) -> None:
        self._by_metric_key: Dict[str, List[MetricHandler]] = {}
        for h in sorted(handlers, key=lambda handler: handler.priority):
            self._by_metric_key.setdefault(h.metric_key, []).append(h)
        # Run-scoped memory of providers that have already raised
        # ProviderRateLimitedError once — mirrors ScrapeExecutor._aborted_hosts.
        # DomainRateLimiter's circuit breaker (shared/http/rate_limiter.py) already
        # stops real HTTP calls to the domain, but this instance has no equivalent
        # of ScrapeExecutor to skip calling fetch() at all for the remaining
        # articles in a refresh_metrics run — without this, every subsequent
        # article still pays a thread hop + two log lines per exhausted provider.
        self._exhausted_providers: set[str] = set()

    @property
    def tracked_metric_keys(self) -> List[str]:
        """The metric_keys this service has at least one enabled provider for."""
        return list(self._by_metric_key.keys())

    def fetch_all(self, article_identifiers: Dict[str, str]) -> Dict[str, Any]:
        """For each tracked metric_key, try each provider in priority order until
        one returns a non-null value. Returns {metric_key: value} only for
        metrics that resolved to a value — silent on ones that didn't."""
        results: Dict[str, Any] = {}
        for metric_key, handlers in self._by_metric_key.items():
            for handler in handlers:
                if handler.provider_name in self._exhausted_providers:
                    continue
                try:
                    raw = handler.extractor.fetch(article_identifiers)
                    if raw is None:
                        continue
                    value = handler.extractor.extract(raw, handler.extractor_spec)
                    if value is not None:
                        results[metric_key] = value
                        break
                except ProviderRateLimitedError as e:
                    self._exhausted_providers.add(handler.provider_name)
                    logger.warning(
                        "metric_provider_exhausted_for_run",
                        metric_key=metric_key,
                        provider=handler.provider_name,
                        error=str(e),
                    )
                except Exception as e:
                    logger.warning(
                        "metric_extractor_failed",
                        metric_key=metric_key,
                        provider=handler.provider_name,
                        error=str(e),
                    )
        return results


def build_resilient_metrics_service(metric_definitions: List[Dict[str, Any]]) -> ResilientMetricsService:
    """Build a ResilientMetricsService from DB-loaded metric_definitions rows
    (shared/metric_definition.py::load_enabled_metric_definitions)."""
    fetchers = build_provider_fetchers()
    handlers: List[MetricHandler] = []
    for cfg in metric_definitions:
        provider_name = cfg["provider_name"]
        extractor_type = cfg["extractor_type"]

        if extractor_type == "json_path":
            fetcher = fetchers.get(provider_name)
            if fetcher is None:
                logger.warning("unknown_metric_provider_skipped", provider=provider_name)
                continue
            extractor: Optional[MetricExtractor] = JsonPathMetricExtractor(provider_name, fetcher)
        elif extractor_type == "code":
            extractor = CODE_EXTRACTOR_REGISTRY.get(cfg["extractor_spec"].get("key"))
            if extractor is None:
                logger.warning("unknown_metric_extractor_skipped", key=cfg["extractor_spec"].get("key"))
                continue
        else:
            logger.warning("unknown_extractor_type_skipped", extractor_type=extractor_type)
            continue

        handlers.append(MetricHandler(
            metric_key=cfg["metric_key"],
            provider_name=provider_name,
            priority=cfg["priority"],
            extractor=extractor,
            extractor_spec=cfg["extractor_spec"],
        ))

    return ResilientMetricsService(handlers)
