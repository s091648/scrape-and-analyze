"""add_data_migrations_table_and_tag_group_id_fk

Add data_migrations tracking table.
Replace tags.tag_group_name (string join) with tags.tag_group_id (UUID FK)
to fix cross-topic group name collisions and simplify merge/rename operations.

Revision ID: 18_add_data_migrations_table
Revises: 17_add_vector_failed_task_and_auto_tag
Create Date: 2026-05-24
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "18_add_data_migrations_table"
down_revision = "17_add_vector_failed_task_and_auto_tag"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── data_migrations tracking table ──

    op.create_table(
        "data_migrations",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("name", sa.String(200), nullable=False, unique=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("executed_at", sa.DateTime(timezone=True),
                  server_default=sa.text("NOW()"), nullable=False),
        sa.Column("rolled_back_at", sa.DateTime(timezone=True), nullable=True),
    )

    # ── tags: replace tag_group_name (string) with tag_group_id (UUID FK) ──

    # 0. Auto-create missing tag_group_definitions for any (tag_group_name, topic_id)
    #    pair that exists in tags but has no matching definition row yet.
    #    This makes the migration self-contained — no need to run
    #    backfill_tag_group_definitions.py beforehand.
    op.execute("""
        INSERT INTO tag_group_definitions (id, name, display_name, topic_id)
        SELECT
            gen_random_uuid(),
            t.tag_group_name,
            t.tag_group_name || '_unsupervised',
            a.topic_id
        FROM tags t
        JOIN article_tags at2 ON at2.tag_id = t.id
        JOIN articles a       ON a.id = at2.article_id
        WHERE t.tag_group_name IS NOT NULL
          AND t.tag_group_name <> ''
          AND a.topic_id IN (SELECT id FROM topics)
          AND NOT EXISTS (
              SELECT 1 FROM tag_group_definitions tgd
              WHERE tgd.name = t.tag_group_name
                AND tgd.topic_id = a.topic_id
          )
        ON CONFLICT (name, topic_id) DO NOTHING
    """)

    # 1. Delete orphan tags — no article associations means topic cannot be resolved
    op.execute("""
        DELETE FROM tags
        WHERE NOT EXISTS (
            SELECT 1 FROM article_tags at WHERE at.tag_id = tags.id
        )
    """)

    # 2. Add tag_group_id column (nullable for backfill)
    op.add_column(
        "tags",
        sa.Column("tag_group_id", UUID(as_uuid=True), nullable=True),
    )

    # 3. Backfill: resolve tag_group_id via article_tags → articles.topic_id
    op.execute("""
        UPDATE tags t
        SET tag_group_id = tgd.id
        FROM tag_group_definitions tgd
        WHERE tgd.name = t.tag_group_name
          AND tgd.topic_id = (
              SELECT a.topic_id
              FROM article_tags at
              JOIN articles a ON a.id = at.article_id
              WHERE at.tag_id = t.id
              LIMIT 1
          )
    """)

    # 3b. Last-resort: delete truly unresolvable tags (tag_group_name is blank/null
    #     or couldn't be matched even after step 0). Must remove article_tags first.
    op.execute("""
        DELETE FROM article_tags
        WHERE tag_id IN (SELECT id FROM tags WHERE tag_group_id IS NULL)
    """)
    op.execute("""
        DELETE FROM tags
        WHERE tag_group_id IS NULL
    """)

    # 4. Set NOT NULL — all unresolvable rows deleted above
    op.alter_column("tags", "tag_group_id", nullable=False)

    # 5. FK: cascade so deleting a group also deletes its tags
    op.create_foreign_key(
        "fk_tags_tag_group_id",
        "tags", "tag_group_definitions",
        ["tag_group_id"], ["id"],
        ondelete="CASCADE",
    )

    # 6. Swap unique constraint
    op.drop_constraint("uq_tag_name_group", "tags", type_="unique")
    op.create_unique_constraint("uq_tag_name_group", "tags", ["name", "tag_group_id"])

    # 7. Swap index
    op.drop_index("idx_tags_group", table_name="tags")
    op.create_index("idx_tags_group", "tags", ["tag_group_id"])

    # 8. Drop tag_group_name
    op.drop_column("tags", "tag_group_name")


def downgrade() -> None:
    # ── reverse tags schema change ──

    # 1. Re-add tag_group_name (nullable for backfill)
    op.add_column(
        "tags",
        sa.Column("tag_group_name", sa.String(100), nullable=True),
    )

    # 2. Backfill tag_group_name from tag_group_id
    op.execute("""
        UPDATE tags t
        SET tag_group_name = tgd.name
        FROM tag_group_definitions tgd
        WHERE tgd.id = t.tag_group_id
    """)

    # 3. Set NOT NULL
    op.alter_column("tags", "tag_group_name", nullable=False)

    # 4. Swap index
    op.drop_index("idx_tags_group", table_name="tags")
    op.create_index("idx_tags_group", "tags", ["tag_group_name"])

    # 5. Swap unique constraint
    op.drop_constraint("uq_tag_name_group", "tags", type_="unique")
    op.create_unique_constraint("uq_tag_name_group", "tags", ["name", "tag_group_name"])

    # 6. Drop FK and tag_group_id
    op.drop_constraint("fk_tags_tag_group_id", "tags", type_="foreignkey")
    op.drop_column("tags", "tag_group_id")

    # Note: orphan tags deleted in upgrade() cannot be restored.

    # ── reverse data_migrations table ──

    op.drop_table("data_migrations")
