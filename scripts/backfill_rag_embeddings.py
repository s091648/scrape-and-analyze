#!/usr/bin/env python
# scripts/backfill_rag_embeddings.py
"""
Backfill dense (and optionally sparse) RAG embeddings for existing articles.

Fetches articles from the main DB that have not yet been ingested into the
vector store, then calls IngestProcessor to chunk and embed them.

Usage:
    # Local (uses DATABASE_URL + VECTOR_DB_* from .env):
    uv run python scripts/backfill_rag_embeddings.py [--limit N] [--dry-run]

    # Remote staging (default):
    uv run python scripts/backfill_rag_embeddings.py --remote [--limit N]

    # Remote production:
    uv run python scripts/backfill_rag_embeddings.py --remote --env production [--limit N]

Required env vars (from .env):
    VECTOR_DB_NAME, VECTOR_DB_USER, VECTOR_DB_PASSWORD, VECTOR_DB_HOST, VECTOR_DB_PORT
    EMBEDDING_MODEL_API, EMBEDDING_DIM
    REMOTE_RAILWAY_STAGING_DB_URL   (for --remote, default)
    REMOTE_RAILWAY_DB_URL           (for --remote --env production)

Optional env vars:
    SPARSE_EMBEDDING_MODEL_API   (enables SPLADE sparse ingestion)
"""
import argparse
import os
import sys
import uuid

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def main():
    parser = argparse.ArgumentParser(description="Backfill RAG embeddings for existing articles")
    parser.add_argument("--limit", type=int, default=0,
                        help="Max articles to process (0 = all)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Fetch and chunk articles without writing to vector store")
    parser.add_argument("--remote", action="store_true",
                        help="Use remote DATABASE_URL instead of local")
    parser.add_argument("--env", choices=["staging", "production"], default="staging",
                        help="Remote environment (requires --remote). Default: staging")
    args = parser.parse_args()

    if args.remote:
        if args.env == "production":
            remote_url = os.environ.get("REMOTE_RAILWAY_DB_URL", "")
            env_var = "REMOTE_RAILWAY_DB_URL"
        else:
            remote_url = os.environ.get("REMOTE_RAILWAY_STAGING_DB_URL", "")
            env_var = "REMOTE_RAILWAY_STAGING_DB_URL"
        if not remote_url:
            print(f"ERROR: {env_var} must be set in .env", file=sys.stderr)
            sys.exit(1)
        os.environ["DATABASE_URL"] = remote_url
        print(f"Using remote DB ({args.env}): {env_var}")

    from src.shared.logging import get_logger
    logger = get_logger(__name__)

    from src.infrastructure.persistence.database import get_session, init_db
    from sqlalchemy import text

    init_db()
    session = get_session()

    # ── Build IngestProcessor ──────────────────────────────────────────────────
    from chatbot_plugin_sdk import IngestProcessor, SyncPgBackend, DatabaseConfig, EndpointProvider

    embedding_dim = int(os.environ.get("DENSE_EMBEDDING_DIM", "768"))
    embedding_api = os.environ.get("DENSE_EMBEDDING_MODEL_API", "")
    if not embedding_api and not args.dry_run:
        print("ERROR: DENSE_EMBEDDING_MODEL_API must be set", file=sys.stderr)
        sys.exit(1)

    backend = SyncPgBackend(DatabaseConfig(
        dbname=os.environ.get("VECTOR_DB_NAME", ""),
        user=os.environ.get("VECTOR_DB_USER", ""),
        password=os.environ.get("VECTOR_DB_PASSWORD", ""),
        host=os.environ.get("VECTOR_DB_HOST", "localhost"),
        port=int(os.environ.get("VECTOR_DB_PORT", "5432")),
    ))

    dense_provider = EndpointProvider(url=embedding_api, dimension=embedding_dim)

    sparse_api = os.environ.get("SPARSE_EMBEDDING_MODEL_API", "")  # URL only; "local" not supported in backfill script
    sparse_provider = None
    if sparse_api:
        sparse_provider = EndpointProvider(url=sparse_api, response_key="sparse")
        logger.info("sparse_embedding_enabled", api=sparse_api)
    else:
        logger.info("sparse_embedding_disabled_no_api_set")

    processor = IngestProcessor()
    processor.configure(backend=backend, dense=dense_provider, sparse=sparse_provider)

    # ── Fetch articles not yet in vector store ─────────────────────────────────
    # Uses UUID5(NAMESPACE_URL, url) to match the article_id convention in IngestProcessor
    query = text("""
        SELECT id, url, title, content, metadata_
        FROM articles
        WHERE url IS NOT NULL AND content IS NOT NULL AND LENGTH(TRIM(content)) > 0
        ORDER BY scraped_at DESC
    """ + (" LIMIT :limit" if args.limit else ""))

    params = {"limit": args.limit} if args.limit else {}
    rows = session.execute(query, params).fetchall()

    logger.info("backfill_rag_start", total=len(rows), dry_run=args.dry_run,
                env=args.env if args.remote else "local")
    print(f"Found {len(rows)} articles to process")

    done = 0
    skipped = 0
    failed = 0

    for row in rows:
        article_id = str(row[0])
        article_url = row[1]
        article_title = row[2] or ""
        content = row[3] or ""
        metadata = row[4] or {}

        # Skip short content
        if len(content.strip()) < 50:
            skipped += 1
            continue

        if args.dry_run:
            done += 1
            if done % 50 == 0:
                print(f"  [dry-run] processed {done}/{len(rows)}")
            continue

        try:
            processor.ingest(
                content,
                metadata={
                    "url": article_url,
                    "title": article_title,
                    "public_article_id": article_id,
                    **metadata,
                },
            )
            done += 1
            if done % 10 == 0:
                logger.info("backfill_rag_progress", done=done, total=len(rows))
                print(f"  Ingested {done}/{len(rows)}")
        except Exception as exc:
            failed += 1
            logger.error("backfill_rag_article_failed", url=article_url,
                         error=type(exc).__name__, detail=str(exc))

    logger.info("backfill_rag_complete", done=done, skipped=skipped, failed=failed, total=len(rows))
    print(f"\nDone: {done} ingested, {skipped} skipped (short content), {failed} failed")


if __name__ == "__main__":
    main()
