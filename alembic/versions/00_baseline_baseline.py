"""baseline

Revision ID: baseline
Revises: 
Create Date: 2026-02-21 00:11:05.176363

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = 'baseline'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'articles',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('url', sa.Text(), nullable=False, unique=True),
        sa.Column('url_hash', sa.String(64), nullable=False),
        sa.Column('source', sa.String(50), nullable=False),
        sa.Column('title', sa.Text(), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('published_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('scraped_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('metadata', postgresql.JSONB(), nullable=True),
        sa.Column('correlation_id', postgresql.UUID(as_uuid=True), nullable=False),
    )
    op.create_index('idx_articles_url_hash', 'articles', ['url_hash'])
    op.create_index('idx_articles_source', 'articles', ['source'])
    op.create_index('idx_articles_scraped_at', 'articles', ['scraped_at'])

    op.create_table(
        'analyses',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('article_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('correlation_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('tags', postgresql.ARRAY(sa.Text()), nullable=False),
        sa.Column('pain_points', sa.Text(), nullable=True),
        sa.Column('insights', sa.Text(), nullable=True),
        sa.Column('innovations', sa.Text(), nullable=True),
        sa.Column('analyzed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('model_used', sa.String(100), nullable=False),
        sa.Column('input_tokens', sa.Integer(), nullable=True),
        sa.Column('output_tokens', sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(['article_id'], ['articles.id']),
        sa.UniqueConstraint('article_id'),
    )
    op.create_index('idx_analyses_article_id', 'analyses', ['article_id'])
    op.create_index('idx_analyses_analyzed_at', 'analyses', ['analyzed_at'])

    op.create_table(
        'failed_tasks',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('task_type', sa.String(50), nullable=False),
        sa.Column('article_url', sa.Text(), nullable=True),
        sa.Column('article_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('exception_type', sa.String(200), nullable=True),
        sa.Column('exception_message', sa.Text(), nullable=True),
        sa.Column('failed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('resolved', sa.Boolean(), nullable=True),
        sa.Column('resolved_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['article_id'], ['articles.id']),
    )
    op.create_index('idx_failed_tasks_resolved', 'failed_tasks', ['resolved'])
    op.create_index('idx_failed_tasks_failed_at', 'failed_tasks', ['failed_at'])


def downgrade() -> None:
    op.drop_table('failed_tasks')
    op.drop_table('analyses')
    op.drop_table('articles')
