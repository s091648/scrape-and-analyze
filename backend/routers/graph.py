import time
from datetime import datetime
from typing import Any, List, Optional
from uuid import UUID
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.services.graph_service import (
    load_group_defs,
    load_group_def,
    query_analyses,
    query_group_articles,
    build_graph,
)

router = APIRouter()

_cache: dict[tuple, tuple[Any, float]] = {}
CACHE_TTL_SECONDS = 300


@router.get('/analyses/graph')
def get_graph(
    topic_id: Optional[UUID] = Query(default=None),
    lang: str = Query(default="en"),
    published_after: Optional[datetime] = Query(default=None),
    published_before: Optional[datetime] = Query(default=None),
    scraped_after: Optional[datetime] = Query(default=None),
    scraped_before: Optional[datetime] = Query(default=None),
    aggregator: Optional[List[str]] = Query(default=None),
    original_source: Optional[List[str]] = Query(default=None),
    tag: Optional[List[str]] = Query(default=None),
    db: Session = Depends(get_db),
):
    cache_key = (
        str(topic_id), lang,
        str(published_after), str(published_before),
        str(scraped_after), str(scraped_before),
        tuple(sorted(aggregator or [])),
        tuple(sorted(original_source or [])),
        tuple(sorted(tag or [])),
    )
    now = time.time()
    if cache_key in _cache:
        result, expires_at = _cache[cache_key]
        if now < expires_at:
            return result

    group_defs = load_group_defs(db, lang=lang)
    analyses = query_analyses(
        db,
        topic_id=topic_id,
        published_after=published_after,
        published_before=published_before,
        scraped_after=scraped_after,
        scraped_before=scraped_before,
        aggregators=aggregator or None,
        original_sources=original_source or None,
        tags=tag or None,
    )
    result = build_graph(analyses, group_defs)
    _cache[cache_key] = (result, now + CACHE_TTL_SECONDS)
    return result


@router.get('/analyses/graph/group/{group_name}')
def get_group_articles(
    group_name: str,
    topic_id: Optional[UUID] = Query(default=None),
    lang: str = Query(default="en"),
    published_after: Optional[datetime] = Query(default=None),
    published_before: Optional[datetime] = Query(default=None),
    scraped_after: Optional[datetime] = Query(default=None),
    scraped_before: Optional[datetime] = Query(default=None),
    aggregator: Optional[List[str]] = Query(default=None),
    original_source: Optional[List[str]] = Query(default=None),
    tag: Optional[List[str]] = Query(default=None),
    db: Session = Depends(get_db),
):
    from models.analyses_translation import AnalysesTranslation
    from models.tag_translation import TagsTranslation
    from models.tag_group_translation import TagGroupDefinitionsTranslation

    group_def = load_group_def(db, group_name)
    group_id = group_def.id if group_def else None

    display_name = group_def.display_name if group_def else group_name
    group_description = group_def.description if group_def else None
    if lang != "en" and group_def:
        group_trans = db.query(TagGroupDefinitionsTranslation).filter(
            TagGroupDefinitionsTranslation.tag_group_definition_id == group_def.id,
            TagGroupDefinitionsTranslation.language == lang,
        ).first()
        if group_trans:
            display_name = group_trans.display_name
            group_description = group_trans.description

    analyses = query_group_articles(
        db, group_name,
        topic_id=topic_id,
        published_after=published_after,
        published_before=published_before,
        scraped_after=scraped_after,
        scraped_before=scraped_before,
        aggregators=aggregator or None,
        original_sources=original_source or None,
        tags=tag or None,
    )

    analysis_ids = [a.id for a in analyses]
    trans_map: dict = {}
    en_map: dict = {}
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

    tag_trans_map: dict = {}
    if lang != "en" and group_id:
        from models.tag import Tag
        tag_ids = set()
        for analysis in analyses:
            if analysis.article:
                for tag_obj in analysis.article.tags:
                    if tag_obj.tag_group_id == group_id:
                        tag_ids.add(tag_obj.id)
        if tag_ids:
            tag_translations = db.query(TagsTranslation).filter(
                TagsTranslation.tag_id.in_(tag_ids),
                TagsTranslation.language == lang,
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
            if t.tag_group_id == group_id
        ]

        pain_points = insights = innovations = None
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
