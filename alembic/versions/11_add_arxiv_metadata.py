"""add_arxiv_metadata_table

Revision ID: 11_add_arxiv_metadata
Revises: 10_add_summary_to_analyses
Create Date: 2026-04-09
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB, ARRAY

revision: str = "11_add_arxiv_metadata"
down_revision: Union[str, Sequence[str], None] = "10_add_summary_to_analyses"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "arxiv_metadata",
        sa.Column("id", UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("article_id", UUID(as_uuid=True),
                  sa.ForeignKey("articles.id", ondelete="CASCADE"),
                  nullable=False),
        sa.Column("arxiv_id", sa.String(50), nullable=True),
        sa.Column("authors", ARRAY(sa.Text()), nullable=False,
                  server_default=sa.text("ARRAY[]::text[]")),
        sa.Column("pdf_available", sa.Boolean(), nullable=False,
                  server_default=sa.text("false")),
        sa.Column("sections", JSONB, nullable=False,
                  server_default=sa.text("'{}'")),
    )
    op.create_unique_constraint(
        "uq_arxiv_metadata_article_id", "arxiv_metadata", ["article_id"]
    )
    op.create_index(
        "idx_arxiv_metadata_article_id", "arxiv_metadata", ["article_id"]
    )
    # Backfill: existing arxiv articles get a row; sections left empty
    op.execute("""
        INSERT INTO arxiv_metadata (id, article_id, arxiv_id, authors, pdf_available, sections)
        SELECT
            gen_random_uuid(),
            a.id,
            a.metadata->>'arxiv_id',
            COALESCE(
                ARRAY(SELECT jsonb_array_elements_text(a.metadata->'authors')),
                ARRAY[]::text[]
            ),
            COALESCE((a.metadata->>'pdf_available')::boolean, false),
            '{}'::jsonb
        FROM articles a
        WHERE a.source = 'arxiv'
        ON CONFLICT DO NOTHING
    """)



def downgrade() -> None:
    op.drop_index("idx_arxiv_metadata_article_id", table_name="arxiv_metadata")
    op.drop_constraint("uq_arxiv_metadata_article_id", "arxiv_metadata")
    op.drop_table("arxiv_metadata")
