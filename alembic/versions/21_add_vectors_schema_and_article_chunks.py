"""add_vectors_schema_and_article_chunks

Revision ID: 21_add_vectors_schema_and_article_chunks
Revises: 20_add_article_translation
Create Date: 2026-06-11
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision = "21_add_vectors_schema_and_article_chunks"
down_revision = "20_add_article_translation"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE SCHEMA IF NOT EXISTS vectors")
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    # Denormalised flag on public.articles — kept in sync by trigger below
    op.execute(
        "ALTER TABLE public.articles "
        "ADD COLUMN IF NOT EXISTS has_vectors BOOLEAN NOT NULL DEFAULT FALSE"
    )

    # Parent table — stores article metadata for search result joins
    op.create_table(
        "articles",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("url", sa.Text(), nullable=False, unique=True),
        sa.Column("title", sa.Text(), nullable=True),
        sa.Column("source", sa.Text(), nullable=True),
        sa.Column("public_article_id", UUID(as_uuid=True), nullable=True),
        sa.Column("topic_id", UUID(as_uuid=True), nullable=True),
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

    op.execute("""
        CREATE OR REPLACE FUNCTION public.sync_article_has_vectors()
        RETURNS TRIGGER AS $$
        BEGIN
          IF TG_OP = 'INSERT' THEN
            IF NEW.public_article_id IS NOT NULL THEN
              UPDATE public.articles SET has_vectors = TRUE WHERE id = NEW.public_article_id;
            END IF;
          ELSIF TG_OP = 'DELETE' THEN
            IF OLD.public_article_id IS NOT NULL THEN
              UPDATE public.articles
              SET has_vectors = EXISTS (
                SELECT 1 FROM vectors.articles WHERE public_article_id = OLD.public_article_id
              )
              WHERE id = OLD.public_article_id;
            END IF;
          END IF;
          RETURN NULL;
        END;
        $$ LANGUAGE plpgsql
    """)
    op.execute("""
        CREATE TRIGGER trg_sync_article_has_vectors
          AFTER INSERT OR DELETE ON vectors.articles
          FOR EACH ROW EXECUTE FUNCTION public.sync_article_has_vectors()
    """)

    # Backfill articles that already have vector rows
    op.execute("""
        UPDATE public.articles a
        SET has_vectors = TRUE
        WHERE EXISTS (
          SELECT 1 FROM vectors.articles va WHERE va.public_article_id = a.id
        )
    """)


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_sync_article_has_vectors ON vectors.articles")
    op.execute("DROP FUNCTION IF EXISTS public.sync_article_has_vectors()")
    op.execute("ALTER TABLE public.articles DROP COLUMN IF EXISTS has_vectors")
    op.execute("DROP TABLE IF EXISTS vectors.article_chunks CASCADE")
    op.execute("DROP TABLE IF EXISTS vectors.articles CASCADE")
    op.execute("DROP SCHEMA IF EXISTS vectors")
