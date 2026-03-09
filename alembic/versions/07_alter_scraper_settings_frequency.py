"""alter_scraper_settings_frequency

Revision ID: 07_alter_scraper_settings_frequency
Revises: 06_extend_auth_users
Create Date: 2026-03-10
"""
from alembic import op
import sqlalchemy as sa

revision = '07_alter_scraper_settings_frequency'
down_revision = '06_extend_auth_users'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add last_scraped_at
    op.add_column('scraper_settings',
        sa.Column('last_scraped_at', sa.DateTime(timezone=True), nullable=True)
    )

    # Add temp integer column, populate, swap
    op.add_column('scraper_settings',
        sa.Column('frequency_hours', sa.Integer(), nullable=True)
    )
    op.execute("UPDATE scraper_settings SET frequency_hours = 24  WHERE frequency = 'daily'")
    op.execute("UPDATE scraper_settings SET frequency_hours = 168 WHERE frequency = 'weekly'")
    op.drop_column('scraper_settings', 'frequency')
    op.alter_column('scraper_settings', 'frequency_hours',
                    new_column_name='frequency', nullable=False)


def downgrade() -> None:
    op.add_column('scraper_settings',
        sa.Column('frequency_str', sa.String(20), nullable=True)
    )
    op.execute("UPDATE scraper_settings SET frequency_str = 'daily'  WHERE frequency = 24")
    op.execute("UPDATE scraper_settings SET frequency_str = 'weekly' WHERE frequency = 168")
    op.drop_column('scraper_settings', 'frequency')
    op.alter_column('scraper_settings', 'frequency_str',
                    new_column_name='frequency', nullable=False)
    op.drop_column('scraper_settings', 'last_scraped_at')
