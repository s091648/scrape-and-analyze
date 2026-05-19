"""add_pgvector_and_tag_normalization_suggestions

Revision ID: 16_add_pgvector_and_tag_normalization
Revises: 15_add_translations
Create Date: 2026-05-18
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision: str = "16_add_pgvector"
down_revision: Union[str, Sequence[str], None] = "15_add_translations"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. Enable pgvector extension
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    # 2. Add embedding column to tags (nullable — backfilled separately)
    op.add_column(
        "tags",
        sa.Column("embedding", sa.Text(), nullable=True),  # stored as text, cast by pgvector
    )
    # Use raw DDL for vector type since SQLAlchemy doesn't know it natively
    op.execute("ALTER TABLE tags ALTER COLUMN embedding TYPE vector(768) USING embedding::vector")

    # 3. Create HNSW index for fast cosine similarity search
    op.execute(
        "CREATE INDEX idx_tags_embedding ON tags USING hnsw (embedding vector_cosine_ops)"
    )

    # 4. Create tag_normalization_suggestions table
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


def downgrade() -> None:
    op.drop_index("idx_tns_new_tag_id", table_name="tag_normalization_suggestions")
    op.drop_index("idx_tns_status", table_name="tag_normalization_suggestions")
    op.drop_constraint("fk_tns_article", "tag_normalization_suggestions", type_="foreignkey")
    op.drop_constraint("fk_tns_existing_tag", "tag_normalization_suggestions", type_="foreignkey")
    op.drop_constraint("fk_tns_new_tag", "tag_normalization_suggestions", type_="foreignkey")
    op.drop_table("tag_normalization_suggestions")
    op.execute("DROP INDEX IF EXISTS idx_tags_embedding")
    op.drop_column("tags", "embedding")
