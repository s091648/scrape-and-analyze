"""
002_backfill_arxiv_id

Normalizes articles.metadata->>'arxiv_id' for rows persisted before
ArxivClient._parse_entry() was fixed to strip arXiv's Atom <id> URL form
(e.g. "http://arxiv.org/abs/2606.29232v1") down to the bare id
("2606.29232"). Until that fix, every article scraped from the "arxiv"
source stored the raw URL as its arxiv_id — external lookups keyed on it
(Semantic Scholar's paper/ARXIV:<id>) 404'd for all of them, which is why
refresh_metrics.py logged semantic_scholar_fetch_by_arxiv_id_failed
repeatedly instead of an occasional per-article failure.

Only touches rows whose arxiv_id still has the URL form — articles sourced
via semantic_scholar/openalex already stored a bare id (those clients
normalize it themselves), so they're left untouched.

down() is intentionally omitted: the transformation discards the version
suffix (e.g. "v1"), so there is no faithful original value to restore, and
the pre-migration value was buggy data rather than a state worth keeping.
"""
from sqlalchemy import text

from src.infrastructure.collection.clients.arxiv_client import normalize_arxiv_id

name = "002_backfill_arxiv_id"
description = "Normalize articles.metadata->>'arxiv_id' from arXiv Atom URL form to bare id"
requires_api = False
down_revision = "001_backfill_tag_group_definitions"
alembic_revision = None  # articles.metadata has existed since baseline — no schema precondition

_SQL_URL_FORM_ARXIV_IDS = """
SELECT id, metadata->>'arxiv_id' AS arxiv_id
FROM articles
WHERE metadata->>'arxiv_id' LIKE 'http%'
"""


def up(session) -> None:
    rows = session.execute(text(_SQL_URL_FORM_ARXIV_IDS)).fetchall()
    if not rows:
        print("    no URL-form arxiv_id values found")
        return

    fixed = 0
    for row in rows:
        article_id, raw_id = row.id, row.arxiv_id
        normalized = normalize_arxiv_id(raw_id)
        if normalized == raw_id:
            continue
        session.execute(
            text("""
                UPDATE articles
                SET metadata = jsonb_set(metadata, '{arxiv_id}', to_jsonb(CAST(:normalized AS text)))
                WHERE id = :id
            """),
            {"normalized": normalized, "id": article_id},
        )
        fixed += 1
        print(f"    {raw_id} -> {normalized}")

    session.commit()
    print(f"    normalized {fixed} of {len(rows)} arxiv_id values")
