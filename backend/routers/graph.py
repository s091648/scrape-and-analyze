# backend/routers/graph.py
import time
from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from typing import Any

from backend.database import get_db

router = APIRouter()

# In-process cache: {days: (result, expires_at)}
_cache: dict[int, tuple[Any, float]] = {}
CACHE_TTL_SECONDS = 300  # 5 minutes


def load_group_defs(db: Session) -> dict:
    """Load tag group definitions as a name→metadata dict."""
    from models.tag_group import TagGroupDefinition
    rows = db.query(TagGroupDefinition).order_by(TagGroupDefinition.sort_order).all()
    return {
        r.name: {'display_name': r.display_name, 'color_hex': r.color_hex or '#6b7280'}
        for r in rows
    }


def load_group_def(db: Session, group_name: str):
    """Load a single tag group definition by name."""
    from models.tag_group import TagGroupDefinition
    return db.query(TagGroupDefinition).filter_by(name=group_name).first()


def query_analyses(db: Session, days: int) -> list:
    from models.analysis import Analysis
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    return db.query(Analysis).filter(Analysis.analyzed_at >= cutoff).all()


def query_group_articles(db: Session, group_name: str) -> list:
    """Return all analyses whose article has at least one tag in the given group."""
    from models.analysis import Analysis
    from models.article import Article
    from models.tag import Tag, article_tags as at
    return (
        db.query(Analysis)
        .join(Article, Article.id == Analysis.article_id)
        .join(at, at.c.article_id == Article.id)
        .join(Tag, Tag.id == at.c.tag_id)
        .filter(Tag.tag_group_name == group_name)
        .distinct()
        .all()
    )


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
            group_name = tag.tag_group_name
            if not group_name or group_name in seen_groups:
                continue
            seen_groups.add(group_name)
            group_node_id = f'group:{group_name}'
            if group_node_id not in group_node_ids:
                group_node_ids.add(group_node_id)
                gdef = group_defs.get(group_name, {})
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


@router.get('/analyses/graph')
def get_graph(days: int = Query(30, ge=1, le=365), db: Session = Depends(get_db)):
    now = time.time()
    if days in _cache:
        result, expires_at = _cache[days]
        if now < expires_at:
            return result

    group_defs = load_group_defs(db)
    analyses = query_analyses(db, days)
    result = build_graph(analyses, group_defs)
    _cache[days] = (result, now + CACHE_TTL_SECONDS)
    return result


@router.get('/analyses/graph/group/{group_name}')
def get_group_articles(group_name: str, db: Session = Depends(get_db)):
    group_def = load_group_def(db, group_name)
    display_name = group_def.display_name if group_def else group_name

    analyses = query_group_articles(db, group_name)
    result = []
    for analysis in analyses:
        article = analysis.article
        if not article:
            continue
        group_tags = [
            t.name for t in (analysis.article.tags if analysis.article else [])
            if t.tag_group_name == group_name
        ]
        result.append({
            'groupName': group_name,
            'displayName': display_name,
            'tags': group_tags,
            'articleId': str(analysis.article_id),
            'title': article.title,
            'source': article.source,
            'url': article.url,
            'published_at': article.published_at.isoformat() if article.published_at else None,
            'excerpt': (article.content or '')[:200],
            'pain_points': analysis.pain_points,
            'insights': analysis.insights,
            'innovations': analysis.innovations,
        })
    return result
