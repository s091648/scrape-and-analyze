#!/usr/bin/env python3
"""
Manually rebuild the autocomplete/search term index (023-article-search) without
waiting for the next scheduled scrape run to finish (`SearchIndexRebuildHandler`
normally does this once per completed pipeline run, see src/bootstrap.py).

Useful after a translation backfill or any other change to article content that
should be reflected in the intelligence.search_terms table / Redis suggestion
index right away.

Usage:
    DATABASE_URL=... python scripts/rebuild_search_index.py [--min-doc-freq N]
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.infrastructure.persistence.database import get_session, init_db
from src.shared.logging import get_logger

logger = get_logger(__name__)


def parse_args():
    parser = argparse.ArgumentParser(description="Rebuild the autocomplete/search term index.")
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
    from src.infrastructure.persistence.intelligence import SqlAlchemySearchTermRepository
    from src.modules.search.application.use_cases import RebuildSearchIndexUseCase

    init_db()
    session = get_session()

    try:
        search_term_repo = SqlAlchemySearchTermRepository(session)
        search_index_gateway = RedisSearchIndexGateway(redis_url=SEARCH_INDEX_REDIS_URL)
        use_case = RebuildSearchIndexUseCase(
            session=session,
            search_term_repo=search_term_repo,
            search_index_gateway=search_index_gateway,
            min_doc_freq=args.min_doc_freq if args.min_doc_freq is not None else SEARCH_MIN_DOC_FREQ,
        )
        stats = use_case.execute()
    finally:
        session.close()

    print(
        f"Search index rebuilt: {stats['article_count']} article(s), "
        f"{stats['topic_count']} topic(s), {stats['term_count']} term(s)"
    )


if __name__ == "__main__":
    main()
