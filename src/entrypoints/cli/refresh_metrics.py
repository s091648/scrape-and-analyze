"""
Recurring metric refresh CLI entrypoint — keeps catalog-defined recommendation
signals (citation_count today; future impact_factor/h-index) fresh for
previously-scraped articles, independent of the initial scrape.

Usage:
    uv run python -m src.entrypoints.cli.refresh_metrics
    uv run python -m src.entrypoints.cli.refresh_metrics --limit 200

Deployed as its own Railway Cron Service (see src/railway.toml), separate from
both the weekly report runner and the backend's view_count Redis flush —
research.md §9b explains why these three don't share a runner.

Architecture:
    - Domain: MetricExtractor interface (src/modules/collection/domain/services/).
    - Infrastructure: ResilientMetricsService, JsonPathMetricExtractor
      (src/infrastructure/collection/metrics/), generalized
      ArticleMetricsRepository.upsert().
    - Bootstrap: build_metrics_refresh_pipeline() reads the metric_definitions
      catalog from DB and wires the fetcher registry.
"""
import argparse

from sqlalchemy import text

from src.config.settings import APP_ENV, SENTRY_DSN, validate_config
from src.shared.logging import get_logger
from src.infrastructure.shared.logging import bind_correlation_id, configure_logging
from src.infrastructure.shared.http import HttpClient, init_default_client
from src.infrastructure.shared.observability import init_run_context


if SENTRY_DSN:
    import sentry_sdk
    sentry_sdk.init(dsn=SENTRY_DSN, environment=APP_ENV, traces_sample_rate=0.1, include_local_variables=False)

logger = get_logger(__name__)

# Articles missing (or with a stale) article_metric_values row for any enabled
# metric_key, restricted to articles that actually carry a DOI/arxiv_id (the
# only identifiers current metric providers can look up by) — see
# research.md §9e for the expression indexes this query relies on.
_STALE_ARTICLES_QUERY = text(
    """
    SELECT a.id, a.metadata
    FROM articles a
    WHERE (a.metadata->>'doi' IS NOT NULL OR a.metadata->>'arxiv_id' IS NOT NULL)
      AND EXISTS (
          SELECT 1 FROM unnest(:metric_keys) AS mk(metric_key)
          WHERE NOT EXISTS (
              SELECT 1 FROM article_metric_values amv
              WHERE amv.article_id = a.id
                AND amv.metric_key = mk.metric_key
                AND amv.last_flushed_at >= now() - interval '1 day'
          )
      )
    LIMIT :limit
    """
)


def main() -> None:
    """CLI entry point: refreshes catalog-defined metrics for stale articles."""
    from opentelemetry import trace as otel_trace
    from src.infrastructure.shared.observability import get_tracer, shutdown_tracing
    from shared.enums.observability import SpanName, SpanAttribute

    parser = argparse.ArgumentParser(description="Refresh recommendation-signal metrics (citation_count, etc.)")
    parser.add_argument("--limit", type=int, default=200, help="Max number of articles to refresh per run")
    args = parser.parse_args()

    validate_config()
    configure_logging()
    init_default_client(HttpClient.build_default())

    run_id, correlation_id = init_run_context()
    bind_correlation_id(correlation_id)

    tracer = get_tracer()
    try:
        with tracer.start_as_current_span(SpanName.REFRESH_METRICS_RUN) as span:
            span.set_attribute(SpanAttribute.RUN_ID, run_id)
            span.set_attribute(SpanAttribute.CORRELATION_ID, correlation_id)

            session = None
            try:
                from src.bootstrap import build_metrics_refresh_pipeline
                metrics_service, metrics_repo, session = build_metrics_refresh_pipeline()

                enabled_metric_keys = metrics_service.tracked_metric_keys
                if not enabled_metric_keys:
                    logger.warning("no_enabled_metric_definitions")
                    print("No enabled metric definitions found — nothing to refresh")
                    return

                rows = session.execute(
                    _STALE_ARTICLES_QUERY,
                    {"metric_keys": enabled_metric_keys, "limit": args.limit},
                ).fetchall()
                logger.info("stale_articles_found", count=len(rows), metric_keys=enabled_metric_keys)

                refreshed = 0
                failed = 0
                for row in rows:
                    article_id, metadata = row.id, row.metadata or {}
                    identifiers = {
                        k: v for k, v in {"doi": metadata.get("doi"), "arxiv_id": metadata.get("arxiv_id")}.items()
                        if v
                    }
                    if not identifiers:
                        continue
                    try:
                        metrics = metrics_service.fetch_all(identifiers)
                        if metrics:
                            metrics_repo.upsert(article_id, metrics)
                            refreshed += 1
                            logger.info("article_metrics_refreshed", article_id=str(article_id), metrics=list(metrics.keys()))
                    except Exception as e:
                        failed += 1
                        logger.warning("article_metrics_refresh_failed", article_id=str(article_id), error=str(e))

                logger.info("metrics_refresh_completed", total=len(rows), refreshed=refreshed, failed=failed)
                print(f"Metrics refresh complete: {refreshed}/{len(rows)} articles refreshed ({failed} failed)")
            except Exception as e:
                span.record_exception(e)
                span.set_status(otel_trace.StatusCode.ERROR, str(e))
                raise
            finally:
                if session is not None:
                    session.close()
    finally:
        shutdown_tracing()


if __name__ == "__main__":
    main()
