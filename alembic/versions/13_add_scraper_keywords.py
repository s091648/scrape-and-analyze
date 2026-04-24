"""add_scraper_keywords

Revision ID: 13_add_scraper_keywords
Revises: 12_add_topic_system
Create Date: 2026-04-25
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision: str = "13_add_scraper_keywords"
down_revision: Union[str, Sequence[str], None] = "12_add_topic_system"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── New table: scraper_keywords ───────────────────────────────────────
    # Stores per-ScraperSetting keyword overrides for RSS filtering.
    # Semantics (in RssScraper):
    #   0 rows  → use _DEFAULT_KEYWORDS
    #   1+ rows → use only these keywords (full override)
    op.create_table(
        "scraper_keywords",
        sa.Column("id", UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("scraper_setting_id", UUID(as_uuid=True),
                  sa.ForeignKey("scraper_settings.id", ondelete="CASCADE"),
                  nullable=False),
        sa.Column("keyword", sa.String(500), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.text("NOW()")),
        sa.UniqueConstraint("scraper_setting_id", "keyword",
                            name="uq_scraper_keyword_setting_keyword"),
    )
    op.create_index(
        "idx_scraper_keywords_setting_id", "scraper_keywords", ["scraper_setting_id"]
    )

    # ── Column comments: ID/key column glossary ───────────────────────────
    # articles
    op.execute("""
        COMMENT ON COLUMN articles.correlation_id IS
        'UUID shared by all articles produced in a single CollectionPipeline.run() call.
         Use to group or trace everything from one pipeline execution.
         Also appears as correlation_id in structured logs for the same run.'
    """)
    op.execute("""
        COMMENT ON COLUMN articles.url_hash IS
        'SHA-256 hex digest of the article URL.
         Indexed for O(1) deduplication checks — avoids full-text comparison on the url column.'
    """)
    op.execute("""
        COMMENT ON COLUMN articles.topic_id IS
        'FK → topics.id. Research topic this article was collected under (e.g. digital-twins).'
    """)

    # analyses
    op.execute("""
        COMMENT ON COLUMN analyses.correlation_id IS
        'UUID shared by all analyses produced in the same analysis pipeline run.
         Mirrors the pattern used in articles.correlation_id.'
    """)
    op.execute("""
        COMMENT ON COLUMN analyses.article_id IS
        'FK → articles.id. One-to-one: each article has at most one analysis row.'
    """)

    # scraper_settings
    op.execute("""
        COMMENT ON COLUMN scraper_settings.topic_id IS
        'FK → topics.id. Determines which research topic this scraper collects for.'
    """)

    # scraper_keywords
    op.execute("""
        COMMENT ON COLUMN scraper_keywords.scraper_setting_id IS
        'FK → scraper_settings.id. The source this keyword override belongs to.'
    """)
    op.execute("""
        COMMENT ON COLUMN scraper_keywords.keyword IS
        'Regex pattern used to filter RSS entries for this source.
         If 1+ rows exist, they fully replace _DEFAULT_KEYWORDS in RssScraper.
         If 0 rows exist, RssScraper falls back to _DEFAULT_KEYWORDS.'
    """)


def downgrade() -> None:
    op.drop_index("idx_scraper_keywords_setting_id", table_name="scraper_keywords")
    op.drop_table("scraper_keywords")

    # COMMENT ON COLUMN cannot be easily reversed; drop by setting to NULL
    op.execute("COMMENT ON COLUMN articles.correlation_id IS NULL")
    op.execute("COMMENT ON COLUMN articles.url_hash IS NULL")
    op.execute("COMMENT ON COLUMN articles.topic_id IS NULL")
    op.execute("COMMENT ON COLUMN analyses.correlation_id IS NULL")
    op.execute("COMMENT ON COLUMN analyses.article_id IS NULL")
    op.execute("COMMENT ON COLUMN scraper_settings.topic_id IS NULL")
