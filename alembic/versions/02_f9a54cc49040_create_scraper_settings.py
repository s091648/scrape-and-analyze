"""create_scraper_settings

Revision ID: f9a54cc49040
Revises: 4f2e59c8650f
Create Date: 2026-02-21 00:45:48.678619

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB
import uuid

revision = 'f9a54cc49040'
down_revision = '4f2e59c8650f'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'scraper_settings',
        sa.Column('id', UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column('source_type', sa.String(20), nullable=False),  # 'rss' | 'blog'
        sa.Column('name', sa.String(100), nullable=False),
        sa.Column('url', sa.Text, nullable=False),
        sa.Column('frequency', sa.String(20), nullable=False),  # 'daily' | 'weekly'
        sa.Column('is_active', sa.Boolean, nullable=False, server_default='true'),
        sa.Column('selector_config', JSONB),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # Seed existing RSS sources (daily)
    rss_sources = [
        ('techcrunch', 'https://techcrunch.com/feed/'),
        ('venturebeat', 'https://venturebeat.com/feed/'),
        ('iotworldtoday', 'https://www.iotworldtoday.com/rss.xml'),
    ]
    for name, url in rss_sources:
        op.execute(
            f"INSERT INTO scraper_settings (id, source_type, name, url, frequency, is_active) "
            f"VALUES (gen_random_uuid(), 'rss', '{name}', '{url}', 'daily', true)"
        )

    # Seed existing blog sources (weekly)
    blog_sources = [
        ('nvidia', 'https://developer.nvidia.com/blog',
         '{"article_link": ".post-card a.post-card__link", "title": "h1.post-title", "content": ".post-content"}'),
        ('siemens', 'https://blogs.sw.siemens.com/digital-transformation',
         '{"article_link": "article.post a.entry-title-link", "title": "h1.entry-title", "content": ".entry-content"}'),
        ('aws_iot', 'https://aws.amazon.com/blogs/iot',
         '{"article_link": ".blog-post a.title", "title": "h1.blog-post-title", "content": ".blog-post-content"}'),
        ('azure_iot', 'https://azure.microsoft.com/en-us/blog/topics/internet-of-things',
         '{"article_link": ".card a.card-link", "title": "h1.article-title", "content": ".article-content"}'),
    ]
    for name, url, selectors in blog_sources:
        op.execute(
            f"INSERT INTO scraper_settings (id, source_type, name, url, frequency, is_active, selector_config) "
            f"VALUES (gen_random_uuid(), 'blog', '{name}', '{url}', 'weekly', true, '{selectors}'::jsonb)"
        )


def downgrade() -> None:
    op.drop_table('scraper_settings')
