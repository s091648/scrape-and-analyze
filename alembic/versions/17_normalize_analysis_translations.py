"""normalize_analysis_translations

Revision ID: 17_normalize_analysis_translations
Revises: 16_add_tag_translations
Create Date: 2026-05-07

Move content columns (summary, pain_points, insights, innovations) from
analyses into analysis_translations (renamed from translations) so that
all language variants — including English — live in a single table.
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision: str = "17_normalize_analysis_translations"
down_revision: Union[str, Sequence[str], None] = "16_add_tag_translations"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. Rename translations table → analysis_translations
    op.rename_table("translations", "analysis_translations")

    # 2. Rename indexes, unique constraint, and FK to match new table name
    op.drop_index("idx_translations_analysis_id", table_name="analysis_translations")
    op.create_index(
        "idx_analysis_translations_analysis_id",
        "analysis_translations",
        ["analysis_id"],
    )
    op.drop_index("idx_translations_language", table_name="analysis_translations")
    op.create_index(
        "idx_analysis_translations_language",
        "analysis_translations",
        ["language"],
    )
    op.drop_constraint(
        "uq_translations_analysis_language",
        "analysis_translations",
        type_="unique",
    )
    op.create_unique_constraint(
        "uq_analysis_translations_analysis_language",
        "analysis_translations",
        ["analysis_id", "language"],
    )
    op.drop_constraint(
        "fk_translations_analysis_id",
        "analysis_translations",
        type_="foreignkey",
    )
    op.create_foreign_key(
        "fk_analysis_translations_analysis_id",
        "analysis_translations",
        "analyses",
        ["analysis_id"],
        ["id"],
        ondelete="CASCADE",
    )

    # 3. Migrate English content from analyses into analysis_translations
    op.execute(
        """
        INSERT INTO analysis_translations (id, analysis_id, language, summary, pain_points, insights, innovations, created_at, updated_at)
        SELECT gen_random_uuid(), id, 'en', summary, pain_points, insights, innovations, analyzed_at, analyzed_at
        FROM analyses
        WHERE summary IS NOT NULL OR pain_points IS NOT NULL OR insights IS NOT NULL OR innovations IS NOT NULL
        """
    )

    # 4. Drop content columns and language column from analyses
    op.drop_column("analyses", "pain_points")
    op.drop_column("analyses", "insights")
    op.drop_column("analyses", "innovations")
    op.drop_column("analyses", "summary")
    op.drop_index("idx_analyses_language", table_name="analyses")
    op.drop_column("analyses", "language")


def downgrade() -> None:
    # 1. Re-add dropped columns to analyses (all nullable for safety)
    op.add_column(
        "analyses",
        sa.Column("language", sa.String(10), nullable=True, server_default="en"),
    )
    op.add_column("analyses", sa.Column("summary", sa.Text(), nullable=True))
    op.add_column(
        "analyses", sa.Column("innovations", sa.Text(), nullable=True)
    )
    op.add_column("analyses", sa.Column("insights", sa.Text(), nullable=True))
    op.add_column(
        "analyses", sa.Column("pain_points", sa.Text(), nullable=True)
    )
    op.create_index("idx_analyses_language", "analyses", ["language"])

    # 2. Copy English content back from analysis_translations → analyses
    op.execute(
        """
        UPDATE analyses
        SET summary = at.summary,
            pain_points = at.pain_points,
            insights = at.insights,
            innovations = at.innovations,
            language = 'en'
        FROM analysis_translations at
        WHERE at.analysis_id = analyses.id AND at.language = 'en'
        """
    )

    # 3. Delete English rows from analysis_translations (reverse of migration step)
    op.execute(
        "DELETE FROM analysis_translations WHERE language = 'en'"
    )

    # 4. Make language NOT NULL again
    op.alter_column("analyses", "language", nullable=False)

    # 5. Rename table and constraints back to translations
    op.drop_constraint(
        "fk_analysis_translations_analysis_id",
        "analysis_translations",
        type_="foreignkey",
    )
    op.create_foreign_key(
        "fk_translations_analysis_id",
        "analysis_translations",
        "analyses",
        ["analysis_id"],
        ["id"],
    )
    op.drop_constraint(
        "uq_analysis_translations_analysis_language",
        "analysis_translations",
        type_="unique",
    )
    op.create_unique_constraint(
        "uq_translations_analysis_language",
        "analysis_translations",
        ["analysis_id", "language"],
    )
    op.drop_index(
        "idx_analysis_translations_language", table_name="analysis_translations"
    )
    op.create_index(
        "idx_translations_language", "analysis_translations", ["language"]
    )
    op.drop_index(
        "idx_analysis_translations_analysis_id",
        table_name="analysis_translations",
    )
    op.create_index(
        "idx_translations_analysis_id", "analysis_translations", ["analysis_id"]
    )

    op.rename_table("analysis_translations", "translations")
