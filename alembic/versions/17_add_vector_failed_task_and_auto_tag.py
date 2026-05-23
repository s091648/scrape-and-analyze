"""squash_pgvector_extend_tasks_add_auto_tag_groups_add_embedding_providers

Squashes migrations 16 (pgvector + tag_normalization_suggestions) and
17 (extend failed_tasks), adds auto_tag_groups boolean to topics,
and extends llm_providers with a type column + seeds embedding providers.

Revision ID: 17_add_vector_failed_task_and_auto_tag
Revises: 16_add_llm_providers
Create Date: 2026-05-22
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB

revision: str = "17_add_vector_failed_task_and_auto_tag"
down_revision: Union[str, Sequence[str], None] = "16_add_llm_providers"
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

    # ── llm_providers: add type column ──

    op.add_column(
        "llm_providers",
        sa.Column("type", sa.String(20), nullable=False, server_default="llm"),
    )

    # Replace priority-only unique constraint with (priority, type) unique constraint
    op.drop_constraint("uq_llm_providers_priority", "llm_providers", type_="unique")
    op.execute("""
        ALTER TABLE llm_providers
        ADD CONSTRAINT uq_llm_providers_priority_type
        UNIQUE (priority, type)
        DEFERRABLE INITIALLY DEFERRED
    """)

    # Seed embedding providers
    op.execute("""
        INSERT INTO llm_providers (id, name, model, api_key_env, priority, type, is_active, rpm, tpm, rpd)
        VALUES
            (gen_random_uuid(), 'gemini', 'gemini-embedding-001', 'GEMINI_API_KEY', 1, 'embedding', true, 100, 30000, 1000),
            (gen_random_uuid(), 'gemini', 'gemini-embedding-2', 'GEMINI_API_KEY', 2, 'embedding', true, 100, 30000, 1000)
    """)

    # ── tag_group_definitions: embedding vector ──

    op.add_column(
        "tag_group_definitions",
        sa.Column("embedding", sa.Text(), nullable=True),
    )
    op.execute(
        "ALTER TABLE tag_group_definitions ALTER COLUMN embedding "
        "TYPE vector(768) USING embedding::vector"
    )
    op.execute(
        "CREATE INDEX idx_tag_group_defs_embedding "
        "ON tag_group_definitions USING hnsw (embedding vector_cosine_ops)"
    )


def downgrade() -> None:
    # ── reverse tag_group_definitions embedding (added last, reversed first) ──
    op.execute("DROP INDEX IF EXISTS idx_tag_group_defs_embedding")
    op.drop_column("tag_group_definitions", "embedding")

    # ── reverse llm_providers embedding changes (added last, reversed first) ──

    op.execute("DELETE FROM llm_providers WHERE type = 'embedding'")
    op.execute("ALTER TABLE llm_providers DROP CONSTRAINT uq_llm_providers_priority_type")
    op.execute("""
        ALTER TABLE llm_providers
        ADD CONSTRAINT uq_llm_providers_priority
        UNIQUE (priority)
        DEFERRABLE INITIALLY DEFERRED
    """)
    op.drop_column("llm_providers", "type")

    # ── reverse remaining changes ──

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
