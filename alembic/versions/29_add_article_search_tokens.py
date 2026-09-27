"""add_article_search_tokens

Replaces the hand-built term->article inverted index (intelligence.search_terms +
intelligence.search_term_articles, 26_add_search_terms_and_pg_trgm) with
intelligence.article_search_tokens: one row per (article, language) holding that text's
tokens as a text[], with a GIN index on it. GIN is itself an inverted index, so
exact-match retrieval becomes `tokens @> ARRAY[...]` instead of a GROUP BY/HAVING over a
link table, and — the actual point — the table can be kept current incrementally
(re-tokenize only new/changed (article, language) pairs each scrape cycle) instead of
being DELETEd and re-INSERTed wholesale every run, which re-tokenized every article and
rewrote both tables plus their trigram GIN index each time.

intelligence.search_terms survives under the same name, now as a MATERIALIZED VIEW
derived from article_search_tokens (topic_id, language, term, occurrence_count) — still
autocomplete's Postgres fallback and still backed by the pg_trgm GIN index for its
`term ILIKE '%...%'` contains-query. REFRESH MATERIALIZED VIEW CONCURRENTLY (needs the
UNIQUE index below) only writes the rows that changed, and keeps the view readable while
it runs. Like intelligence.tag_article_counts (28_add_tag_article_counts_mv), it is NOT
mapped as an ORM model — read via text() SQL.

occurrence_count is COUNT(*) rather than COUNT(DISTINCT article_id): each
(article, language) row's `tokens` is already a set, so one (topic, language, term)
group can never see the same article twice.

Both tables start empty: the first RebuildSearchIndexUseCase run after this migration
finds every eligible (article, language) pair missing and indexes it — the same work the
old full rebuild did every run, done once.

Also drops three HNSW indexes that production's pg_stat_user_indexes showed with
idx_scan = 0 over the ~34 days since pg_stat_statements was last reset (2026-08-23),
while still being maintained on every write:
  - vectors.idx_article_chunks_dense_vector (118 MB) and
    vectors.idx_article_chunks_sparse_vector (51 MB): /search's vector query takes
    MIN(distance) per article under GROUP BY, a shape HNSW can't serve, so it computes
    distances over the topic's chunks directly; EXPLAIN ANALYZE showed even a plain
    ORDER BY ... LIMIT picks a seq scan at this table size, and forcing HNSW caps
    results at hnsw.ef_search (40). Meanwhile every chunk INSERT (the most expensive
    statement in pg_stat_statements by total time) paid for maintaining both graphs.
  - intelligence.idx_tags_embedding (37 MB): the tag-similarity query filters by tag
    group before ordering by distance, and ~10k tags are cheaper to scan; every tag
    embedding INSERT/UPDATE paid for the graph anyway.
Re-add them (together with a query shape that can actually use them, plus
hnsw.ef_search / hnsw.iterative_scan tuning) once row counts grow by an order of
magnitude. downgrade() recreates all three.

Revision ID: 29_add_article_search_tokens
Revises: 28_add_tag_article_counts_mv
Create Date: 2026-09-26
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import ARRAY, UUID

revision = "29_add_article_search_tokens"
down_revision = "28_add_tag_article_counts_mv"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "article_search_tokens",
        sa.Column(
            "article_id", UUID(as_uuid=True),
            sa.ForeignKey("core.articles.id", ondelete="CASCADE"), primary_key=True,
        ),
        sa.Column("language", sa.String(10), primary_key=True),
        sa.Column("topic_id", UUID(as_uuid=True), nullable=False),
        sa.Column("tokens", ARRAY(sa.Text()), nullable=False),
        sa.Column("source_updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("indexed_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        schema="intelligence",
    )
    op.execute(
        "CREATE INDEX idx_article_search_tokens_tokens "
        "ON intelligence.article_search_tokens USING gin (tokens)"
    )
    op.create_index(
        "idx_article_search_tokens_topic_language", "article_search_tokens",
        ["topic_id", "language"], schema="intelligence",
    )

    op.drop_table("search_term_articles", schema="intelligence")
    op.drop_table("search_terms", schema="intelligence")

    op.execute("""
        CREATE MATERIALIZED VIEW intelligence.search_terms AS
        SELECT ast.topic_id, ast.language, t.term, COUNT(*)::int AS occurrence_count
        FROM intelligence.article_search_tokens ast
        CROSS JOIN LATERAL unnest(ast.tokens) AS t(term)
        GROUP BY ast.topic_id, ast.language, t.term
    """)
    # Required by REFRESH MATERIALIZED VIEW CONCURRENTLY; its (topic_id, language) prefix
    # also serves the fallback query's equality filters.
    op.execute(
        "CREATE UNIQUE INDEX idx_search_terms_topic_language_term "
        "ON intelligence.search_terms (topic_id, language, term)"
    )
    op.execute(
        "CREATE INDEX idx_search_terms_term_trgm "
        "ON intelligence.search_terms USING gin (term gin_trgm_ops)"
    )

    op.execute("DROP INDEX IF EXISTS vectors.idx_article_chunks_dense_vector")
    op.execute("DROP INDEX IF EXISTS vectors.idx_article_chunks_sparse_vector")
    op.execute("DROP INDEX IF EXISTS intelligence.idx_tags_embedding")


def downgrade() -> None:
    # Same definitions as 17_add_vector_failed_task_and_auto_tag /
    # 21_add_vectors_schema_and_article_chunks created them.
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_tags_embedding "
        "ON intelligence.tags USING hnsw (embedding vector_cosine_ops)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_article_chunks_sparse_vector "
        "ON vectors.article_chunks USING hnsw (sparse_vector sparsevec_cosine_ops)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_article_chunks_dense_vector "
        "ON vectors.article_chunks USING hnsw (dense_vector vector_cosine_ops)"
    )

    op.execute("DROP MATERIALIZED VIEW IF EXISTS intelligence.search_terms")

    # Recreated empty, exactly as 26_add_search_terms_and_pg_trgm left them — the
    # previous code's full rebuild repopulates both on its next run.
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

    op.drop_index("idx_article_search_tokens_topic_language", table_name="article_search_tokens", schema="intelligence")
    op.execute("DROP INDEX IF EXISTS intelligence.idx_article_search_tokens_tokens")
    op.drop_table("article_search_tokens", schema="intelligence")
