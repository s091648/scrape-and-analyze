"""add_topic_system

Revision ID: 12_add_topic_system
Revises: 11_add_arxiv_metadata
Create Date: 2026-04-09
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB

revision: str = "12_add_topic_system"
down_revision: Union[str, Sequence[str], None] = "11_add_arxiv_metadata"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. Create topics table
    op.create_table(
        "topics",
        sa.Column("id", UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("name", sa.String(100), nullable=False, unique=True),
        sa.Column("display_name", sa.String(200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("color_hex", sa.String(7), nullable=True),
        sa.Column("prompt_override", sa.Text(), nullable=True),
        sa.Column("sort_order", sa.Integer(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False,
                  server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.text("NOW()")),
    )
    op.create_index("idx_topics_name", "topics", ["name"])

    # 2. Seed default topic for all existing data
    op.execute("""
        INSERT INTO topics (id, name, display_name, description, color_hex, sort_order, is_active)
        VALUES (
            '2058f94a-94cd-4d9e-9ae0-082281b5d106',
            'digital-twins',
            'Digital Twins',
            'Digital twin and cyber-physical systems research',
            '#3B82F6',
            1,
            true
        )
    """)

    # 3. Add topic_id to scraper_settings (nullable first for backfill)
    op.add_column('scraper_settings',
        sa.Column('topic_id', UUID(as_uuid=True), nullable=True))
    op.execute("""
        UPDATE scraper_settings
        SET topic_id = (SELECT id FROM topics WHERE name = 'digital-twins')
    """)
    # Backfill arxiv keywords into selector_config before dropping the table
    op.execute("""
        UPDATE scraper_settings
        SET selector_config = COALESCE(selector_config, '{}'::jsonb) ||
            jsonb_build_object(
                'keywords',
                (SELECT jsonb_agg(keyword) FROM arxiv_keywords)
            )
        WHERE source_type = 'arxiv'
    """)
    op.create_foreign_key(
        'fk_scraper_settings_topic_id', 'scraper_settings',
        'topics', ['topic_id'], ['id']
    )
    op.alter_column('scraper_settings', 'topic_id', nullable=False)

    # 4. Add topic_id to articles (nullable — old rows stay null)
    op.add_column('articles',
        sa.Column('topic_id', UUID(as_uuid=True), nullable=True))
    op.execute("""
        UPDATE articles
        SET topic_id = (SELECT id FROM topics WHERE name = 'digital-twins')
    """)
    op.create_foreign_key(
        'fk_articles_topic_id', 'articles',
        'topics', ['topic_id'], ['id']
    )
    op.create_index('idx_articles_topic_id', 'articles', ['topic_id'])

    # 5. Add topic_id to tag_group_definitions
    op.add_column('tag_group_definitions',
        sa.Column('topic_id', UUID(as_uuid=True), nullable=True))
    op.execute("""
        UPDATE tag_group_definitions
        SET topic_id = (SELECT id FROM topics WHERE name = 'digital-twins')
    """)
    op.create_foreign_key(
        'fk_tag_group_definitions_topic_id', 'tag_group_definitions',
        'topics', ['topic_id'], ['id']
    )
    op.alter_column('tag_group_definitions', 'topic_id', nullable=False)
    # Drop old single-column unique, add composite unique
    # tags.tag_group_name FK depends on this index — drop it first
    op.drop_constraint('fk_tags_group', 'tags', type_='foreignkey')
    op.drop_constraint('tag_group_definitions_name_key', 'tag_group_definitions',
                       type_='unique')
    op.create_unique_constraint(
        'uq_tag_group_name_topic', 'tag_group_definitions', ['name', 'topic_id']
    )
    # tag_group_name is now a plain denormalized column (no FK; name is per-topic)

    # 6. Drop arxiv_keywords table (data already backfilled into selector_config)
    op.drop_table("arxiv_keywords")


def downgrade() -> None:
    # Recreate arxiv_keywords
    op.create_table(
        "arxiv_keywords",
        sa.Column("id", UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("keyword", sa.String(500), nullable=False, unique=True),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.text("NOW()")),
    )
    # Restore from first arxiv scraper's selector_config
    op.execute("""
        INSERT INTO arxiv_keywords (keyword)
        SELECT jsonb_array_elements_text(selector_config->'keywords')
        FROM scraper_settings WHERE source_type = 'arxiv' LIMIT 1
        ON CONFLICT DO NOTHING
    """)

    op.drop_constraint('uq_tag_group_name_topic', 'tag_group_definitions', type_='unique')
    op.create_unique_constraint('tag_group_definitions_name_key', 'tag_group_definitions', ['name'])
    op.create_foreign_key('fk_tags_group', 'tags', 'tag_group_definitions',
                          ['tag_group_name'], ['name'])
    op.drop_constraint('fk_tag_group_definitions_topic_id', 'tag_group_definitions', type_='foreignkey')
    op.drop_column('tag_group_definitions', 'topic_id')

    op.drop_index('idx_articles_topic_id', table_name='articles')
    op.drop_constraint('fk_articles_topic_id', 'articles', type_='foreignkey')
    op.drop_column('articles', 'topic_id')

    op.drop_constraint('fk_scraper_settings_topic_id', 'scraper_settings', type_='foreignkey')
    op.drop_column('scraper_settings', 'topic_id')

    op.drop_index("idx_topics_name", table_name="topics")
    op.drop_table("topics")
