#!/usr/bin/env python3
"""
Manually sync the search index (023-article-search) without waiting for the next
scheduled scrape run to finish (`SearchIndexRebuildHandler` normally does this once
per completed pipeline run, see src/bootstrap.py): incrementally updates
intelligence.article_search_tokens, then refreshes intelligence.search_terms and the
Redis suggestion index from it.

Useful after a translation backfill or any other change to article content that
should be searchable right away. Pass --full after changing the tokenizer or its
stopwords, so every article is re-tokenized instead of only new/changed ones.

Usage:
    DATABASE_URL=... python scripts/rebuild_search_index.py [--full] [--min-doc-freq N]
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.infrastructure.persistence.database import get_session, init_db
from src.shared.logging import get_logger

logger = get_logger(__name__)


def parse_args():
    parser = argparse.ArgumentParser(description="Sync the search index.")
    parser.add_argument(
        "--full", action="store_true",
        help="Re-tokenize every eligible article, not just new/changed ones",
    )
    parser.add_argument(
        "--min-doc-freq", type=int, default=None,
        help="Override SEARCH_MIN_DOC_FREQ (minimum distinct articles a term must appear in)",
    )
    return parser.parse_args()


def main():
    args = parse_args()

    if not os.environ.get("DATABASE_URL"):
        print("ERROR: DATABASE_URL environment variable is required", file=sys.stderr)
        sys.exit(1)

    from src.config.settings import SEARCH_INDEX_REDIS_URL, SEARCH_MIN_DOC_FREQ
    from shared.search_index import RedisSearchIndexGateway
    from src.infrastructure.persistence.intelligence import SqlAlchemyArticleSearchTokenRepository
    from src.modules.search.application.use_cases import RebuildSearchIndexUseCase

    init_db()
    session = get_session()

    try:
        search_index_gateway = RedisSearchIndexGateway(redis_url=SEARCH_INDEX_REDIS_URL)
        use_case = RebuildSearchIndexUseCase(
            search_token_repo=SqlAlchemyArticleSearchTokenRepository(session),
            search_index_gateway=search_index_gateway,
            min_doc_freq=args.min_doc_freq if args.min_doc_freq is not None else SEARCH_MIN_DOC_FREQ,
        )
        stats = use_case.execute(full=args.full)
    finally:
        session.close()

    print(
        f"Search index synced: {stats['indexed_count']} source(s) indexed, "
        f"{stats['deleted_count']} removed, {stats['topic_count']} topic(s), "
        f"{stats['term_count']} suggestible term(s)"
    )


if __name__ == "__main__":
    main()
