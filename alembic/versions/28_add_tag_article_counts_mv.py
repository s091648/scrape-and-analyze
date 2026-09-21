"""add_tag_article_counts_mv

Adds intelligence.tag_article_counts, a materialized view pre-computing each tag's
per-topic article count (fix/db_imprv). Previously
backend/services/tag_service.py's tag_outs_for_group() / tag_outs_for_groups() /
ungrouped_tag_outs() computed this with a live JOIN across intelligence.tags,
intelligence.article_tags and core.articles (plus intelligence.tag_group_definitions
for the batched variant) on every GET /tag-groups request — a public,
require_any_token-gated, high-read-frequency endpoint recomputing a
COUNT(DISTINCT) aggregate that only actually changes once per scrape pipeline run.

One row per (tag_id, topic_id) rather than per tag_id alone: Tag has no topic_id
column of its own (only TagGroupDefinition does), so the same tag can in principle
link to articles across more than one topic, and every original live-query caller
always scoped the count by a specific topic_id (the tag's group's topic, or the
topic_id param for ungrouped tags) — never a cross-topic total. tag_group_id is
carried along rather than re-derived via a join at read time since it's
functionally dependent on tag_id and both grouped/ungrouped read paths filter on
it directly.

(tag_id, topic_id) is the natural key and backs the UNIQUE index
REFRESH MATERIALIZED VIEW CONCURRENTLY requires (see TagCountsRefreshHandler in
src/modules/intelligence/application/event_handlers/, subscribed to the same
TextPipelineCompletedEvent as the search-term index rebuild — both are read
models derived from tag/article state that only changes once a scrape pipeline
run's text stage settles).

Deliberately NOT mapped as a Base ORM model (unlike intelligence.search_terms,
which is a real table written by application code): a materialized view is a
different pg_class relkind, and Base.metadata.create_all()'s checkfirst DDL
(invoked by init_db() on every pipeline run) isn't something to point at a
relation kind it wasn't designed to safely coexist with — same reasoning
vectors.article_chunks (21_add_vectors_schema_and_article_chunks.py) already
documents for staying raw-SQL-only. Read via text() SQL instead.

Also folds in a small, unrelated-in-substance but still-unshipped fix (was a
separate 29_fix_has_vectors_trigger_redundant_write revision, merged back into
this one before either ever reached a shared environment — no reason to carry
two migrations for one branch's still-local work): adds a
`WHERE has_vectors IS FALSE` guard to sync_article_has_vectors()'s INSERT
branch (21_add_vectors_schema_and_article_chunks.py, repointed from
`public.articles` to `core.articles` by 25_add_article_merge_tombstone). A
redundant INSERT into vectors.articles for an article that already has
has_vectors=true still matches the row and writes a new tuple version even
though the value doesn't change — Postgres does not diff old vs new column
value to decide whether to skip a write. `WHERE has_vectors IS FALSE` makes
that case match zero rows, so it performs zero tuple writes instead of one
wasted one. In practice this mostly guards against write paths other than the
SDK's normal one (chatbot_plugin_sdk's article upsert derives its id
deterministically via `uuid5(NAMESPACE_URL, url)` and INSERTs ... ON CONFLICT
(id) DO UPDATE, so a genuine re-ingestion of the same article takes the UPDATE
branch and never re-fires this AFTER INSERT trigger at all) — cheap insurance
against any other path that does a bare re-INSERT, not a fix for an observed
hot-path waste. The DELETE branch is left unguarded: it only fires when a
vectors.articles row is actually deleted, nowhere near as hot as the INSERT
side, and guarding it would need the EXISTS(...) subquery's result compared
against the current value rather than a straight column-vs-literal check.

Revision ID: 28_add_tag_article_counts_mv
Revises: 27_add_article_view_daily
Create Date: 2026-09-20
"""
from alembic import op

revision = "28_add_tag_article_counts_mv"
down_revision = "27_add_article_view_daily"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE MATERIALIZED VIEW intelligence.tag_article_counts AS
        SELECT
            t.id AS tag_id,
            t.tag_group_id,
            a.topic_id,
            COUNT(DISTINCT at.article_id) AS article_count
        FROM intelligence.tags t
        JOIN intelligence.article_tags at ON at.tag_id = t.id
        JOIN core.articles a ON a.id = at.article_id
        GROUP BY t.id, t.tag_group_id, a.topic_id
    """)
    # Required by REFRESH MATERIALIZED VIEW CONCURRENTLY (TagCountsRefreshHandler).
    op.execute(
        "CREATE UNIQUE INDEX idx_tag_article_counts_tag_topic "
        "ON intelligence.tag_article_counts (tag_id, topic_id)"
    )
    # Backs the actual read pattern: tag_outs_for_group(s)/ungrouped_tag_outs all
    # filter by (tag_group_id, topic_id), never by tag_id alone.
    op.execute(
        "CREATE INDEX idx_tag_article_counts_group_topic "
        "ON intelligence.tag_article_counts (tag_group_id, topic_id)"
    )

    op.execute("""
        CREATE OR REPLACE FUNCTION public.sync_article_has_vectors()
        RETURNS TRIGGER AS $$
        BEGIN
          IF TG_OP = 'INSERT' THEN
            IF NEW.public_article_id IS NOT NULL THEN
              UPDATE core.articles
              SET has_vectors = TRUE
              WHERE id = NEW.public_article_id AND has_vectors IS FALSE;
            END IF;
          ELSIF TG_OP = 'DELETE' THEN
            IF OLD.public_article_id IS NOT NULL THEN
              UPDATE core.articles
              SET has_vectors = EXISTS (
                SELECT 1 FROM vectors.articles WHERE public_article_id = OLD.public_article_id
              )
              WHERE id = OLD.public_article_id;
            END IF;
          END IF;
          RETURN NULL;
        END;
        $$ LANGUAGE plpgsql
    """)


def downgrade() -> None:
    op.execute("DROP MATERIALIZED VIEW IF EXISTS intelligence.tag_article_counts")

    op.execute("""
        CREATE OR REPLACE FUNCTION public.sync_article_has_vectors()
        RETURNS TRIGGER AS $$
        BEGIN
          IF TG_OP = 'INSERT' THEN
            IF NEW.public_article_id IS NOT NULL THEN
              UPDATE core.articles SET has_vectors = TRUE WHERE id = NEW.public_article_id;
            END IF;
          ELSIF TG_OP = 'DELETE' THEN
            IF OLD.public_article_id IS NOT NULL THEN
              UPDATE core.articles
              SET has_vectors = EXISTS (
                SELECT 1 FROM vectors.articles WHERE public_article_id = OLD.public_article_id
              )
              WHERE id = OLD.public_article_id;
            END IF;
          END IF;
          RETURN NULL;
        END;
        $$ LANGUAGE plpgsql
    """)
