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


def query_analyses(db: Session, days: int) -> list:
    from src.models.analysis import Analysis
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    return db.query(Analysis).filter(Analysis.analyzed_at >= cutoff).all()


def build_graph(analyses: list) -> dict:
    nodes = []
    edges = []
    tag_ids: dict[str, str] = {}
    article_ids: set[str] = set()

    for analysis in analyses:
        article_id = str(analysis.article_id)
        if article_id not in article_ids:
            article_ids.add(article_id)
            nodes.append({
                "id": article_id,
                "type": "article",
                "label": analysis.article.title if analysis.article else "",
                "articleId": article_id,
            })

        for tag in (analysis.tags or []):
            tag_node_id = f"tag:{tag}"
            if tag_node_id not in tag_ids:
                tag_ids[tag_node_id] = tag_node_id
                nodes.append({"id": tag_node_id, "type": "tag", "label": tag})
            edges.append({"source": tag_node_id, "target": article_id})

    return {"nodes": nodes, "edges": edges}


def query_tag_articles(db: Session, tag: str) -> list:
    from src.models.analysis import Analysis
    from sqlalchemy import cast
    from sqlalchemy.dialects.postgresql import ARRAY, TEXT
    return db.query(Analysis).filter(
        Analysis.tags.contains(cast([tag], ARRAY(TEXT)))
    ).all()


@router.get("/analyses/graph/tag/{tag}")
def get_tag_articles(tag: str, db: Session = Depends(get_db)):
    analyses = query_tag_articles(db, tag)
    result = []
    for analysis in analyses:
        article = analysis.article
        if article:
            result.append({
                "articleId": str(analysis.article_id),
                "title": article.title,
                "source": article.source,
                "url": article.url,
                "published_at": article.published_at.isoformat() if article.published_at else None,
                "excerpt": (article.content or "")[:200],
                "pain_points": analysis.pain_points,
                "insights": analysis.insights,
                "innovations": analysis.innovations,
            })
    return result


@router.get("/analyses/graph")
def get_graph(days: int = Query(30, ge=1, le=365), db: Session = Depends(get_db)):
    now = time.time()
    if days in _cache:
        result, expires_at = _cache[days]
        if now < expires_at:
            return result

    analyses = query_analyses(db, days)
    result = build_graph(analyses)
    _cache[days] = (result, now + CACHE_TTL_SECONDS)
    return result
