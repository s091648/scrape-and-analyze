from datetime import date
from typing import Dict, List, Optional
from uuid import UUID

from sqlalchemy.orm import Session

from backend.schemas.article import ArticleOut


def build_article_out(article, translation=None, metrics=None, metric_values: Optional[Dict[str, float]] = None, favorite=None) -> ArticleOut:
    meta = article.metadata_ or {}
    return ArticleOut(
        id=article.id,
        url=article.url,
        source=article.source,
        title=article.title,
        content=article.content,
        published_at=article.published_at,
        scraped_at=article.scraped_at,
        via_source=meta.get("via_source"),
        original_source=article.original_source or meta.get("original_source"),
        translated_title=translation.title if translation else None,
        translated_content=translation.content if translation else None,
        has_vectors=article.has_vectors,
        metrics=metric_values or {},
        view_count=metrics.view_count if metrics else 0,
        is_favorited=favorite is not None,
    )


def get_articles_paginated(
    db: Session,
    sort: str,
    order: str,
    page: int,
    size: int,
    sources: List[str] | None = None,
    aggregators: List[str] | None = None,
    original_sources: List[str] | None = None,
    tags: List[str] | None = None,
    tag_ids: List[UUID] | None = None,
    tag_groups: List[str] | None = None,
    published_after: Optional[date] = None,
    published_before: Optional[date] = None,
    scraped_after: Optional[date] = None,
    scraped_before: Optional[date] = None,
    topic_id: Optional[UUID] = None,
    user_id: Optional[UUID] = None,
    favorites_only: bool = False,
):
    from models.article import Article
    from models.article_metrics import ArticleMetrics
    from models.article_metric_value import ArticleMetricValue
    from models.user_subscription import UserArticleFavorite
    from sqlalchemy.orm import aliased

    if favorites_only and not user_id:
        return 0, []  # unauthenticated users have no favorites to filter by

    query = db.query(Article, ArticleMetrics, UserArticleFavorite).outerjoin(
        ArticleMetrics, ArticleMetrics.article_id == Article.id
    ).outerjoin(
        UserArticleFavorite,
        (UserArticleFavorite.article_id == Article.id) & (UserArticleFavorite.user_id == user_id)
        if user_id else (UserArticleFavorite.article_id == None),
    )

    if favorites_only and user_id:
        query = query.filter(UserArticleFavorite.user_id == user_id)

    if topic_id:
        query = query.filter(Article.topic_id == topic_id)
    if sources:
        query = query.filter(Article.source.in_(sources))
    if aggregators:
        query = query.filter(Article.source.in_(aggregators))
    if original_sources:
        query = query.filter(Article.original_source.in_(original_sources))
    if tag_ids:
        from models.tag import article_tags as at
        from sqlalchemy import select
        for tag_id in tag_ids:
            subq = select(at.c.article_id).where(at.c.tag_id == tag_id).scalar_subquery()
            query = query.filter(Article.id.in_(subq))
    if tags:
        from models.tag import Tag, article_tags as at
        from sqlalchemy import select
        for tag_name in tags:
            subq = select(at.c.article_id).join(Tag, Tag.id == at.c.tag_id).where(Tag.name == tag_name).scalar_subquery()
            query = query.filter(Article.id.in_(subq))
    if tag_groups:
        from models.tag import Tag, article_tags as at
        from models.tag_group import TagGroupDefinition
        from sqlalchemy import select
        for group_name in tag_groups:
            subq = (
                select(at.c.article_id)
                .join(Tag, Tag.id == at.c.tag_id)
                .join(TagGroupDefinition, TagGroupDefinition.id == Tag.tag_group_id)
                .where(TagGroupDefinition.name == group_name)
                .scalar_subquery()
            )
            query = query.filter(Article.id.in_(subq))

    if published_after:
        query = query.filter(Article.published_at >= published_after)
    if published_before:
        query = query.filter(Article.published_at <= published_before)
    if scraped_after:
        query = query.filter(Article.scraped_at >= scraped_after)
    if scraped_before:
        query = query.filter(Article.scraped_at <= scraped_before)

    _FIXED_SORT_COLUMNS = {"scraped_at", "published_at", "source", "title"}
    if sort == "view_count":
        col = ArticleMetrics.view_count
        # nullslast() regardless of direction: articles are outer-joined, so most have no
        # row at all (NULL, not 0). Postgres defaults to NULLS FIRST on DESC, which would
        # otherwise push every article with no metrics to the top of the "highest first"
        # sort — always sink them to the bottom instead.
        query = query.order_by(col.desc().nullslast() if order == "desc" else col.asc().nullslast())
    elif sort in _FIXED_SORT_COLUMNS:
        col = getattr(Article, sort)
        query = query.order_by(col.desc() if order == "desc" else col.asc())
    else:
        # 2026-07-12: `sort` is no longer restricted to a hardcoded set of metric names —
        # any deployment-defined catalog metric_key (citation_count, impact_factor, ...) is
        # sortable this way. An unrecognized value simply joins to nothing and produces a
        # no-op sort, the same graceful degradation as the old `getattr(Article, sort, None)`
        # fallback below.
        sort_metric = aliased(ArticleMetricValue)
        query = query.outerjoin(
            sort_metric,
            (sort_metric.article_id == Article.id) & (sort_metric.metric_key == sort),
        )
        col = sort_metric.value
        query = query.order_by(col.desc().nullslast() if order == "desc" else col.asc().nullslast())

    total = query.count()
    page_rows = query.offset((page - 1) * size).limit(size).all()

    article_ids = [article.id for article, _, _ in page_rows]
    metrics_by_article: dict[UUID, Dict[str, float]] = {}
    if article_ids:
        metric_rows = (
            db.query(ArticleMetricValue)
            .filter(ArticleMetricValue.article_id.in_(article_ids), ArticleMetricValue.value.isnot(None))
            .all()
        )
        for mv in metric_rows:
            metrics_by_article.setdefault(mv.article_id, {})[mv.metric_key] = float(mv.value)

    rows = [
        (article, metrics, metrics_by_article.get(article.id, {}), favorite)
        for article, metrics, favorite in page_rows
    ]
    return total, rows  # list of (Article, ArticleMetrics|None, metrics: Dict[str, float], UserArticleFavorite|None)


