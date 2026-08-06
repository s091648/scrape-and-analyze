# alembic/versions/25_add_article_merge_tombstone.py
"""add_article_merge_tombstone

Adds merged_into_id / merged_at / last_reconciled_at to `articles` so that
upstream (OpenAlex) dedup decisions discovered after we've already scraped
both sides of a duplicate can be reconciled without ever deleting a row.
Several FKs into `articles` (analyses, article_tags, failed_tasks) have no
ON DELETE action, so a hard delete would either fail outright or require
manually re-pointing every one of them — tombstoning sidesteps that entirely.

Consumed by src/entrypoints/cli/dedup_reconcile.py.

Also repoints `sync_article_has_vectors()` (created in migration 21) from
`public.articles` to `core.articles`. Migration 24 moved `articles` into the
`core` schema, but Postgres does not track a schema-qualified table
reference inside a function body as a dependency the way it does for views,
so that move silently left this trigger function pointing at a table that
no longer exists. Every INSERT/DELETE on `vectors.articles` (i.e. every RAG
ingest) fires this trigger, so it started failing with `UndefinedTable:
relation "public.articles" does not exist` as soon as 24 landed. The
unqualified-reference fix migration 24 already applies via
`ALTER DATABASE ... SET search_path` doesn't help here since this function
qualifies the table explicitly, bypassing search_path — the body itself has
to be corrected.

Revision ID: 25_add_article_merge_tombstone
Revises: 24_reorganize_public_schema_into_ddd_schemas
Create Date: 2026-07-27
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "25_add_article_merge_tombstone"
down_revision = "24_reorganize_public_schema_into_ddd_schemas"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "articles",
        sa.Column("merged_into_id", UUID(as_uuid=True), sa.ForeignKey("core.articles.id"), nullable=True),
        schema="core",
    )
    op.add_column("articles", sa.Column("merged_at", sa.DateTime(timezone=True), nullable=True), schema="core")
    op.add_column(
        "articles", sa.Column("last_reconciled_at", sa.DateTime(timezone=True), nullable=True), schema="core"
    )
    op.create_index("idx_articles_merged_into_id", "articles", ["merged_into_id"], schema="core")

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


def downgrade() -> None:
    op.execute("""
        CREATE OR REPLACE FUNCTION public.sync_article_has_vectors()
        RETURNS TRIGGER AS $$
        BEGIN
          IF TG_OP = 'INSERT' THEN
            IF NEW.public_article_id IS NOT NULL THEN
              UPDATE public.articles SET has_vectors = TRUE WHERE id = NEW.public_article_id;
            END IF;
          ELSIF TG_OP = 'DELETE' THEN
            IF OLD.public_article_id IS NOT NULL THEN
              UPDATE public.articles
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

    op.drop_index("idx_articles_merged_into_id", table_name="articles", schema="core")
    op.drop_column("articles", "last_reconciled_at", schema="core")
    op.drop_column("articles", "merged_at", schema="core")
    op.drop_column("articles", "merged_into_id", schema="core")
