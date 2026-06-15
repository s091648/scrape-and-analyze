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

    # Parent table — stores article metadata for search result joins
    op.create_table(
        "articles",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("url", sa.Text(), nullable=False, unique=True),
        sa.Column("title", sa.Text(), nullable=True),
        sa.Column("source", sa.Text(), nullable=True),
        sa.Column("metadata", JSONB, nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        schema="vectors",
    )
    op.create_index("idx_articles_url",    "articles", ["url"],    schema="vectors")
    op.create_index("idx_articles_source", "articles", ["source"], schema="vectors")

    # Chunk table — one row per text chunk, holds dense + sparse vectors
    #   dense_vector  VECTOR(768)       — Gemini embedding-001 dimension
    #   sparse_vector SPARSEVEC(30522)  — SPLADE BERT vocab dimension
    op.create_table(
        "article_chunks",
        sa.Column(
            "id", UUID(as_uuid=True), primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "article_id", UUID(as_uuid=True),
            sa.ForeignKey("vectors.articles.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("chunk_index", sa.Integer(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("dense_vector", sa.Text(), nullable=True),
        sa.Column("sparse_vector", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.UniqueConstraint(
            "article_id", "chunk_index",
            name="uq_article_chunks_article_chunk_idx",
        ),
        schema="vectors",
    )
    op.execute(
        "ALTER TABLE vectors.article_chunks "
        "ALTER COLUMN dense_vector TYPE vector(768) USING dense_vector::vector(768)"
    )
    op.execute(
        "ALTER TABLE vectors.article_chunks "
        "ALTER COLUMN sparse_vector TYPE sparsevec(30522) USING NULL"
    )
    op.execute(
        "CREATE INDEX idx_article_chunks_dense_vector "
        "ON vectors.article_chunks USING hnsw (dense_vector vector_cosine_ops)"
    )
    op.execute(
        "CREATE INDEX idx_article_chunks_sparse_vector "
        "ON vectors.article_chunks USING hnsw (sparse_vector sparsevec_cosine_ops)"
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS vectors.article_chunks CASCADE")
    op.execute("DROP TABLE IF EXISTS vectors.articles CASCADE")
    op.execute("DROP SCHEMA IF EXISTS vectors")
