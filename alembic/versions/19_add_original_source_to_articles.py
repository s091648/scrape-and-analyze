"""add_original_source_to_articles

Revision ID: 19_add_original_source_to_articles
Revises: 18_add_data_migrations_table
Create Date: 2026-06-05
"""
from alembic import op
import sqlalchemy as sa

revision = "19_add_original_source_to_articles"
down_revision = "18_add_data_migrations_table"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "articles",
        sa.Column("original_source", sa.String(200), nullable=True),
    )
    # Backfill: non-aggregator articles already have their source name as the original source
    op.execute("""
        UPDATE articles
        SET original_source = source
        WHERE source NOT IN ('openalex', 'semantic_scholar')
          AND original_source IS NULL
    """)
    op.create_index("idx_articles_original_source", "articles", ["original_source"])


def downgrade() -> None:
    op.drop_index("idx_articles_original_source", table_name="articles")
    op.drop_column("articles", "original_source")
