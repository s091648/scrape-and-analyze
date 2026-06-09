"""add_article_translation

Revision ID: 20_add_article_translation
Revises: 19_add_original_source_to_articles
Create Date: 2026-06-09
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "20_add_article_translation"
down_revision = "19_add_original_source_to_articles"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "articles_translation",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("article_id", UUID(as_uuid=True), sa.ForeignKey("articles.id", ondelete="CASCADE"), nullable=False),
        sa.Column("language", sa.String(10), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("content", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("idx_articles_translation_article_id", "articles_translation", ["article_id"])
    op.create_index("idx_articles_translation_language", "articles_translation", ["language"])
    op.create_unique_constraint(
        "uq_articles_translation_article_language",
        "articles_translation",
        ["article_id", "language"],
    )


def downgrade() -> None:
    op.drop_constraint("uq_articles_translation_article_language", "articles_translation")
    op.drop_index("idx_articles_translation_language", table_name="articles_translation")
    op.drop_index("idx_articles_translation_article_id", table_name="articles_translation")
    op.drop_table("articles_translation")
