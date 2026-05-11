"""rename analysis_translations to analyses_translation

Revision ID: 16_rename_analysis_translations
Revises: 15_add_translations
Create Date: 2026-05-11
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "16_rename_analysis_translations"
down_revision = "15_add_translations"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Rename table
    op.rename_table("analysis_translations", "analyses_translation")

    # Rename indexes
    op.drop_index("idx_analysis_translations_analysis_id", table_name="analysis_translations")
    op.create_index("idx_analyses_translation_analysis_id", "analyses_translation", ["analysis_id"])

    op.drop_index("idx_analysis_translations_language", table_name="analysis_translations")
    op.create_index("idx_analyses_translation_language", "analyses_translation", ["language"])

    # Rename unique constraint
    op.drop_constraint("uq_analysis_translations_analysis_language", "analyses_translation", type_="unique")
    op.create_unique_constraint("uq_analyses_translation_analysis_language", "analyses_translation", ["analysis_id", "language"])

    # Rename foreign key
    op.drop_constraint("fk_analysis_translations_analysis_id", "analyses_translation", type_="foreignkey")
    op.create_foreign_key("fk_analyses_translation_analysis_id", "analyses_translation", "analyses", ["analysis_id"], ["id"], ondelete="CASCADE")


def downgrade() -> None:
    # Rename foreign key back
    op.drop_constraint("fk_analyses_translation_analysis_id", "analyses_translation", type_="foreignkey")
    op.create_foreign_key("fk_analysis_translations_analysis_id", "analyses_translation", "analyses", ["analysis_id"], ["id"], ondelete="CASCADE")

    # Rename unique constraint back
    op.drop_constraint("uq_analyses_translation_analysis_language", "analyses_translation", type_="unique")
    op.create_unique_constraint("uq_analysis_translations_analysis_language", "analyses_translation", ["analysis_id", "language"])

    # Rename indexes back
    op.drop_index("idx_analyses_translation_language", table_name="analyses_translation")
    op.create_index("idx_analysis_translations_language", "analyses_translation", ["language"])

    op.drop_index("idx_analyses_translation_analysis_id", table_name="analyses_translation")
    op.create_index("idx_analysis_translations_analysis_id", "analyses_translation", ["analysis_id"])

    # Rename table back
    op.rename_table("analyses_translation", "analysis_translations")
