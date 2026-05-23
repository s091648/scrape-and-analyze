"""add_data_migrations_table

Revision ID: 18_add_data_migrations_table
Revises: 17_add_vector_failed_task_and_auto_tag
Create Date: 2026-05-24
"""
from alembic import op
import sqlalchemy as sa

revision = "18_add_data_migrations_table"
down_revision = "17_add_vector_failed_task_and_auto_tag"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "data_migrations",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("name", sa.String(200), nullable=False, unique=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("executed_at", sa.DateTime(timezone=True),
                  server_default=sa.text("NOW()"), nullable=False),
        sa.Column("rolled_back_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_table("data_migrations")
