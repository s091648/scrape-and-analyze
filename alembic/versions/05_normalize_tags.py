"""normalize_tags

Revision ID: 05_normalize_tags
Revises: b3f1a9d2c8e0
Create Date: 2026-03-03
"""
from typing import Sequence, Union
import uuid
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = '05_normalize_tags'
down_revision: Union[str, Sequence[str], None] = 'b3f1a9d2c8e0'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. Create tags table
    op.create_table(
        'tags',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('name', sa.Text(), nullable=False),
        sa.Column('tag_group_name', sa.String(100), nullable=False),
        sa.UniqueConstraint('name', 'tag_group_name', name='uq_tag_name_group'),
        sa.ForeignKeyConstraint(
            ['tag_group_name'], ['tag_group_definitions.name'],
            name='fk_tags_group'
        ),
    )
    op.create_index('idx_tags_group', 'tags', ['tag_group_name'])

    # 2. Create article_tags junction table
    op.create_table(
        'article_tags',
        sa.Column('article_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('tag_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.PrimaryKeyConstraint('article_id', 'tag_id', name='pk_article_tags'),
        sa.ForeignKeyConstraint(['article_id'], ['articles.id'], name='fk_at_article'),
        sa.ForeignKeyConstraint(['tag_id'], ['tags.id'], name='fk_at_tag'),
    )

    # 3. Migrate existing data from analyses.tag_groups JSONB
    conn = op.get_bind()
    rows = conn.execute(sa.text("""
        SELECT
            a.article_id,
            tg.value->>'group'                         AS group_name,
            tag_elem.value                             AS tag_name
        FROM analyses a
        CROSS JOIN jsonb_array_elements(a.tag_groups)          AS tg(value)
        CROSS JOIN jsonb_array_elements_text(tg.value->'tags') AS tag_elem(value)
        WHERE a.tag_groups IS NOT NULL
          AND jsonb_array_length(a.tag_groups) > 0
    """)).fetchall()

    tag_cache: dict = {}  # (name, group_name) -> uuid str
    for article_id, group_name, tag_name in rows:
        if not tag_name or not group_name:
            continue
        key = (tag_name, group_name)
        if key not in tag_cache:
            new_id = str(uuid.uuid4())
            conn.execute(sa.text("""
                INSERT INTO tags (id, name, tag_group_name)
                VALUES (:id, :name, :group_name)
                ON CONFLICT (name, tag_group_name) DO NOTHING
            """), {'id': new_id, 'name': tag_name, 'group_name': group_name})
            row = conn.execute(sa.text("""
                SELECT id FROM tags WHERE name = :name AND tag_group_name = :group_name
            """), {'name': tag_name, 'group_name': group_name}).first()
            tag_cache[key] = str(row[0])

        conn.execute(sa.text("""
            INSERT INTO article_tags (article_id, tag_id)
            VALUES (:article_id, :tag_id)
            ON CONFLICT DO NOTHING
        """), {'article_id': str(article_id), 'tag_id': tag_cache[key]})

    # 4. Drop old columns
    op.drop_column('analyses', 'tags')
    op.drop_column('analyses', 'tag_groups')


def downgrade() -> None:
    op.add_column('analyses', sa.Column('tag_groups', postgresql.JSONB(), nullable=True))
    op.add_column('analyses', sa.Column('tags', postgresql.ARRAY(sa.Text()), nullable=True))
    op.drop_table('article_tags')
    op.drop_index('idx_tags_group', table_name='tags')
    op.drop_table('tags')
