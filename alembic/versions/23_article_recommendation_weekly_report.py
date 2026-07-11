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
    # Usage-only signal (view_count), owned by the backend's Redis-flush path.
    # citation_count intentionally NOT here — see metric_definitions / article_metric_values
    # below (2026-07-12 revision: extensible metric catalog, research.md §9b).
    op.create_table(
        'article_metrics',
        sa.Column('id', UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('article_id', UUID(as_uuid=True), sa.ForeignKey('articles.id', ondelete='CASCADE'), nullable=False),
        sa.Column('view_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('last_flushed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()')),
    )
    op.create_unique_constraint('uq_article_metrics_article_id', 'article_metrics', ['article_id'])
    op.create_index('idx_article_metrics_article_id', 'article_metrics', ['article_id'])
    op.create_index(
        'idx_article_metrics_view_count',
        'article_metrics',
        [sa.text('view_count DESC')],
    )

    # --- metric_definitions ---
    # Maintainer-curated catalog of recommendation-signal metrics and how to obtain
    # each one. Changed only via migration + code review — never via a runtime/admin
    # API (FR-022). See research.md §9b-§9d.
    op.create_table(
        'metric_definitions',
        sa.Column('id', UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('metric_key', sa.String(50), nullable=False),
        sa.Column('provider_name', sa.String(50), nullable=False),
        sa.Column('priority', sa.Integer(), nullable=False),
        sa.Column('extractor_type', sa.String(20), nullable=False),
        sa.Column('extractor_spec', JSONB, nullable=False),
        sa.Column('enabled', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('label_i18n_key', sa.String(100), nullable=False),
        sa.Column('format_hint', sa.String(20), nullable=True),
        sa.Column('unit', sa.String(20), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()')),
    )
    op.create_unique_constraint(
        'uq_metric_definitions_metric_key_provider_name',
        'metric_definitions',
        ['metric_key', 'provider_name'],
    )
    op.create_check_constraint(
        'ck_metric_definitions_extractor_type',
        'metric_definitions',
        "extractor_type IN ('json_path', 'code')",
    )
    op.create_index(
        'idx_metric_definitions_metric_key',
        'metric_definitions',
        ['metric_key'],
        postgresql_where=sa.text('enabled = true'),
    )
    op.execute(
        """
        INSERT INTO metric_definitions
            (metric_key, provider_name, priority, extractor_type, extractor_spec, label_i18n_key, format_hint)
        VALUES
            ('citation_count', 'openalex', 1, 'json_path', '{"path": "cited_by_count"}', 'metrics.citation_count', 'integer'),
            ('citation_count', 'semantic_scholar', 2, 'json_path', '{"path": "citationCount"}', 'metrics.citation_count', 'integer')
        """
    )

    # --- article_metric_values ---
    # Normalized value storage — one row per (article, metric). Replaces the old
    # article_metrics.citation_count column. Written by ProcessScrapedArticleUseCase
    # (opportunistic seed) and by refresh_metrics.py (authoritative recurring refresh).
    op.create_table(
        'article_metric_values',
        sa.Column('id', UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('article_id', UUID(as_uuid=True), sa.ForeignKey('articles.id', ondelete='CASCADE'), nullable=False),
        sa.Column('metric_key', sa.String(50), nullable=False),
        sa.Column('value', sa.Numeric(), nullable=True),
        sa.Column('last_flushed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()')),
    )
    op.create_unique_constraint(
        'uq_article_metric_values_article_id_metric_key',
        'article_metric_values',
        ['article_id', 'metric_key'],
    )
    op.create_index('idx_article_metric_values_article_id', 'article_metric_values', ['article_id'])
    op.create_index(
        'idx_article_metric_values_metric_key_value',
        'article_metric_values',
        [sa.text('metric_key'), sa.text('value DESC NULLS LAST')],
    )
    op.create_index(
        'idx_article_metric_values_stale',
        'article_metric_values',
        ['last_flushed_at'],
        postgresql_where=sa.text('last_flushed_at IS NOT NULL'),
    )

    # --- articles.metadata expression indexes (DOI / arxiv_id lookup for refresh_metrics.py) ---
    # No new columns on `articles` — keeps the hot-path table lean (research.md §9e).
    op.create_index(
        'idx_articles_metadata_doi',
        'articles',
        [sa.text("(metadata->>'doi')")],
        postgresql_where=sa.text("metadata->>'doi' IS NOT NULL"),
    )
    op.create_index(
        'idx_articles_metadata_arxiv_id',
        'articles',
        [sa.text("(metadata->>'arxiv_id')")],
        postgresql_where=sa.text("metadata->>'arxiv_id' IS NOT NULL"),
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
        sa.Column('article_ids', JSONB, nullable=False, server_default=sa.text("'[]'")),
        sa.Column('article_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('status', sa.String(20), nullable=False, server_default=sa.text("'pending'")),
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

    # --- weekly_reports_translation ---
    op.create_table(
        'weekly_reports_translation',
        sa.Column('id', UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('weekly_report_id', UUID(as_uuid=True), sa.ForeignKey('weekly_reports.id', ondelete='CASCADE'), nullable=False),
        sa.Column('language', sa.String(10), nullable=False),
        sa.Column('title', sa.Text(), nullable=False),
        sa.Column('summary_text', sa.Text(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()')),
    )
    op.create_unique_constraint(
        'uq_weekly_reports_translation_report_language',
        'weekly_reports_translation',
        ['weekly_report_id', 'language'],
    )
    op.create_index('idx_weekly_reports_translation_report_id', 'weekly_reports_translation', ['weekly_report_id'])
    op.create_index('idx_weekly_reports_translation_language', 'weekly_reports_translation', ['language'])

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
        sa.Column('locale', sa.String(10), nullable=False, server_default=sa.text("'en'")),
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

    # --- llm_providers: widen type CheckConstraint to include 'multimodal' ---
    # NOTE: the `type` column itself was already added in migration 17
    # (17_add_vector_failed_task_and_auto_tag.py) — do not re-add it here.
    op.create_check_constraint(
        'ck_llm_provider_type',
        'llm_providers',
        "type IN ('llm', 'embedding', 'multimodal')",
    )


def downgrade():
    # Reverse llm_providers changes (column itself belongs to migration 17, not touched here)
    op.drop_constraint('ck_llm_provider_type', 'llm_providers', type_='check')

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

    # Drop weekly_reports_translation (before weekly_reports — FK dependency)
    op.drop_index('idx_weekly_reports_translation_language', table_name='weekly_reports_translation')
    op.drop_index('idx_weekly_reports_translation_report_id', table_name='weekly_reports_translation')
    op.drop_constraint('uq_weekly_reports_translation_report_language', 'weekly_reports_translation', type_='unique')
    op.drop_table('weekly_reports_translation')

    # Drop weekly_reports
    op.drop_index('idx_weekly_reports_status', table_name='weekly_reports')
    op.drop_index('idx_weekly_reports_week_start', table_name='weekly_reports')
    op.drop_index('idx_weekly_reports_topic_id', table_name='weekly_reports')
    op.drop_constraint('uq_weekly_reports_topic_week', 'weekly_reports', type_='unique')
    op.drop_table('weekly_reports')

    # Drop articles.metadata expression indexes
    op.drop_index('idx_articles_metadata_arxiv_id', table_name='articles')
    op.drop_index('idx_articles_metadata_doi', table_name='articles')

    # Drop article_metric_values
    op.drop_index('idx_article_metric_values_stale', table_name='article_metric_values')
    op.drop_index('idx_article_metric_values_metric_key_value', table_name='article_metric_values')
    op.drop_index('idx_article_metric_values_article_id', table_name='article_metric_values')
    op.drop_constraint('uq_article_metric_values_article_id_metric_key', 'article_metric_values', type_='unique')
    op.drop_table('article_metric_values')

    # Drop metric_definitions
    op.drop_index('idx_metric_definitions_metric_key', table_name='metric_definitions')
    op.drop_constraint('ck_metric_definitions_extractor_type', 'metric_definitions', type_='check')
    op.drop_constraint('uq_metric_definitions_metric_key_provider_name', 'metric_definitions', type_='unique')
    op.drop_table('metric_definitions')

    # Drop article_metrics
    op.drop_index('idx_article_metrics_view_count', table_name='article_metrics')
    op.drop_index('idx_article_metrics_article_id', table_name='article_metrics')
    op.drop_constraint('uq_article_metrics_article_id', 'article_metrics', type_='unique')
    op.drop_table('article_metrics')
