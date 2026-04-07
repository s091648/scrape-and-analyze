"""add_summary_to_analyses

Revision ID: 10_add_summary_to_analyses
Revises: 09_add_arxiv_keywords
Create Date: 2026-04-07
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = '10_add_summary_to_analyses'
down_revision: Union[str, Sequence[str], None] = '09_add_arxiv_keywords'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('analyses', sa.Column('summary', sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column('analyses', 'summary')
