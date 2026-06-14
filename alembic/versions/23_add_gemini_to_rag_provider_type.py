# alembic/versions/23_add_gemini_to_rag_provider_type.py
"""add_gemini_to_rag_provider_type_check_constraint

Revision ID: 23_add_gemini_to_rag_provider_type
Revises: 22_add_correlation_id_and_rag_providers
Create Date: 2026-06-14
"""
from alembic import op
import sqlalchemy as sa

revision = '23_add_gemini_to_rag_provider_type'
down_revision = '22_add_correlation_id_and_rag_providers'
branch_labels = None
depends_on = None


def upgrade():
    op.drop_constraint('ck_rag_provider_type', 'rag_embedding_providers', type_='check')
    op.create_check_constraint(
        'ck_rag_provider_type',
        'rag_embedding_providers',
        "provider_type IN ('endpoint', 'local', 'gemini')",
    )


def downgrade():
    op.drop_constraint('ck_rag_provider_type', 'rag_embedding_providers', type_='check')
    op.create_check_constraint(
        'ck_rag_provider_type',
        'rag_embedding_providers',
        "provider_type IN ('endpoint', 'local')",
    )
