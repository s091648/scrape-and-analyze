"""add_translations

Revision ID: 15_add_translations
Revises: 14_migrate_arxiv_keywords
Create Date: 2026-04-24

Consolidated migration for i18n support:
- Add language column to analyses
- Create analyses_translation table for multi-language analysis content
- Create tags_translation table for multi-language tag names
- Create tag_group_definitions_translation table for multi-language tag group names and descriptions
- Migrate English content from analyses to analyses_translation
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
    # Step 2: Create analyses_translation table
    # ========================================
    op.create_table(
        "analyses_translation",
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
        "idx_analyses_translation_analysis_id",
        "analyses_translation",
        ["analysis_id"],
    )
    op.create_index(
        "idx_analyses_translation_language",
        "analyses_translation",
        ["language"],
    )
    op.create_unique_constraint(
        "uq_analyses_translation_analysis_language",
        "analyses_translation",
        ["analysis_id", "language"],
    )
    op.create_foreign_key(
        "fk_analyses_translation_analysis_id",
        "analyses_translation",
        "analyses",
        ["analysis_id"],
        ["id"],
        ondelete="CASCADE",
    )

    # ========================================
    # Step 3: Create tags_translation table
    # ========================================
    op.create_table(
        "tags_translation",
        sa.Column("id", UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("tag_id", UUID(as_uuid=True), nullable=False),
        sa.Column("language", sa.String(10), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.text("NOW()")),
    )
    op.create_index(
        "idx_tags_translation_tag_id", "tags_translation", ["tag_id"]
    )
    op.create_index(
        "idx_tags_translation_language", "tags_translation", ["language"]
    )
    op.create_unique_constraint(
        "uq_tags_translation_tag_language",
        "tags_translation",
        ["tag_id", "language"],
    )
    op.create_foreign_key(
        "fk_tags_translation_tag_id",
        "tags_translation",
        "tags",
        ["tag_id"],
        ["id"],
        ondelete="CASCADE",
    )

    # ========================================
    # Step 4: Create tag_group_definitions_translation table
    # ========================================
    op.create_table(
        "tag_group_definitions_translation",
        sa.Column("id", UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("tag_group_definition_id", UUID(as_uuid=True), nullable=False),
        sa.Column("language", sa.String(10), nullable=False),
        sa.Column("display_name", sa.String(200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.text("NOW()")),
    )
    op.create_index(
        "idx_tag_group_definitions_translation_group_id",
        "tag_group_definitions_translation",
        ["tag_group_definition_id"],
    )
    op.create_index(
        "idx_tag_group_definitions_translation_language",
        "tag_group_definitions_translation",
        ["language"],
    )
    op.create_unique_constraint(
        "uq_tag_group_definitions_translation_group_language",
        "tag_group_definitions_translation",
        ["tag_group_definition_id", "language"],
    )
    op.create_foreign_key(
        "fk_tag_group_definitions_translation_group_id",
        "tag_group_definitions_translation",
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
        INSERT INTO analyses_translation
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
    # Step 2: Copy English content back from analyses_translation
    # ========================================
    op.execute(
        """
        UPDATE analyses
        SET summary = at.summary,
            pain_points = at.pain_points,
            insights = at.insights,
            innovations = at.innovations,
            language = 'en'
        FROM analyses_translation at
        WHERE at.analysis_id = analyses.id AND at.language = 'en'
        """
    )

    # ========================================
    # Step 3: Delete English rows from analyses_translation
    # ========================================
    op.execute("DELETE FROM analyses_translation WHERE language = 'en'")

    # ========================================
    # Step 4: Make language NOT NULL
    # ========================================
    op.alter_column("analyses", "language", nullable=False)

    # ========================================
    # Step 5: Drop tag_group_definitions_translation
    # ========================================
    op.drop_constraint(
        "fk_tag_group_definitions_translation_group_id",
        "tag_group_definitions_translation",
        type_="foreignkey",
    )
    op.drop_unique_constraint(
        "uq_tag_group_definitions_translation_group_language",
        "tag_group_definitions_translation",
    )
    op.drop_index(
        "idx_tag_group_definitions_translation_language",
        table_name="tag_group_definitions_translation",
    )
    op.drop_index(
        "idx_tag_group_definitions_translation_group_id",
        table_name="tag_group_definitions_translation",
    )
    op.drop_table("tag_group_definitions_translation")

    # ========================================
    # Step 6: Drop tags_translation
    # ========================================
    op.drop_constraint(
        "fk_tags_translation_tag_id",
        "tags_translation",
        type_="foreignkey",
    )
    op.drop_unique_constraint(
        "uq_tags_translation_tag_language",
        "tags_translation",
    )
    op.drop_index(
        "idx_tags_translation_language",
        table_name="tags_translation",
    )
    op.drop_index(
        "idx_tags_translation_tag_id",
        table_name="tags_translation",
    )
    op.drop_table("tags_translation")

    # ========================================
    # Step 7: Drop analyses_translation
    # ========================================
    op.drop_constraint(
        "fk_analyses_translation_analysis_id",
        "analyses_translation",
        type_="foreignkey",
    )
    op.drop_unique_constraint(
        "uq_analyses_translation_analysis_language",
        "analyses_translation",
    )
    op.drop_index(
        "idx_analyses_translation_language",
        table_name="analyses_translation",
    )
    op.drop_index(
        "idx_analyses_translation_analysis_id",
        table_name="analyses_translation",
    )
    op.drop_table("analyses_translation")
