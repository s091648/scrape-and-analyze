# alembic/versions/22_add_correlation_id_and_rag_providers.py
"""add_correlation_id_to_failed_tasks_and_rag_embedding_providers

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
    # --- failed_tasks: add correlation_id ---
    op.add_column(
        'failed_tasks',
        sa.Column('correlation_id', UUID(as_uuid=True), nullable=True),
    )
    op.create_index(
        'idx_failed_tasks_correlation_id',
        'failed_tasks',
        ['correlation_id'],
    )

    # --- rag_embedding_providers table ---
    op.create_table(
        'rag_embedding_providers',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('role', sa.String(10), nullable=False),
        sa.Column('provider_type', sa.String(20), nullable=False),
        sa.Column('model', sa.String(200), nullable=True),
        sa.Column('endpoint_url', sa.Text(), nullable=True),
        sa.Column('api_key_env', sa.String(100), nullable=True),
        sa.Column('dimension', sa.Integer(), nullable=False),
        sa.Column('rpm', sa.Integer(), nullable=True),
        sa.Column('tpm', sa.Integer(), nullable=True),
        sa.Column('rpd', sa.Integer(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("role IN ('dense', 'sparse')", name='ck_rag_role'),
        sa.CheckConstraint("provider_type IN ('endpoint', 'local')", name='ck_rag_provider_type'),
    )
    # Partial unique index: at most one active provider per role
    op.create_index(
        'uq_rag_embedding_providers_active_role',
        'rag_embedding_providers',
        ['role'],
        unique=True,
        postgresql_where=sa.text('is_active = true'),
    )


def downgrade():
    op.drop_index('uq_rag_embedding_providers_active_role', table_name='rag_embedding_providers')
    op.drop_table('rag_embedding_providers')
    op.drop_index('idx_failed_tasks_correlation_id', table_name='failed_tasks')
    op.drop_column('failed_tasks', 'correlation_id')
