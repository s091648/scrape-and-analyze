# alembic/versions/25_add_article_merge_tombstone.py
"""add_article_merge_tombstone

Adds merged_into_id / merged_at / last_reconciled_at to `articles` so that
upstream (OpenAlex) dedup decisions discovered after we've already scraped
both sides of a duplicate can be reconciled without ever deleting a row.
Several FKs into `articles` (analyses, article_tags, failed_tasks) have no
ON DELETE action, so a hard delete would either fail outright or require
manually re-pointing every one of them — tombstoning sidesteps that entirely.

Consumed by src/entrypoints/cli/dedup_reconcile.py.

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
    )
    op.add_column("articles", sa.Column("merged_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("articles", sa.Column("last_reconciled_at", sa.DateTime(timezone=True), nullable=True))
    op.create_index("idx_articles_merged_into_id", "articles", ["merged_into_id"])


def downgrade() -> None:
    op.drop_index("idx_articles_merged_into_id", table_name="articles")
    op.drop_column("articles", "last_reconciled_at")
    op.drop_column("articles", "merged_at")
    op.drop_column("articles", "merged_into_id")