def get_article_by_id(db: Session, article_id: UUID):
    from models.article import Article
    return db.query(Article).filter(Article.id == article_id).first()


def get_tag_groups_for_article(db: Session, article_id: UUID, lang: str = "en") -> list:
    from models.tag import Tag, article_tags as at
    from models.tag_group import TagGroupDefinition
    from models.tag_translation import TagsTranslation
    from models.tag_group_translation import TagGroupDefinitionsTranslation

    tags = (
        db.query(Tag)
        .join(at, Tag.id == at.c.tag_id)
        .outerjoin(TagGroupDefinition, Tag.tag_group_id == TagGroupDefinition.id)
        .filter(at.c.article_id == article_id)
        .order_by(TagGroupDefinition.name, Tag.name)
        .all()
    )

    tag_ids = [t.id for t in tags]
    tag_trans_map: dict = {}
    group_trans_map: dict = {}
    if lang != "en" and tag_ids:
        tag_translations = db.query(TagsTranslation).filter(
            TagsTranslation.tag_id.in_(tag_ids),
            TagsTranslation.language == lang,
        ).all()
        tag_trans_map = {tt.tag_id: tt.name for tt in tag_translations}

        group_ids = list({t.group_def.id for t in tags if t.group_def})
        if group_ids:
            group_translations = db.query(TagGroupDefinitionsTranslation).filter(
                TagGroupDefinitionsTranslation.tag_group_definition_id.in_(group_ids),
                TagGroupDefinitionsTranslation.language == lang,
            ).all()
            group_trans_map = {gt.tag_group_definition_id: gt for gt in group_translations}

    groups: dict = {}
    for tag in tags:
        gname = tag.group_def.name if tag.group_def else "ungrouped"
        if gname not in groups:
            gdef = tag.group_def
            if gdef:
                if lang != "en" and gdef.id in group_trans_map:
                    display_name = group_trans_map[gdef.id].display_name
                else:
                    display_name = gdef.display_name
            else:
                display_name = "Ungrouped"
            groups[gname] = {
                "group_name": gname,
                "display_name": display_name,
                "color": gdef.color_hex if gdef else None,
                "tags": [],
            }
        tag_name = tag_trans_map.get(tag.id, tag.name) if lang != "en" else tag.name
        groups[gname]["tags"].append(tag_name)

    result = list(groups.values())
    result.sort(key=lambda g: (g["group_name"] == "ungrouped", g["display_name"]))
    return result


def get_filter_sources(db: Session, topic_id: Optional[UUID] = None) -> list:
    from models.article import Article
    query = db.query(Article.source).distinct()
    if topic_id:
        query = query.filter(Article.topic_id == topic_id)
    return [r[0] for r in query.order_by(Article.source).all()]


def get_filter_original_sources(db: Session, topic_id: Optional[UUID] = None) -> list:
    from models.article import Article
    query = db.query(Article.original_source).distinct().filter(Article.original_source.isnot(None))
    if topic_id:
        query = query.filter(Article.topic_id == topic_id)
    return [r[0] for r in query.order_by(Article.original_source).all()]


async def flush_view_counts(db: Session) -> int:
    """Scan Redis view:* keys, flush accumulated counts to article_metrics, return flushed count."""
    import redis.asyncio as aioredis
    import os
    from models.article_metrics import ArticleMetrics
    from sqlalchemy import text

    redis_url = os.environ.get("REDIS_URL", "redis://redis:6379/0")
    r = aioredis.from_url(redis_url)
    flushed = 0
    try:
        cursor = 0
        while True:
            cursor, keys = await r.scan(cursor, match="view:*", count=100)
            for key in keys:
                raw = await r.getdel(key)
                if not raw:
                    continue
                count = int(raw)
                if count <= 0:
                    continue
                article_id_str = key.decode().split(":", 1)[1]
                db.execute(
                    text(
                        "UPDATE article_metrics SET view_count = view_count + :count "
                        "WHERE article_id = :article_id"
                    ),
                    {"count": count, "article_id": article_id_str},
                )
                flushed += 1
            if cursor == 0:
                break
        db.commit()
    finally:
        await r.aclose()
    return flushed


def get_filter_tags(db: Session, topic_id: Optional[UUID] = None) -> list:
    from models.tag import Tag, article_tags as at
    from models.article import Article
    query = db.query(Tag.name).distinct()
    if topic_id:
        query = (
            query
            .join(at, Tag.id == at.c.tag_id)
            .join(Article, Article.id == at.c.article_id)
            .filter(Article.topic_id == topic_id)
        )
    return [r[0] for r in query.order_by(Tag.name).all()]
