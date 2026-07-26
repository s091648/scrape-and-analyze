#!/usr/bin/env python
# scripts/backfill_tag_embeddings.py
"""
One-off script: embed all existing tags and tag_group_definitions that have
no embedding yet.

Usage:
    uv run python scripts/backfill_tag_embeddings.py [--limit N] [--dry-run]
    uv run python scripts/backfill_tag_embeddings.py --only tags
    uv run python scripts/backfill_tag_embeddings.py --only tag-groups
    uv run python scripts/backfill_tag_embeddings.py --remote
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def build_embedding_service(session):
    from typing import List
    from shared.llm_provider import load_active_embedding_providers
    from src.infrastructure.intelligence.llm.resilient_llm_service import (
        ResilientEmbeddingService, EmbeddingProviderHandler
    )
    from src.infrastructure.intelligence.llm.embedding import GeminiEmbeddingProvider
    from src.infrastructure.intelligence.llm.rate_limit import SlidingWindowStrategy, NoOpStrategy
    from src.shared.logging import get_logger

    logger = get_logger(__name__)
    emb_handlers: List[EmbeddingProviderHandler] = []

    for emb_cfg in load_active_embedding_providers(session):
        name = emb_cfg['name']
        api_key = os.environ.get(emb_cfg['api_key_env'], '')

        if name == 'gemini':
            provider = GeminiEmbeddingProvider(api_key=api_key, model=emb_cfg['model'])
        else:
            logger.warning("unknown_embedding_provider_skipped", name=name)
            continue

        s = emb_cfg.get('strategy', {})
        if s.get('type') == 'sliding_window':
            strategy = SlidingWindowStrategy(rpm=s['rpm'], tpm=s['tpm'], rpd=s['rpd'])
        else:
            strategy = NoOpStrategy()

        emb_handlers.append(EmbeddingProviderHandler(
            provider=provider,
            strategy=strategy,
            priority=emb_cfg['priority'],
            name=name,
        ))

    if not emb_handlers:
        raise ValueError("llm_providers table 中未設定任何有效的 Embedding provider")

    return ResilientEmbeddingService(handlers=emb_handlers)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=0,
                        help="Max rows to process per table (0 = all)")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--only", choices=["tags", "tag-groups"], default=None,
                        help="Restrict to one table only")
    parser.add_argument("--remote", action="store_true",
                        help="Use REMOTE_RAILWAY_DB_URL instead of DATABASE_URL")
    args = parser.parse_args()

    if args.remote:
        remote_url = os.environ.get("REMOTE_RAILWAY_DB_URL", "")
        if not remote_url:
            print("ERROR: REMOTE_RAILWAY_DB_URL must be set in .env", file=sys.stderr)
            sys.exit(1)
        os.environ["DATABASE_URL"] = remote_url

    if not os.environ.get("DATABASE_URL"):
        print("ERROR: DATABASE_URL environment variable is required", file=sys.stderr)
        sys.exit(1)

    from src.shared.logging import get_logger
    logger = get_logger(__name__)

    from src.infrastructure.persistence.database import get_session, init_db
    from sqlalchemy import text

    init_db()
    session = get_session()

    provider = build_embedding_service(session)
    batch_size = 10

    def embed_table(table: str, text_col: str, label: str):
        query = f"SELECT id, {text_col} FROM {table} WHERE embedding IS NULL"
        if args.limit:
            query += f" LIMIT {args.limit}"
        rows = session.execute(text(query)).fetchall()

        logger.info(f"backfill_{label}_start", total=len(rows), dry_run=args.dry_run)

        for i in range(0, len(rows), batch_size):
            batch = rows[i : i + batch_size]
            ids = [str(r[0]) for r in batch]
            texts = [r[1] for r in batch]

            vectors = provider.embed_batch(texts)

            if not args.dry_run:
                for row_id, vec in zip(ids, vectors):
                    vec_str = "[" + ",".join(str(x) for x in vec) + "]"
                    session.execute(
                        text(f"UPDATE {table} SET embedding = CAST(:vec AS vector) WHERE id = :id"),
                        {"vec": vec_str, "id": row_id},
                    )
                session.commit()

            logger.info(f"backfill_{label}_batch_done", batch_start=i, count=len(batch))

        logger.info(f"backfill_{label}_complete", total=len(rows))

    only = args.only

    if only != "tag-groups":
        embed_table("tags", "name", "tags")

    if only != "tags":
        embed_table("tag_group_definitions", "name", "tag_group_defs")


if __name__ == "__main__":
    main()
