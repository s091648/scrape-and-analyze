# alembic/versions/26_add_search_terms_and_pg_trgm.py
"""add_search_terms_and_pg_trgm

Adds intelligence.search_terms — the compact, pre-expansion autocomplete term list
(023-article-search) — and intelligence.search_term_articles, the term->article inverted
index backing exact-match retrieval (023-article-search follow-up). Neither is a copy of
the fully expanded Redis suffix-prefix structure (see specs/023-article-search/
data-model.md) — search_terms is the smaller normalized input that structure is derived
from, and it backs a cache-aside fallback query when Redis is unavailable/missing a key.
Unlike vectors.article_chunks (raw-SQL-only, no ORM model), both tables here DO have
SQLAlchemy ORM models (models/search_term.py, models/search_term_article.py) — written
via ORM by src/'s RebuildSearchIndexUseCase and queried via ORM by backend/'s
search_service.py, matching this codebase's normal ORM-first convention rather than
raw SQL (023-article-search follow-up: the original raw-SQL-only design was reconsidered
specifically because it made search_service.py's style inconsistent with every other
backend service).

UNIQUE (topic_id, term, language) is both the natural key and the ON CONFLICT target the
rebuild job's upsert/replace write uses — `language` splits mixed-language term counts
apart the same way ArticleTranslation/AnalysesTranslation/etc. split translated content
apart, added here (rather than at initial creation) once query-time evidence showed a
non-English exact-match query needs a language-scoped, not merged, term lookup.

search_term_articles.search_term_id FKs to search_terms.id (surrogate key, not the
composite natural key — simpler joins, and Postgres FKs can't target a plain unique
index on non-PK columns without extra ceremony) with ON DELETE CASCADE, so a
search_terms rebuild-triggered delete never leaves orphaned association rows.

pg_trgm is required for the Postgres-fallback's `term ILIKE '%...%'` contains-query to
use an index (a leading-wildcard LIKE can't use a plain B-tree index) — standard
Postgres contrib extension, same category as the already-installed `vector` extension.

Revision ID: 26_add_search_terms_and_pg_trgm
Revises: 25_add_article_merge_tombstone
Create Date: 2026-08-16
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "26_add_search_terms_and_pg_trgm"
down_revision = "25_add_article_merge_tombstone"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")

    op.create_table(
        "search_terms",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("topic_id", UUID(as_uuid=True), nullable=False),
        sa.Column("term", sa.Text(), nullable=False),
        sa.Column("language", sa.String(10), nullable=False),
        sa.Column("occurrence_count", sa.Integer(), nullable=False),
        sa.UniqueConstraint("topic_id", "term", "language", name="uq_search_terms_topic_term_language"),
        schema="intelligence",
    )
    op.execute(
        "CREATE INDEX idx_search_terms_term_trgm "
        "ON intelligence.search_terms USING gin (term gin_trgm_ops)"
    )
    op.create_index(
        "idx_search_terms_topic_language", "search_terms", ["topic_id", "language"], schema="intelligence",
    )

    op.create_table(
        "search_term_articles",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column(
            "search_term_id", UUID(as_uuid=True),
            sa.ForeignKey("intelligence.search_terms.id", ondelete="CASCADE"), nullable=False,
        ),
        sa.Column(
            "article_id", UUID(as_uuid=True),
            sa.ForeignKey("core.articles.id", ondelete="CASCADE"), nullable=False,
        ),
        sa.UniqueConstraint("search_term_id", "article_id", name="uq_search_term_articles_term_article"),
        schema="intelligence",
    )
    op.create_index(
        "idx_search_term_articles_article_id", "search_term_articles", ["article_id"], schema="intelligence",
    )


def downgrade() -> None:
    op.drop_index("idx_search_term_articles_article_id", table_name="search_term_articles", schema="intelligence")
    op.drop_table("search_term_articles", schema="intelligence")
    op.drop_index("idx_search_terms_topic_language", table_name="search_terms", schema="intelligence")
    op.execute("DROP INDEX IF EXISTS intelligence.idx_search_terms_term_trgm")
    op.drop_table("search_terms", schema="intelligence")
    op.execute("DROP EXTENSION IF EXISTS pg_trgm")
