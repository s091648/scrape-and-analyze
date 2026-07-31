"""
Recurring OpenAlex duplicate-reconciliation CLI entrypoint — catches articles
that OpenAlex indexed as two separate works because its own dedup hadn't
finished yet at scrape time, and merges them once OpenAlex resolves it.

Usage:
    uv run python -m src.entrypoints.cli.dedup_reconcile
    uv run python -m src.entrypoints.cli.dedup_reconcile --limit 200

Deployed as its own Railway Cron Service (see src/railway.toml), independent
of refresh_metrics.py and the scraper worker.

How it works:
    For each openalex-sourced article not reconciled in the last week, refetch
    its stored work_id. OpenAlex transparently 301-redirects a merged-away
    work_id to the surviving work, so a returned id that differs from what we
    stored means OpenAlex has since deduped it:
      - No local article exists under the survivor's work_id → we never
        scraped it separately; just heal this article's own work_id/doi to
        the canonical values (no merge needed).
      - A local article already exists under the survivor's work_id → true
        in-DB duplicate. Tombstone the loser via merged_into_id (roll up its
        view_count and tags into the survivor). Nothing is ever deleted —
        several FKs into `articles` have no ON DELETE action.
"""
import argparse

from sqlalchemy import text

from src.config.settings import SENTRY_DSN, validate_config
from src.shared.logging import get_logger
from src.infrastructure.shared.logging import bind_correlation_id, configure_logging
from src.infrastructure.shared.http import HttpClient, init_default_client
from src.infrastructure.shared.observability import init_run_context


if SENTRY_DSN:
    import sentry_sdk
    sentry_sdk.init(dsn=SENTRY_DSN, traces_sample_rate=0.1, include_local_variables=False)

logger = get_logger(__name__)

# Openalex-sourced articles not yet re-checked in the last week — OpenAlex's
# own dedup typically resolves within days of a work being indexed, but there's
# no hard SLA, so we keep re-checking weekly rather than giving up after once.
_PENDING_RECONCILIATION_QUERY = text(
    """
    SELECT a.id, a.metadata->>'work_id' AS work_id
    FROM articles a
    WHERE a.metadata->>'work_id' IS NOT NULL
      AND a.merged_into_id IS NULL
      AND (a.last_reconciled_at IS NULL OR a.last_reconciled_at < now() - interval '7 days')
    LIMIT :limit
    """
)


def main() -> None:
    """CLI entry point: reconciles OpenAlex work_ids that were deduped after we scraped them."""
    from opentelemetry import trace as otel_trace
    from src.infrastructure.shared.observability import get_tracer, shutdown_tracing
    from shared.enums.observability import SpanName, SpanAttribute

    parser = argparse.ArgumentParser(description="Detect and merge OpenAlex works deduped after we scraped them")
    parser.add_argument("--limit", type=int, default=200, help="Max number of articles to check per run")
    args = parser.parse_args()

    validate_config()
    configure_logging()
    init_default_client(HttpClient.build_default())

    run_id, correlation_id = init_run_context()
    bind_correlation_id(correlation_id)

    tracer = get_tracer()
    try:
        with tracer.start_as_current_span(SpanName.DEDUP_RECONCILE_RUN) as span:
            span.set_attribute(SpanAttribute.RUN_ID, run_id)
            span.set_attribute(SpanAttribute.CORRELATION_ID, correlation_id)

            session = None
            try:
                from src.bootstrap import build_dedup_reconciliation_pipeline
                client, dedup_repo, session = build_dedup_reconciliation_pipeline()

                rows = session.execute(_PENDING_RECONCILIATION_QUERY, {"limit": args.limit}).fetchall()
                logger.info("dedup_reconcile_candidates_found", count=len(rows))

                healed = 0
                merged = 0
                failed = 0
                for row in rows:
                    article_id, work_id = row.id, row.work_id
                    try:
                        raw = client.fetch_by_id(work_id)
                        if raw is None:
                            failed += 1
                            continue

                        canonical_work_id = raw.get("id")
                        if not canonical_work_id or canonical_work_id == work_id:
                            dedup_repo.mark_reconciled(article_id)
                            continue

                        ids = raw.get("ids") or {}
                        canonical_doi_url = ids.get("doi") or raw.get("doi")
                        canonical_doi = canonical_doi_url.replace("https://doi.org/", "") if canonical_doi_url else None

                        survivor_id = dedup_repo.find_by_work_id(canonical_work_id)
                        if survivor_id is None or survivor_id == article_id:
                            dedup_repo.heal_identifiers(article_id, canonical_work_id, canonical_doi)
                            healed += 1
                            logger.info(
                                "dedup_reconcile_healed",
                                article_id=str(article_id),
                                canonical_work_id=canonical_work_id,
                            )
                            continue

                        dedup_repo.merge(loser_id=article_id, survivor_id=survivor_id)
                        merged += 1
                        logger.info(
                            "dedup_reconcile_merged",
                            loser_id=str(article_id),
                            survivor_id=str(survivor_id),
                        )
                    except Exception as e:
                        failed += 1
                        logger.warning("dedup_reconcile_failed", article_id=str(article_id), error=str(e))

                logger.info("dedup_reconcile_completed", total=len(rows), healed=healed, merged=merged, failed=failed)
                print(f"Dedup reconciliation complete: {healed} healed, {merged} merged, {failed} failed (of {len(rows)} checked)")
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
