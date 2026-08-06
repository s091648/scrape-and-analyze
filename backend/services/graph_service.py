from datetime import datetime
from typing import List, Optional

from sqlalchemy.orm import Session


def load_group_defs(db: Session, lang: str = "en") -> dict:
    from models.tag_group import TagGroupDefinition
    from models.tag_group_translation import TagGroupDefinitionsTranslation

    rows = db.query(TagGroupDefinition).order_by(TagGroupDefinition.sort_order).all()

    group_trans_map: dict = {}
    if lang != "en":
        group_ids = [r.id for r in rows]
        if group_ids:
            translations = db.query(TagGroupDefinitionsTranslation).filter(
                TagGroupDefinitionsTranslation.tag_group_definition_id.in_(group_ids),
                TagGroupDefinitionsTranslation.language == lang,
            ).all()
            group_trans_map = {gt.tag_group_definition_id: gt for gt in translations}

    return {
        r.id: {
            'name': r.name,
            'display_name': group_trans_map[r.id].display_name if r.id in group_trans_map else r.display_name,
            'description': group_trans_map[r.id].description if r.id in group_trans_map else r.description,
            'color_hex': r.color_hex or '#6b7280',
        }
        for r in rows
    }


def load_group_def(db: Session, group_name: str):
    from models.tag_group import TagGroupDefinition
    return db.query(TagGroupDefinition).filter_by(name=group_name).first()


def query_analyses(
    db: Session,
    topic_id=None,
    published_after: Optional[datetime] = None,
    published_before: Optional[datetime] = None,
    scraped_after: Optional[datetime] = None,
    scraped_before: Optional[datetime] = None,
    aggregators: Optional[List[str]] = None,
    original_sources: Optional[List[str]] = None,
    tags: Optional[List[str]] = None,
) -> list:
    from models.analysis import Analysis
    from models.article import Article
    query = (
        db.query(Analysis)
        .join(Article, Article.id == Analysis.article_id)
        .filter(Article.merged_into_id.is_(None))
    )
    if topic_id:
        query = query.filter(Article.topic_id == topic_id)
    if published_after:
        query = query.filter(Article.published_at >= published_after)
    if published_before:
        query = query.filter(Article.published_at <= published_before)
    if scraped_after:
        query = query.filter(Article.scraped_at >= scraped_after)
    if scraped_before:
        query = query.filter(Article.scraped_at <= scraped_before)
    if aggregators:
        query = query.filter(Article.source.in_(aggregators))
    if original_sources:
        query = query.filter(Article.original_source.in_(original_sources))
    if tags:
        from models.tag import Tag, article_tags as at
        query = (
            query
            .join(at, at.c.article_id == Article.id)
            .join(Tag, Tag.id == at.c.tag_id)
            .filter(Tag.name.in_(tags))
            .distinct()
        )
    return query.all()


def query_group_articles(
    db: Session,
    group_name: str,
    topic_id=None,
    published_after: Optional[datetime] = None,
    published_before: Optional[datetime] = None,
    scraped_after: Optional[datetime] = None,
    scraped_before: Optional[datetime] = None,
    aggregators: Optional[List[str]] = None,
    original_sources: Optional[List[str]] = None,
    tags: Optional[List[str]] = None,
) -> list:
    from models.analysis import Analysis
    from models.article import Article
    from models.tag import Tag, article_tags as at
    from models.tag_group import TagGroupDefinition
    query = (
        db.query(Analysis)
        .join(Article, Article.id == Analysis.article_id)
        .join(at, at.c.article_id == Article.id)
        .join(Tag, Tag.id == at.c.tag_id)
        .join(TagGroupDefinition, TagGroupDefinition.id == Tag.tag_group_id)
        .filter(TagGroupDefinition.name == group_name)
        .filter(Article.merged_into_id.is_(None))
        .distinct()
    )
    if topic_id:
        query = query.filter(Article.topic_id == topic_id)
    if published_after:
        query = query.filter(Article.published_at >= published_after)
    if published_before:
        query = query.filter(Article.published_at <= published_before)
    if scraped_after:
        query = query.filter(Article.scraped_at >= scraped_after)
    if scraped_before:
        query = query.filter(Article.scraped_at <= scraped_before)
    if aggregators:
        query = query.filter(Article.source.in_(aggregators))
    if original_sources:
        query = query.filter(Article.original_source.in_(original_sources))
    if tags:
        from models.tag import Tag as T2, article_tags as at2
        query = (
            query
            .join(at2, at2.c.article_id == Article.id)
            .join(T2, T2.id == at2.c.tag_id)
            .filter(T2.name.in_(tags))
        )
    return query.all()


def build_graph(analyses: list, group_defs: dict) -> dict:
    nodes = []
    edges = []
    group_node_ids: set = set()
    article_ids: set = set()
    group_article_counts: dict = {}

    for analysis in analyses:
        article_id = str(analysis.article_id)
        if article_id not in article_ids:
            article_ids.add(article_id)
            nodes.append({
                'id': article_id,
                'type': 'article',
                'label': analysis.article.title if analysis.article else '',
                'articleId': article_id,
            })

        seen_groups: set = set()
        for tag in (analysis.article.tags if analysis.article else []):
            gdef = group_defs.get(tag.tag_group_id)
            if not gdef:
                continue
            group_name = gdef['name']
            if group_name in seen_groups:
                continue
            seen_groups.add(group_name)
            group_node_id = f'group:{group_name}'
            if group_node_id not in group_node_ids:
                group_node_ids.add(group_node_id)
                nodes.append({
                    'id': group_node_id,
                    'type': 'group',
                    'label': gdef.get('display_name', group_name),
                    'color': gdef.get('color_hex', '#6b7280'),
                    'groupName': group_name,
                    'articleCount': 0,
                })
                group_article_counts[group_node_id] = 0
            group_article_counts[group_node_id] += 1
            edges.append({'source': group_node_id, 'target': article_id})

    for node in nodes:
        if node['type'] == 'group':
            node['articleCount'] = group_article_counts.get(node['id'], 0)

    return {'nodes': nodes, 'edges': edges}
