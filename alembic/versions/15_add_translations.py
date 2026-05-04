"""add_translations

Revision ID: 15_add_translations
Revises: 14_migrate_arxiv_keywords
Create Date: 2026-04-24
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision: str = "15_add_translations"
down_revision: Union[str, Sequence[str], None] = "14_migrate_arxiv_keywords"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. Add language column to analyses (canonical language, default 'en')
    op.add_column('analyses',
        sa.Column('language', sa.String(10), nullable=False, server_default='en'))
    op.create_index('idx_analyses_language', 'analyses', ['language'])

    # 2. Create translations table for multi-language support
    op.create_table(
        "translations",
        sa.Column("id", UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("analysis_id", UUID(as_uuid=True), nullable=False),
        sa.Column("language", sa.String(10), nullable=False),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("pain_points", sa.Text(), nullable=True),
        sa.Column("insights", sa.Text(), nullable=True),
        sa.Column("innovations", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.text("NOW()")),
        sa.Column("updated_at", sa.DateTime(timezone=True),
                  server_default=sa.text("NOW()")),
    )
    op.create_index("idx_translations_analysis_id", "translations", ["analysis_id"])
    op.create_index("idx_translations_language", "translations", ["language"])
    # Unique constraint: one translation per analysis per language
    op.create_unique_constraint(
        'uq_translations_analysis_language',
        'translations',
        ['analysis_id', 'language']
    )
    op.create_foreign_key(
        'fk_translations_analysis_id',
        'translations',
        'analyses',
        ['analysis_id'],
        ['id']
    )


def downgrade() -> None:
    op.drop_constraint('fk_translations_analysis_id', 'translations', type_='foreignkey')
    op.drop_unique_constraint('uq_translations_analysis_language', 'translations')
    op.drop_index('idx_translations_language', table_name='translations')
    op.drop_index('idx_translations_analysis_id', table_name='translations')
    op.drop_table('translations')

    op.drop_index('idx_analyses_language', table_name='analyses')
    op.drop_column('analyses', 'language')
