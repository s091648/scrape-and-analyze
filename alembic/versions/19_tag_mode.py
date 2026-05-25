"""replace_auto_tag_groups_with_tag_mode

Replace the boolean auto_tag_groups column on topics with a tag_mode
VARCHAR(20) column supporting 'unsupervised', 'semi_supervised', 'supervised'.

Revision ID: 19_tag_mode
Revises: 18_add_data_migrations_table
Create Date: 2026-05-25
"""
from alembic import op
import sqlalchemy as sa

revision: str = "19_tag_mode"
down_revision = "18_add_data_migrations_table"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "topics",
        sa.Column("tag_mode", sa.String(20), nullable=False, server_default="unsupervised"),
    )
    op.execute(
        "UPDATE topics SET tag_mode = CASE WHEN auto_tag_groups = TRUE "
        "THEN 'unsupervised' ELSE 'supervised' END"
    )
    op.alter_column("topics", "tag_mode", server_default=None)
    op.drop_column("topics", "auto_tag_groups")


def downgrade() -> None:
    op.add_column(
        "topics",
        sa.Column(
            "auto_tag_groups",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
    )
    op.execute(
        "UPDATE topics SET auto_tag_groups = CASE WHEN tag_mode = 'supervised' "
        "THEN FALSE ELSE TRUE END"
    )
    op.alter_column("topics", "auto_tag_groups", server_default=None)
    op.drop_column("topics", "tag_mode")
