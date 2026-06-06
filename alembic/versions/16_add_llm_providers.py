"""add_llm_providers

Revision ID: 16_add_llm_providers
Revises: 15_add_translations
Create Date: 2026-05-14
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = '16_add_llm_providers'
down_revision = '15_add_translations'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'llm_providers',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('name', sa.String(50), nullable=False),
        sa.Column('model', sa.String(100), nullable=False, unique=True),
        sa.Column('api_key_env', sa.String(100), nullable=False),
        sa.Column('priority', sa.Integer, nullable=False),
        sa.Column('is_active', sa.Boolean, nullable=False, server_default='true'),
        sa.Column('rpm', sa.Integer, nullable=True),
        sa.Column('tpm', sa.Integer, nullable=True),
        sa.Column('rpd', sa.Integer, nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint('priority', name='uq_llm_providers_priority', deferrable=True, initially='deferred'),
    )

    # Seed from providers.toml (values hardcoded here; providers.toml is deleted after this migration)
    op.execute("""
        INSERT INTO llm_providers (id, name, model, api_key_env, priority, is_active, rpm, tpm, rpd)
        VALUES
            (gen_random_uuid(), 'gemini', 'gemini-3-flash-preview', 'GEMINI_API_KEY', 1, true, 5, 250000, 20),
            (gen_random_uuid(), 'gemini', 'gemini-3.1-flash-lite', 'GEMINI_API_KEY', 2, true, 15, 250000, 500),
            (gen_random_uuid(), 'gemini', 'gemini-2.5-flash', 'GEMINI_API_KEY', 3, true, 5, 250000, 20),
            (gen_random_uuid(), 'gemini', 'gemini-2.5-flash-lite', 'GEMINI_API_KEY', 4, true, 10, 250000, 20),
            (gen_random_uuid(), 'openrouter', 'deepseek/deepseek-chat', 'OPENROUTER_API_KEY', 5, true, 20, 100000, 200)
    """)


def downgrade() -> None:
    op.drop_table('llm_providers')
