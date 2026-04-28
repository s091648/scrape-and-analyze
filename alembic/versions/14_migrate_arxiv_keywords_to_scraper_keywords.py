"""migrate_arxiv_keywords_to_scraper_keywords

Moves ArXiv keywords and categories from selector_config JSONB into the
scraper_keywords table as typed rows ('arxiv_keyword' / 'arxiv_category').
Adds keyword_type column and drops the old unique constraint.

Revision ID: 16_migrate_arxiv_keywords
Revises: 13_add_scraper_keywords
Create Date: 2026-04-26
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "14_migrate_arxiv_keywords"
down_revision: Union[str, Sequence[str], None] = "13_add_scraper_keywords"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. Add keyword_type column (default 'rss' so existing rows are unchanged)
    op.add_column(
        "scraper_keywords",
        sa.Column("keyword_type", sa.String(30), nullable=False, server_default="rss"),
    )

    # 2. Drop old unique constraint (topic_id, keyword) → replace with (topic_id, keyword_type, keyword)
    op.drop_constraint("uq_scraper_keyword_topic_keyword", "scraper_keywords", type_="unique")
    op.create_unique_constraint(
        "uq_scraper_keyword_topic_type_keyword",
        "scraper_keywords",
        ["topic_id", "keyword_type", "keyword"],
    )

    # 3. Migrate ArXiv keywords from selector_config into scraper_keywords
    op.execute("""
        INSERT INTO scraper_keywords (id, topic_id, keyword_type, keyword, created_at)
        SELECT
            gen_random_uuid(),
            ss.topic_id,
            'arxiv_keyword',
            kw.value,
            NOW()
        FROM scraper_settings ss,
             jsonb_array_elements_text(ss.selector_config->'keywords') AS kw(value)
        WHERE ss.source_type = 'arxiv'
          AND ss.selector_config ? 'keywords'
          AND jsonb_array_length(ss.selector_config->'keywords') > 0
        ON CONFLICT (topic_id, keyword_type, keyword) DO NOTHING
    """)

    # 4. Migrate ArXiv categories from selector_config into scraper_keywords
    op.execute("""
        INSERT INTO scraper_keywords (id, topic_id, keyword_type, keyword, created_at)
        SELECT
            gen_random_uuid(),
            ss.topic_id,
            'arxiv_category',
            cat.value,
            NOW()
        FROM scraper_settings ss,
             jsonb_array_elements_text(ss.selector_config->'categories') AS cat(value)
        WHERE ss.source_type = 'arxiv'
          AND ss.selector_config ? 'categories'
          AND jsonb_array_length(ss.selector_config->'categories') > 0
        ON CONFLICT (topic_id, keyword_type, keyword) DO NOTHING
    """)

    # 5. Strip keywords and categories from selector_config JSONB
    op.execute("""
        UPDATE scraper_settings
        SET selector_config = selector_config - 'keywords' - 'categories'
        WHERE source_type = 'arxiv'
          AND selector_config IS NOT NULL
    """)

    # 6. Column comment
    op.execute("""
        COMMENT ON COLUMN scraper_keywords.keyword_type IS
        'Discriminates the keyword variant:
           rss            – regex pattern for RSS entry filtering
           arxiv_keyword  – arXiv API query string (e.g. ti:"digital twin")
           arxiv_category – arXiv subject category code (e.g. cs.GR)'
    """)


def downgrade() -> None:
    # Reverse migration: move arxiv keywords/categories back to selector_config
    op.execute("""
        UPDATE scraper_settings ss
        SET selector_config = COALESCE(ss.selector_config, '{}'::jsonb)
            || jsonb_build_object(
                'keywords',
                COALESCE(
                    (SELECT jsonb_agg(sk.keyword ORDER BY sk.created_at)
                     FROM scraper_keywords sk
                     WHERE sk.topic_id = ss.topic_id AND sk.keyword_type = 'arxiv_keyword'),
                    '[]'::jsonb
                ),
                'categories',
                COALESCE(
                    (SELECT jsonb_agg(sk.keyword ORDER BY sk.created_at)
                     FROM scraper_keywords sk
                     WHERE sk.topic_id = ss.topic_id AND sk.keyword_type = 'arxiv_category'),
                    '[]'::jsonb
                )
            )
        WHERE ss.source_type = 'arxiv'
    """)

    # Remove arxiv_keyword and arxiv_category rows from scraper_keywords
    op.execute("""
        DELETE FROM scraper_keywords
        WHERE keyword_type IN ('arxiv_keyword', 'arxiv_category')
    """)

    # Restore old unique constraint
    op.drop_constraint("uq_scraper_keyword_topic_type_keyword", "scraper_keywords", type_="unique")
    op.create_unique_constraint(
        "uq_scraper_keyword_topic_keyword",
        "scraper_keywords",
        ["topic_id", "keyword"],
    )

    # Drop keyword_type column
    op.drop_column("scraper_keywords", "keyword_type")
