"""extend_failed_tasks

Revision ID: 17_extend_failed_tasks
Revises: 16_add_pgvector_and_tag_normalization
Create Date: 2026-05-18
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB

revision: str = "17_extend_failed_tasks"
down_revision: Union[str, Sequence[str], None] = "16_add_pgvector"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("failed_tasks", sa.Column(
        "analysis_id", UUID(as_uuid=True), nullable=True,
    ))
    op.create_foreign_key(
        "fk_failed_tasks_analysis_id", "failed_tasks", "analyses",
        ["analysis_id"], ["id"], ondelete="SET NULL",
    )
    op.add_column("failed_tasks", sa.Column("context", JSONB(), nullable=True))
    op.add_column("failed_tasks", sa.Column("traceback", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("failed_tasks", "traceback")
    op.drop_column("failed_tasks", "context")
    op.drop_constraint("fk_failed_tasks_analysis_id", "failed_tasks", type_="foreignkey")
    op.drop_column("failed_tasks", "analysis_id")
