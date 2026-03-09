"""seed_arxiv_scraper

Revision ID: 08_seed_arxiv_scraper
Revises: 07_alter_scraper_settings_frequency
Create Date: 2026-03-10
"""
from alembic import op
import sqlalchemy as sa

revision = '08_seed_arxiv_scraper'
down_revision = '07_alter_scraper_settings_frequency'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        INSERT INTO scraper_settings
            (id, source_type, name, url, frequency, is_active, selector_config)
        VALUES (
            gen_random_uuid(),
            'arxiv',
            'arxiv',
            '',
            6,
            true,
            '{"max_results": 30, "days_back": 1}'::jsonb
        )
    """)


def downgrade() -> None:
    op.execute("DELETE FROM scraper_settings WHERE source_type = 'arxiv'")
