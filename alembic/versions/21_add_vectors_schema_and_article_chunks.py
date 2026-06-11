"""add_vectors_schema_and_article_chunks

Revision ID: 21_add_vectors_schema_and_article_chunks
Revises: 20_add_article_translation
Create Date: 2026-06-11
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "21_add_vectors_schema_and_article_chunks"
down_revision = "20_add_article_translation"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE SCHEMA IF NOT EXISTS vectors")
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    op.create_table(
        "article_chunks",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("article_id", UUID(as_uuid=True), sa.ForeignKey("articles.id", ondelete="CASCADE"), nullable=False),
        sa.Column("chunk_index", sa.Integer(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("embedding", sa.Text(), nullable=True),  # stored as pgvector VECTOR(768)
        sa.Column("source_url", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.UniqueConstraint("article_id", "chunk_index", name="uq_article_chunks_article_chunk"),
        schema="vectors",
    )

    # Cast embedding column to pgvector type after table creation
    op.execute("ALTER TABLE vectors.article_chunks ALTER COLUMN embedding TYPE vector(768) USING embedding::vector(768)")
    op.execute("CREATE INDEX ON vectors.article_chunks USING ivfflat (embedding vector_cosine_ops)")


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS vectors.article_chunks")
    op.execute("DROP SCHEMA IF EXISTS vectors")
