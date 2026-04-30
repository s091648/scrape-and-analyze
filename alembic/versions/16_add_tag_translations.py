"""add_tag_translations

Revision ID: 16_add_tag_translations
Revises: 15_add_translations
Create Date: 2026-04-27
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision: str = "16_add_tag_translations"
down_revision: Union[str, Sequence[str], None] = "15_add_translations"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. tag_translations table
    op.create_table(
        "tag_translations",
        sa.Column("id", UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("tag_id", UUID(as_uuid=True), nullable=False),
        sa.Column("language", sa.String(10), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.text("NOW()")),
    )
    op.create_index("idx_tag_translations_tag_id", "tag_translations", ["tag_id"])
    op.create_index("idx_tag_translations_language", "tag_translations", ["language"])
    op.create_unique_constraint(
        "uq_tag_translations_tag_language", "tag_translations", ["tag_id", "language"]
    )
    op.create_foreign_key(
        "fk_tag_translations_tag_id", "tag_translations", "tags", ["tag_id"], ["id"]
    )

    # 2. tag_group_translations table
    op.create_table(
        "tag_group_translations",
        sa.Column("id", UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("tag_group_definition_id", UUID(as_uuid=True), nullable=False),
        sa.Column("language", sa.String(10), nullable=False),
        sa.Column("display_name", sa.String(200), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.text("NOW()")),
    )
    op.create_index("idx_tag_group_translations_group_id", "tag_group_translations", ["tag_group_definition_id"])
    op.create_index("idx_tag_group_translations_language", "tag_group_translations", ["language"])
    op.create_unique_constraint(
        "uq_tag_group_translations_group_language",
        "tag_group_translations",
        ["tag_group_definition_id", "language"]
    )
    op.create_foreign_key(
        "fk_tag_group_translations_group_id",
        "tag_group_translations",
        "tag_group_definitions",
        ["tag_group_definition_id"],
        ["id"]
    )


def downgrade() -> None:
    op.drop_constraint("fk_tag_group_translations_group_id", "tag_group_translations", type_="foreignkey")
    op.drop_unique_constraint("uq_tag_group_translations_group_language", "tag_group_translations")
    op.drop_index("idx_tag_group_translations_language", table_name="tag_group_translations")
    op.drop_index("idx_tag_group_translations_group_id", table_name="tag_group_translations")
    op.drop_table("tag_group_translations")

    op.drop_constraint("fk_tag_translations_tag_id", "tag_translations", type_="foreignkey")
    op.drop_unique_constraint("uq_tag_translations_tag_language", "tag_translations")
    op.drop_index("idx_tag_translations_language", table_name="tag_translations")
    op.drop_index("idx_tag_translations_tag_id", table_name="tag_translations")
    op.drop_table("tag_translations")
