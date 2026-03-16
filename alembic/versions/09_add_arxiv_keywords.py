"""add_arxiv_keywords

Revision ID: 09_add_arxiv_keywords
Revises: 08_seed_arxiv_scraper
Create Date: 2026-03-16
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = '09_add_arxiv_keywords'
down_revision = '08_seed_arxiv_scraper'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'arxiv_keywords',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('keyword', sa.String(500), nullable=False, unique=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
    )
    # Seed the previously hardcoded keywords from arxiv_scraper._build_query
    op.execute("""
        INSERT INTO arxiv_keywords (id, keyword, created_at) VALUES
        (gen_random_uuid(), 'ti:"digital twin"', NOW()),
        (gen_random_uuid(), 'ti:"digital twins"', NOW()),
        (gen_random_uuid(), 'abs:"digital twin"', NOW()),
        (gen_random_uuid(), 'abs:"cyber-physical"', NOW())
    """)


def downgrade() -> None:
    op.drop_table('arxiv_keywords')
