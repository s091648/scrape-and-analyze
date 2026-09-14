"""add_article_view_daily

Adds collection.article_view_daily — one row per (article, UTC day) holding that day's delta
of article-detail views. Written by backend/services/article_service.py::flush_view_counts()
alongside the existing cumulative article_metrics.view_count bump (an
`ON CONFLICT (article_id, day) DO UPDATE SET views = views + EXCLUDED.views` upsert).

This is the time-windowed history behind the /admin/analytics page (trending articles over the
last N days, per-article sparklines, site-wide daily view totals). article_metrics.view_count
remains the authoritative all-time total. Daily granularity is intentional — record_article_view
already IP-deduplicates a view over 24h, so finer resolution adds little, and it keeps the row
count bounded (per article per day). History starts the day this migration ships; the cumulative
counter cannot be back-projected into a daily distribution.

The natural key is (article_id, day) — that's the upsert's ON CONFLICT target. A surrogate uuid
`id` PK is kept only to match this codebase's UUID-PK convention. idx_article_view_daily_day
backs the "sum across all articles in the last N days" scans.

Revision ID: 27_add_article_view_daily
Revises: 26_add_search_terms_and_pg_trgm
Create Date: 2026-09-10
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID


revision = "27_add_article_view_daily"
down_revision = "26_add_search_terms_and_pg_trgm"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "article_view_daily",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column(
            "article_id",
            UUID(as_uuid=True),
            sa.ForeignKey("core.articles.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("day", sa.Date(), nullable=False),
        sa.Column("views", sa.Integer(), nullable=False, server_default="0"),
        sa.UniqueConstraint("article_id", "day", name="uq_article_view_daily_article_day"),
        schema="collection",
    )
    op.create_index(
        "idx_article_view_daily_day", "article_view_daily", ["day"], schema="collection"
    )


def downgrade() -> None:
    op.drop_index(
        "idx_article_view_daily_day", table_name="article_view_daily", schema="collection"
    )
    op.drop_table("article_view_daily", schema="collection")
