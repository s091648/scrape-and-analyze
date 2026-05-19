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
    from sqlalchemy import text

    init_db()
    session = get_session()

    def build_llm_service():
        """
        Prompt 不在此處注入——每次 analyze() call 時由 AnalyzeArticleUseCase
        根據 article.topic_id 動態 render 後傳入。
        """
        from typing import List
        from src.config.providers import load_embedding_config
        from src.infrastructure.intelligence.llm.resilient_llm_service import (
            ResilientEmbeddingService, EmbeddingProviderHandler
        )
        from src.infrastructure.intelligence.llm.embedding import GeminiEmbeddingProvider
        from src.infrastructure.intelligence.llm.rate_limit import SlidingWindowStrategy, NoOpStrategy

        emb_handlers: List[EmbeddingProviderHandler] = []
        
        # Embedding provider
        for emb_cfg in load_embedding_config():
            name = emb_cfg['name']
            model = emb_cfg['model']
            api_key = os.environ.get(emb_cfg['api_key_env'], '')

            if name == 'gemini':
                provider = GeminiEmbeddingProvider(api_key=api_key, model=model)

            s_emb_cfg = emb_cfg.get('strategy', {})
            if s_emb_cfg.get('type') == 'sliding_window':
                strategy = SlidingWindowStrategy(
                    rpm=s_emb_cfg['rpm'],
                    tpm=s_emb_cfg['tpm'],
                    rpd=s_emb_cfg['rpd'],
                )
            else:
                strategy = NoOpStrategy()
            
            emb_handlers.append(EmbeddingProviderHandler(
                provider=provider,
                strategy=strategy,
                priority=emb_cfg['priority'],
                name=name,
            ))
        
        if not emb_handlers:
            raise ValueError("providers.toml 中未設定任何有效的 Embedding provider")

        return ResilientEmbeddingService(handlers=emb_handlers)

    provider = build_llm_service()

    # Fetch tags without embeddings
    query = "SELECT id, name FROM tags WHERE embedding IS NULL"
    if args.limit:
        query += f" LIMIT {args.limit}"
    rows = session.execute(text(query)).fetchall()

    logger.info("backfill_start", total=len(rows), dry_run=args.dry_run)

    batch_size = 10
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
