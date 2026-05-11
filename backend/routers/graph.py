# backend/routers/graph.py
import time
from datetime import datetime, timedelta, timezone
from typing import Any, Optional
from uuid import UUID
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from backend.database import get_db

router = APIRouter()

# In-process cache: {(days, topic_id, lang): (result, expires_at)}
_cache: dict[tuple, tuple[Any, float]] = {}
CACHE_TTL_SECONDS = 300  # 5 minutes


def load_group_defs(db: Session, lang: str = "en") -> dict:
    """Load tag group definitions as a name→metadata dict, with optional translation."""
    from models.tag_group import TagGroupDefinition
    from models.tag_group_translation import TagGroupDefinitionTranslation

    rows = db.query(TagGroupDefinition).order_by(TagGroupDefinition.sort_order).all()

    group_trans_map = {}
    if lang != "en":
        group_ids = [r.id for r in rows]
        if group_ids:
            translations = db.query(TagGroupDefinitionTranslation).filter(
                TagGroupDefinitionTranslation.tag_group_definition_id.in_(group_ids),
                TagGroupDefinitionTranslation.language == lang,
            ).all()
            group_trans_map = {gt.tag_group_definition_id: gt for gt in translations}

    return {
        r.name: {
            'display_name': group_trans_map.get(r.id, r).display_name if r.id in group_trans_map else r.display_name,
            'description': group_trans_map.get(r.id, r).description if r.id in group_trans_map else r.description,
            'color_hex': r.color_hex or '#6b7280',
        }
        for r in rows
    }


def load_group_def(db: Session, group_name: str):
    """Load a single tag group definition by name."""
    from models.tag_group import TagGroupDefinition
    return db.query(TagGroupDefinition).filter_by(name=group_name).first()


def query_analyses(db: Session, days: int, topic_id=None) -> list:
    from models.analysis import Analysis
    from models.article import Article
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    query = db.query(Analysis).join(Article, Article.id == Analysis.article_id).filter(
        Analysis.analyzed_at >= cutoff
    )
    if topic_id:
        query = query.filter(Article.topic_id == topic_id)
    return query.all()


def query_group_articles(db: Session, group_name: str, topic_id=None) -> list:
    """Return all analyses whose article has at least one tag in the given group."""
    from models.analysis import Analysis
    from models.article import Article
    from models.tag import Tag, article_tags as at
    query = (
        db.query(Analysis)
        .join(Article, Article.id == Analysis.article_id)
        .join(at, at.c.article_id == Article.id)
        .join(Tag, Tag.id == at.c.tag_id)
        .filter(Tag.tag_group_name == group_name)
        .distinct()
    )
    if topic_id:
        query = query.filter(Article.topic_id == topic_id)
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
def get_graph(days: int = Query(30, ge=1, le=365),
              topic_id: Optional[UUID] = Query(default=None),
              lang: str = Query(default="en"),
              db: Session = Depends(get_db)):
    cache_key = (days, str(topic_id), lang)
    now = time.time()
    if cache_key in _cache:
        result, expires_at = _cache[cache_key]
        if now < expires_at:
            return result

    group_defs = load_group_defs(db, lang=lang)
    analyses = query_analyses(db, days, topic_id=topic_id)
    result = build_graph(analyses, group_defs)
    _cache[cache_key] = (result, now + CACHE_TTL_SECONDS)
    return result


@router.get('/analyses/graph/group/{group_name}')
def get_group_articles(group_name: str,
                       topic_id: Optional[UUID] = Query(default=None),
                       lang: str = Query(default="en"),
                       db: Session = Depends(get_db)):
    from models.analyses_translation import AnalysesTranslation
    from models.tag_translation import TagTranslation
    from models.tag_group_translation import TagGroupDefinitionTranslation

    group_def = load_group_def(db, group_name)

    # Translate group display name and description
    display_name = group_def.display_name if group_def else group_name
    group_description = group_def.description if group_def else None
    if lang != "en" and group_def:
        group_trans = db.query(TagGroupDefinitionTranslation).filter(
            TagGroupDefinitionTranslation.tag_group_definition_id == group_def.id,
            TagGroupDefinitionTranslation.language == lang,
        ).first()
        if group_trans:
            display_name = group_trans.display_name
            group_description = group_trans.description

    analyses = query_group_articles(db, group_name, topic_id=topic_id)

    # Batch-load analysis translations (requested language + English fallback)
    analysis_ids = [a.id for a in analyses]
    trans_map = {}
    en_map = {}
    if analysis_ids:
        languages_to_load = {lang, "en"} if lang != "en" else {"en"}
        translations = db.query(AnalysesTranslation).filter(
            AnalysesTranslation.analysis_id.in_(analysis_ids),
            AnalysesTranslation.language.in_(languages_to_load),
        ).all()
        for t in translations:
            if t.language == lang:
                trans_map[t.analysis_id] = t
            if t.language == "en":
                en_map[t.analysis_id] = t

    # Batch-load tag translations for this group
    tag_trans_map = {}
    if lang != "en":
        from models.tag import Tag
        tag_ids = set()
        for analysis in analyses:
            if analysis.article:
                for tag in analysis.article.tags:
                    if tag.tag_group_name == group_name:
                        tag_ids.add(tag.id)
        if tag_ids:
            tag_translations = db.query(TagTranslation).filter(
                TagTranslation.tag_id.in_(tag_ids),
                TagTranslation.language == lang,
            ).all()
            tag_trans_map = {tt.tag_id: tt.name for tt in tag_translations}

    result = []
    for analysis in analyses:
        article = analysis.article
        if not article:
            continue
        group_tags = [
            tag_trans_map.get(t.id, t.name) if lang != "en" else t.name
            for t in (article.tags if article else [])
            if t.tag_group_name == group_name
        ]

        # Use translated content if available, fallback to English
        trans = trans_map.get(analysis.id)
        en_trans = en_map.get(analysis.id)
        if trans:
            pain_points = trans.pain_points
            insights = trans.insights
            innovations = trans.innovations
        elif en_trans:
            pain_points = en_trans.pain_points
            insights = en_trans.insights
            innovations = en_trans.innovations

        result.append({
            'groupName': group_name,
            'displayName': display_name,
            'groupDescription': group_description,
            'tags': group_tags,
            'articleId': str(analysis.article_id),
            'title': article.title,
            'source': article.source,
            'url': article.url,
            'published_at': article.published_at.isoformat() if article.published_at else None,
            'excerpt': (article.content or '')[:200],
            'pain_points': pain_points,
            'insights': insights,
            'innovations': innovations,
        })
    return result
