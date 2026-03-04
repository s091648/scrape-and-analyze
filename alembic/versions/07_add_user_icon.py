"""add_user_icon

Revision ID: 07_add_user_icon
Revises: 06_extend_auth_users
Create Date: 2026-03-04
"""
from alembic import op
import sqlalchemy as sa

revision = '07_add_user_icon'
down_revision = '06_extend_auth_users'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('users', sa.Column('icon', sa.Text(), nullable=True), schema='auth')


def downgrade() -> None:
    op.drop_column('users', 'icon', schema='auth')
