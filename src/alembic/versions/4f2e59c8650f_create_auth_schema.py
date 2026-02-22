"""create_auth_schema

Revision ID: 4f2e59c8650f
Revises: baseline
Create Date: 2026-02-21 00:44:28.336892

"""
from alembic import op
import sqlalchemy as sa

revision = '4f2e59c8650f'
down_revision = 'baseline'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE SCHEMA IF NOT EXISTS auth")
    op.execute("""
        CREATE TABLE IF NOT EXISTS auth.users (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            username VARCHAR(100) UNIQUE NOT NULL,
            hashed_password TEXT NOT NULL,
            role VARCHAR(20) NOT NULL DEFAULT 'admin',
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """)
    # Least-privilege isolation: scraper's app_user cannot read auth schema
    op.execute("REVOKE ALL ON SCHEMA auth FROM PUBLIC")


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS auth.users")
    op.execute("DROP SCHEMA IF EXISTS auth")
