#!/usr/bin/env python
# scripts/backfill_tag_embeddings.py
"""
One-off script: embed all existing tags that have no embedding yet.

Usage:
    uv run python scripts/backfill_tag_embeddings.py [--limit N] [--dry-run]
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=0, help="Max tags to process (0 = all)")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    from src.shared.logging import get_logger
    logger = get_logger(__name__)

    from src.infrastructure.persistence.database import get_session, init_db
    from src.config.providers import load_tag_normalization_config
    from src.infrastructure.intelligence.embedding import GeminiEmbeddingProvider
    from sqlalchemy import text

    init_db()
    session = get_session()

    cfg = load_tag_normalization_config()
    provider = GeminiEmbeddingProvider(
        api_key=os.environ.get(cfg["api_key_env"], ""),
        model=cfg["embedding_model"],
    )

    # Fetch tags without embeddings
    query = "SELECT id, name FROM tags WHERE embedding IS NULL"
    if args.limit:
        query += f" LIMIT {args.limit}"
    rows = session.execute(text(query)).fetchall()

    logger.info("backfill_start", total=len(rows), dry_run=args.dry_run)

    batch_size = 50
    for i in range(0, len(rows), batch_size):
        batch = rows[i : i + batch_size]
        tag_ids = [str(r[0]) for r in batch]
        tag_names = [r[1] for r in batch]

        vectors = provider.embed_batch(tag_names)

        if not args.dry_run:
            for tag_id, vec in zip(tag_ids, vectors):
                vec_str = "[" + ",".join(str(x) for x in vec) + "]"
                session.execute(
                    text("UPDATE tags SET embedding = CAST(:vec AS vector) WHERE id = :id"),
                    {"vec": vec_str, "id": tag_id},
                )
            session.commit()

        logger.info("backfill_batch_done", batch_start=i, count=len(batch))

    logger.info("backfill_complete", total=len(rows))


if __name__ == "__main__":
    main()
