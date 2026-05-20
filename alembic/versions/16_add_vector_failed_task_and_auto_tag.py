"""squash_pgvector_extend_tasks_add_auto_tag_groups

Squashes migrations 16 (pgvector + tag_normalization_suggestions) and
17 (extend failed_tasks), and adds auto_tag_groups boolean to topics.

Requires alembic_version.version_num >= VARCHAR(64); 15_add_translations
expands the column before this revision is stamped.

Revision ID: 16_add_vector_failed_task_and_auto_tag
Revises: 15_add_translations
Create Date: 2026-05-21
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB

revision: str = "16_add_vector_failed_task_and_auto_tag"
down_revision: Union[str, Sequence[str], None] = "15_add_translations"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── pgvector extension + tag embedding ──

    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    op.add_column(
        "tags",
        sa.Column("embedding", sa.Text(), nullable=True),
    )
    op.execute(
        "ALTER TABLE tags ALTER COLUMN embedding TYPE vector(768) USING embedding::vector"
    )
    op.execute(
        "CREATE INDEX idx_tags_embedding ON tags USING hnsw (embedding vector_cosine_ops)"
    )

    # ── tag_normalization_suggestions ──

    op.create_table(
        "tag_normalization_suggestions",
        sa.Column("id", UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("new_tag_id", UUID(as_uuid=True), nullable=False),
        sa.Column("existing_tag_id", UUID(as_uuid=True), nullable=False),
        sa.Column("similarity_score", sa.Float(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("article_id", UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()")),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resolved_by", UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_tns_new_tag", "tag_normalization_suggestions", "tags",
        ["new_tag_id"], ["id"], ondelete="CASCADE",
    )
    op.create_foreign_key(
        "fk_tns_existing_tag", "tag_normalization_suggestions", "tags",
        ["existing_tag_id"], ["id"], ondelete="CASCADE",
    )
    op.create_foreign_key(
        "fk_tns_article", "tag_normalization_suggestions", "articles",
        ["article_id"], ["id"], ondelete="SET NULL",
    )
    op.create_index("idx_tns_status", "tag_normalization_suggestions", ["status"])
    op.create_index("idx_tns_new_tag_id", "tag_normalization_suggestions", ["new_tag_id"])

    # ── extend failed_tasks ──

    op.add_column("failed_tasks", sa.Column("analysis_id", UUID(as_uuid=True), nullable=True))
    op.create_foreign_key(
        "fk_failed_tasks_analysis_id", "failed_tasks", "analyses",
        ["analysis_id"], ["id"], ondelete="SET NULL",
    )
    op.add_column("failed_tasks", sa.Column("context", JSONB(), nullable=True))
    op.add_column("failed_tasks", sa.Column("traceback", sa.Text(), nullable=True))

    # ── auto_tag_groups flag on topics ──

    op.add_column("topics", sa.Column(
        "auto_tag_groups",
        sa.Boolean(),
        nullable=False,
        server_default=sa.text("true"),
    ))


def downgrade() -> None:
    op.drop_column("topics", "auto_tag_groups")

    op.drop_column("failed_tasks", "traceback")
    op.drop_column("failed_tasks", "context")
    op.drop_constraint("fk_failed_tasks_analysis_id", "failed_tasks", type_="foreignkey")
    op.drop_column("failed_tasks", "analysis_id")

    op.drop_index("idx_tns_new_tag_id", table_name="tag_normalization_suggestions")
    op.drop_index("idx_tns_status", table_name="tag_normalization_suggestions")
    op.drop_constraint("fk_tns_article", "tag_normalization_suggestions", type_="foreignkey")
    op.drop_constraint("fk_tns_existing_tag", "tag_normalization_suggestions", type_="foreignkey")
    op.drop_constraint("fk_tns_new_tag", "tag_normalization_suggestions", type_="foreignkey")
    op.drop_table("tag_normalization_suggestions")
    op.execute("DROP INDEX IF EXISTS idx_tags_embedding")
    op.drop_column("tags", "embedding")
