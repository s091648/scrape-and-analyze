# alembic/versions/22_add_correlation_id_and_rag_providers.py
"""add_correlation_id_to_failed_tasks

Revision ID: 22_add_correlation_id_and_rag_providers
Revises: 21_add_vectors_schema_and_article_chunks
Create Date: 2026-06-14
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = '22_add_correlation_id_and_rag_providers'
down_revision = '21_add_vectors_schema_and_article_chunks'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        'failed_tasks',
        sa.Column('correlation_id', UUID(as_uuid=True), nullable=True),
    )
    op.create_index(
        'idx_failed_tasks_correlation_id',
        'failed_tasks',
        ['correlation_id'],
    )
    op.drop_table('arxiv_metadata')


def downgrade():
    from sqlalchemy.dialects.postgresql import JSONB, ARRAY
    from sqlalchemy import TEXT
    op.create_table(
        'arxiv_metadata',
        sa.Column('id', UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('article_id', UUID(as_uuid=True), sa.ForeignKey('articles.id', ondelete='CASCADE'), nullable=False),
        sa.Column('arxiv_id', sa.String(50), nullable=True),
        sa.Column('authors', ARRAY(TEXT), nullable=False, server_default='{}'),
        sa.Column('pdf_available', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('sections', JSONB, nullable=False, server_default='{}'),
    )
    op.create_index('idx_arxiv_metadata_article_id', 'arxiv_metadata', ['article_id'])
    op.create_unique_constraint('uq_arxiv_metadata_article_id', 'arxiv_metadata', ['article_id'])
    op.drop_index('idx_failed_tasks_correlation_id', table_name='failed_tasks')
    op.drop_column('failed_tasks', 'correlation_id')
