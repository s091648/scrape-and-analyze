# alembic/versions/23_article_recommendation_weekly_report.py
"""article_recommendation_weekly_report

Revision ID: 23_article_recommendation_weekly_report
Revises: 22_add_correlation_id_and_rag_providers
Create Date: 2026-06-27
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB

revision = '23_article_recommendation_weekly_report'
down_revision = '22_add_correlation_id_and_rag_providers'
branch_labels = None
depends_on = None


def upgrade():
    # --- article_metrics ---
    op.create_table(
        'article_metrics',
        sa.Column('id', UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('article_id', UUID(as_uuid=True), sa.ForeignKey('articles.id', ondelete='CASCADE'), nullable=False),
        sa.Column('citation_count', sa.Integer(), nullable=True),
        sa.Column('view_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('last_flushed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()')),
    )
    op.create_unique_constraint('uq_article_metrics_article_id', 'article_metrics', ['article_id'])
    op.create_index('idx_article_metrics_article_id', 'article_metrics', ['article_id'])
    op.create_index(
        'idx_article_metrics_citation_count',
        'article_metrics',
        [sa.text('citation_count DESC NULLS LAST')],
    )
    op.create_index(
        'idx_article_metrics_view_count',
        'article_metrics',
        [sa.text('view_count DESC')],
    )

    # --- weekly_reports ---
    op.create_table(
        'weekly_reports',
        sa.Column('id', UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('topic_id', UUID(as_uuid=True), sa.ForeignKey('topics.id', ondelete='SET NULL'), nullable=True),
        sa.Column('week_start_date', sa.Date(), nullable=False),
        sa.Column('title', sa.Text(), nullable=False),
        sa.Column('summary_text', sa.Text(), nullable=False),
        sa.Column('cover_image_url', sa.Text(), nullable=True),
        sa.Column('article_ids', JSONB, nullable=False, server_default='[]'),
        sa.Column('article_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('status', sa.String(20), nullable=False, server_default='pending'),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()')),
    )
    op.create_unique_constraint('uq_weekly_reports_topic_week', 'weekly_reports', ['topic_id', 'week_start_date'])
    op.create_index('idx_weekly_reports_topic_id', 'weekly_reports', ['topic_id'])
    op.create_index(
        'idx_weekly_reports_week_start',
        'weekly_reports',
        [sa.text('week_start_date DESC')],
    )
    op.create_index('idx_weekly_reports_status', 'weekly_reports', ['status'])

    # --- user_topic_subscriptions ---
    op.create_table(
        'user_topic_subscriptions',
        sa.Column('id', UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('user_id', UUID(as_uuid=True), sa.ForeignKey('auth.users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('topic_id', UUID(as_uuid=True), sa.ForeignKey('topics.id', ondelete='CASCADE'), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()')),
    )
    op.create_unique_constraint('uq_user_topic_subscriptions', 'user_topic_subscriptions', ['user_id', 'topic_id'])
    op.create_index('idx_user_topic_subs_user_id', 'user_topic_subscriptions', ['user_id'])
    op.create_index('idx_user_topic_subs_topic_id', 'user_topic_subscriptions', ['topic_id'])

    # --- user_notification_settings ---
    op.create_table(
        'user_notification_settings',
        sa.Column('id', UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('user_id', UUID(as_uuid=True), sa.ForeignKey('auth.users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('email_enabled', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('telegram_chat_id', sa.String(50), nullable=True),
        sa.Column('telegram_enabled', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('locale', sa.String(10), nullable=False, server_default='en'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()')),
    )
    op.create_unique_constraint('uq_user_notification_settings_user_id', 'user_notification_settings', ['user_id'])
    op.create_index('idx_user_notif_settings_user_id', 'user_notification_settings', ['user_id'])

    # --- user_article_favorites ---
    op.create_table(
        'user_article_favorites',
        sa.Column('id', UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('user_id', UUID(as_uuid=True), sa.ForeignKey('auth.users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('article_id', UUID(as_uuid=True), sa.ForeignKey('articles.id', ondelete='CASCADE'), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()')),
    )
    op.create_unique_constraint('uq_user_article_favorites', 'user_article_favorites', ['user_id', 'article_id'])
    op.create_index('idx_user_article_favs_user_id', 'user_article_favorites', ['user_id'])
    op.create_index('idx_user_article_favs_article_id', 'user_article_favorites', ['article_id'])

    # --- llm_providers: add type column + CheckConstraint ---
    op.add_column('llm_providers', sa.Column('type', sa.String(20), nullable=False, server_default='llm'))
    op.create_check_constraint(
        'ck_llm_provider_type',
        'llm_providers',
        "type IN ('llm', 'embedding', 'multimodal')",
    )


def downgrade():
    # Reverse llm_providers changes
    op.drop_constraint('ck_llm_provider_type', 'llm_providers', type_='check')
    op.drop_column('llm_providers', 'type')

    # Drop user_article_favorites
    op.drop_index('idx_user_article_favs_article_id', table_name='user_article_favorites')
    op.drop_index('idx_user_article_favs_user_id', table_name='user_article_favorites')
    op.drop_constraint('uq_user_article_favorites', 'user_article_favorites', type_='unique')
    op.drop_table('user_article_favorites')

    # Drop user_notification_settings
    op.drop_index('idx_user_notif_settings_user_id', table_name='user_notification_settings')
    op.drop_constraint('uq_user_notification_settings_user_id', 'user_notification_settings', type_='unique')
    op.drop_table('user_notification_settings')

    # Drop user_topic_subscriptions
    op.drop_index('idx_user_topic_subs_topic_id', table_name='user_topic_subscriptions')
    op.drop_index('idx_user_topic_subs_user_id', table_name='user_topic_subscriptions')
    op.drop_constraint('uq_user_topic_subscriptions', 'user_topic_subscriptions', type_='unique')
    op.drop_table('user_topic_subscriptions')

    # Drop weekly_reports
    op.drop_index('idx_weekly_reports_status', table_name='weekly_reports')
    op.drop_index('idx_weekly_reports_week_start', table_name='weekly_reports')
    op.drop_index('idx_weekly_reports_topic_id', table_name='weekly_reports')
    op.drop_constraint('uq_weekly_reports_topic_week', 'weekly_reports', type_='unique')
    op.drop_table('weekly_reports')

    # Drop article_metrics
    op.drop_index('idx_article_metrics_view_count', table_name='article_metrics')
    op.drop_index('idx_article_metrics_citation_count', table_name='article_metrics')
    op.drop_index('idx_article_metrics_article_id', table_name='article_metrics')
    op.drop_constraint('uq_article_metrics_article_id', 'article_metrics', type_='unique')
    op.drop_table('article_metrics')
