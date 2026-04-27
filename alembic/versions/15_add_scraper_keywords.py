"""add_scraper_keywords

Revision ID: 15_add_scraper_keywords
Revises: 13_add_translations
Create Date: 2026-04-25
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision: str = "15_add_scraper_keywords"
down_revision: Union[str, Sequence[str], None] = "13_add_translations"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── New table: scraper_keywords ───────────────────────────────────────
    # Stores keyword filter overrides keyed by topic, shared across all
    # scraper source types (RSS, arxiv, …) for the same topic.
    # Semantics (in scrapers):
    #   0 rows for a topic  → use source-specific defaults
    #   1+ rows for a topic → use only these keywords (full override)
    op.create_table(
        "scraper_keywords",
        sa.Column("id", UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("topic_id", UUID(as_uuid=True),
                  sa.ForeignKey("topics.id", ondelete="CASCADE"),
                  nullable=False),
        sa.Column("keyword", sa.String(500), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.text("NOW()")),
        sa.UniqueConstraint("topic_id", "keyword",
                            name="uq_scraper_keyword_topic_keyword"),
    )
    op.create_index(
        "idx_scraper_keywords_topic_id", "scraper_keywords", ["topic_id"]
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
        COMMENT ON COLUMN scraper_keywords.topic_id IS
        'FK → topics.id. Keywords are topic-scoped and shared by all scraper source types
         (RSS, arxiv, …) for this topic.'
    """)
    op.execute("""
        COMMENT ON COLUMN scraper_keywords.keyword IS
        'Regex pattern used to filter articles for this topic.
         If 1+ rows exist for a topic, they fully replace source-specific defaults.
         If 0 rows exist, the scraper falls back to its own default keyword list.'
    """)


def downgrade() -> None:
    # Indexes are dropped automatically by PostgreSQL when the table is dropped.
    op.drop_table("scraper_keywords")

    # COMMENT ON COLUMN cannot be easily reversed; drop by setting to NULL
    op.execute("COMMENT ON COLUMN articles.correlation_id IS NULL")
    op.execute("COMMENT ON COLUMN articles.url_hash IS NULL")
    op.execute("COMMENT ON COLUMN articles.topic_id IS NULL")
    op.execute("COMMENT ON COLUMN analyses.correlation_id IS NULL")
    op.execute("COMMENT ON COLUMN analyses.article_id IS NULL")
    op.execute("COMMENT ON COLUMN scraper_settings.topic_id IS NULL")
