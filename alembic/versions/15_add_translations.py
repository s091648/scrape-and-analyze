"""add_translations

Revision ID: 15_add_translations
Revises: 14_migrate_arxiv_keywords
Create Date: 2026-04-24

Consolidated migration for i18n support:
- Add language column to analyses
- Create analysis_translations table for multi-language analysis content
- Create tag_translations table for multi-language tag names
- Create tag_group_definition_translations table for multi-language tag group names
- Migrate English content from analyses to analysis_translations
- Drop content columns from analyses
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision: str = "15_add_translations"
down_revision: Union[str, Sequence[str], None] = "14_migrate_arxiv_keywords"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ========================================
    # Step 1: Add language column to analyses
    # ========================================
    op.add_column(
        "analyses",
        sa.Column("language", sa.String(10), nullable=False, server_default="en"),
    )
    op.create_index("idx_analyses_language", "analyses", ["language"])

    # ========================================
    # Step 2: Create analysis_translations table
    # ========================================
    op.create_table(
        "analysis_translations",
        sa.Column("id", UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("analysis_id", UUID(as_uuid=True), nullable=False),
        sa.Column("language", sa.String(10), nullable=False),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("pain_points", sa.Text(), nullable=True),
        sa.Column("insights", sa.Text(), nullable=True),
        sa.Column("innovations", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.text("NOW()")),
        sa.Column("updated_at", sa.DateTime(timezone=True),
                  server_default=sa.text("NOW()")),
    )
    op.create_index(
        "idx_analysis_translations_analysis_id",
        "analysis_translations",
        ["analysis_id"],
    )
    op.create_index(
        "idx_analysis_translations_language",
        "analysis_translations",
        ["language"],
    )
    op.create_unique_constraint(
        "uq_analysis_translations_analysis_language",
        "analysis_translations",
        ["analysis_id", "language"],
    )
    op.create_foreign_key(
        "fk_analysis_translations_analysis_id",
        "analysis_translations",
        "analyses",
        ["analysis_id"],
        ["id"],
        ondelete="CASCADE",
    )

    # ========================================
    # Step 3: Create tag_translations table
    # ========================================
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
    op.create_index(
        "idx_tag_translations_tag_id", "tag_translations", ["tag_id"]
    )
    op.create_index(
        "idx_tag_translations_language", "tag_translations", ["language"]
    )
    op.create_unique_constraint(
        "uq_tag_translations_tag_language",
        "tag_translations",
        ["tag_id", "language"],
    )
    op.create_foreign_key(
        "fk_tag_translations_tag_id",
        "tag_translations",
        "tags",
        ["tag_id"],
        ["id"],
        ondelete="CASCADE",
    )

    # ========================================
    # Step 4: Create tag_group_definition_translations table
    # ========================================
    op.create_table(
        "tag_group_definition_translations",
        sa.Column("id", UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("tag_group_definition_id", UUID(as_uuid=True), nullable=False),
        sa.Column("language", sa.String(10), nullable=False),
        sa.Column("display_name", sa.String(200), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.text("NOW()")),
    )
    op.create_index(
        "idx_tag_group_definition_translations_group_id",
        "tag_group_definition_translations",
        ["tag_group_definition_id"],
    )
    op.create_index(
        "idx_tag_group_definition_translations_language",
        "tag_group_definition_translations",
        ["language"],
    )
    op.create_unique_constraint(
        "uq_tag_group_definition_translations_group_language",
        "tag_group_definition_translations",
        ["tag_group_definition_id", "language"],
    )
    op.create_foreign_key(
        "fk_tag_group_definition_translations_group_id",
        "tag_group_definition_translations",
        "tag_group_definitions",
        ["tag_group_definition_id"],
        ["id"],
        ondelete="CASCADE",
    )

    # ========================================
    # Step 5: Migrate English content from analyses
    # ========================================
    op.execute(
        """
        INSERT INTO analysis_translations
            (id, analysis_id, language, summary, pain_points, insights, innovations, created_at, updated_at)
        SELECT
            gen_random_uuid(), id, 'en', summary, pain_points, insights, innovations, analyzed_at, analyzed_at
        FROM analyses
        WHERE summary IS NOT NULL
            OR pain_points IS NOT NULL
            OR insights IS NOT NULL
            OR innovations IS NOT NULL
        """
    )

    # ========================================
    # Step 6: Drop content columns from analyses
    # ========================================
    op.drop_column("analyses", "pain_points")
    op.drop_column("analyses", "insights")
    op.drop_column("analyses", "innovations")
    op.drop_column("analyses", "summary")
    op.drop_index("idx_analyses_language", table_name="analyses")
    op.drop_column("analyses", "language")


def downgrade() -> None:
    # ========================================
    # Step 1: Re-add columns to analyses
    # ========================================
    op.add_column(
        "analyses",
        sa.Column("language", sa.String(10), nullable=True, server_default="en"),
    )
    op.add_column("analyses", sa.Column("summary", sa.Text(), nullable=True))
    op.add_column("analyses", sa.Column("innovations", sa.Text(), nullable=True))
    op.add_column("analyses", sa.Column("insights", sa.Text(), nullable=True))
    op.add_column("analyses", sa.Column("pain_points", sa.Text(), nullable=True))
    op.create_index("idx_analyses_language", "analyses", ["language"])

    # ========================================
    # Step 2: Copy English content back from analysis_translations
    # ========================================
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

    # ========================================
    # Step 3: Delete English rows from analysis_translations
    # ========================================
    op.execute("DELETE FROM analysis_translations WHERE language = 'en'")

    # ========================================
    # Step 4: Make language NOT NULL
    # ========================================
    op.alter_column("analyses", "language", nullable=False)

    # ========================================
    # Step 5: Drop tag_group_definition_translations
    # ========================================
    op.drop_constraint(
        "fk_tag_group_definition_translations_group_id",
        "tag_group_definition_translations",
        type_="foreignkey",
    )
    op.drop_unique_constraint(
        "uq_tag_group_definition_translations_group_language",
        "tag_group_definition_translations",
    )
    op.drop_index(
        "idx_tag_group_definition_translations_language",
        table_name="tag_group_definition_translations",
    )
    op.drop_index(
        "idx_tag_group_definition_translations_group_id",
        table_name="tag_group_definition_translations",
    )
    op.drop_table("tag_group_definition_translations")

    # ========================================
    # Step 6: Drop tag_translations
    # ========================================
    op.drop_constraint(
        "fk_tag_translations_tag_id",
        "tag_translations",
        type_="foreignkey",
    )
    op.drop_unique_constraint(
        "uq_tag_translations_tag_language",
        "tag_translations",
    )
    op.drop_index(
        "idx_tag_translations_language",
        table_name="tag_translations",
    )
    op.drop_index(
        "idx_tag_translations_tag_id",
        table_name="tag_translations",
    )
    op.drop_table("tag_translations")

    # ========================================
    # Step 7: Drop analysis_translations
    # ========================================
    op.drop_constraint(
        "fk_analysis_translations_analysis_id",
        "analysis_translations",
        type_="foreignkey",
    )
    op.drop_unique_constraint(
        "uq_analysis_translations_analysis_language",
        "analysis_translations",
    )
    op.drop_index(
        "idx_analysis_translations_language",
        table_name="analysis_translations",
    )
    op.drop_index(
        "idx_analysis_translations_analysis_id",
        table_name="analysis_translations",
    )
    op.drop_table("analysis_translations")