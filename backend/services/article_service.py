from datetime import date, datetime, timedelta, timezone
from typing import Dict, List, Optional
from uuid import UUID

from sqlalchemy import func, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session, contains_eager

from backend.schemas.article import ArticleOut, PaginatedArticles


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
    ).filter(Article.merged_into_id.is_(None))

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


def build_articles_list_payload(
    db: Session,
    *,
    sort: str = "scraped_at",
    order: str = "desc",
    page: int = 1,
    size: int = 20,
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
    lang: str = "en",
) -> dict:
    """The GET /articles response body — extracted from routers/articles.py's list_articles()
    so backend/cache_warmup.py (020-redis-caching-layer follow-up) can produce the exact same
    payload a router-served request would, without going through FastAPI/HTTP at all. The
    router still owns the *cache key* shape (its own cache_params dict) — this only guarantees
    the *value* can never drift between the two call sites."""
    total, rows = get_articles_paginated(
        db, sort, order, page, size,
        sources=sources, aggregators=aggregators, original_sources=original_sources,
        tags=tags, tag_ids=tag_ids, tag_groups=tag_groups,
        published_after=published_after, published_before=published_before,
        scraped_after=scraped_after, scraped_before=scraped_before,
        topic_id=topic_id, user_id=user_id, favorites_only=favorites_only,
    )
    trans_map: dict = {}
    if lang != "en" and rows:
        from models.article_translation import ArticleTranslation
        article_ids = [r[0].id for r in rows]
        translations = db.query(ArticleTranslation).filter(
            ArticleTranslation.article_id.in_(article_ids),
            ArticleTranslation.language == lang,
        ).all()
        trans_map = {t.article_id: t for t in translations}
    return PaginatedArticles(
        items=[
            build_article_out(article, trans_map.get(article.id), metrics, metric_values, favorite)
            for article, metrics, metric_values, favorite in rows
        ],
        total=total,
        page=page,
        size=size,
    ).model_dump(mode="json")


def get_article_by_id(db: Session, article_id: UUID):
    """Look up an article by id, transparently following a merge tombstone to
    the surviving article (a stale link to a since-merged duplicate should
    still resolve, like the OpenAlex redirect it mirrors)."""
    from models.article import Article
    article = db.query(Article).filter(Article.id == article_id).first()
    if article and article.merged_into_id:
        return db.query(Article).filter(Article.id == article.merged_into_id).first()
    return article


def get_tag_groups_for_article(db: Session, article_id: UUID, lang: str = "en") -> list:
    from models.tag import Tag, article_tags as at
    from models.tag_group import TagGroupDefinition
    from models.tag_translation import TagsTranslation
    from models.tag_group_translation import TagGroupDefinitionsTranslation

    tags = (
        db.query(Tag)
        .join(at, Tag.id == at.c.tag_id)
        .outerjoin(TagGroupDefinition, Tag.tag_group_id == TagGroupDefinition.id)
        # Reuse the outer join above to populate tag.group_def — the loop below
        # touches it for every tag, which would otherwise be one lazy query each.
        .options(contains_eager(Tag.group_def))
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
    """Scan Redis view:* keys, flush accumulated counts to article_metrics, return flushed count.

    Each flushed batch is applied twice: to the cumulative article_metrics.view_count (the
    authoritative all-time total) and, added into the current UTC day's row in
    article_view_daily (the time-windowed history behind /admin/analytics). The per-day upsert
    keys on (article_id, day) so several flushes in the same day accumulate.
    """
    import redis.asyncio as aioredis
    from models.article_metrics import ArticleMetrics
    from models.article_view_daily import ArticleViewDaily
    from backend.config import REDIS_URL

    r = aioredis.from_url(REDIS_URL)
    today_utc = datetime.now(timezone.utc).date()
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
                article_id = key.decode().split(":", 1)[1]

                db.execute(
                    update(ArticleMetrics)
                    .where(ArticleMetrics.article_id == article_id)
                    .values(view_count=ArticleMetrics.view_count + count)
                )

                bucket = pg_insert(ArticleViewDaily).values(
                    article_id=article_id, day=today_utc, views=count
                )
                db.execute(
                    bucket.on_conflict_do_update(
                        index_elements=["article_id", "day"],
                        set_={"views": ArticleViewDaily.views + bucket.excluded.views},
                    )
                )
                flushed += 1
            if cursor == 0:
                break
        db.commit()
    finally:
        await r.aclose()
    return flushed


def get_analytics_overview(db: Session, days: int) -> dict:
    """Everything the /admin/analytics page needs in one payload, over the last `days` UTC days:
    site-wide daily view totals, the top-20 trending articles (with a per-article daily
    sparkline), a per-topic breakdown, and the all-time top-10 (from article_metrics, no
    window). Read-only."""
    from models.article import Article
    from models.article_metrics import ArticleMetrics
    from models.article_view_daily import ArticleViewDaily
    from models.topic import Topic

    cutoff = datetime.now(timezone.utc).date() - timedelta(days=days)
    in_window = ArticleViewDaily.day >= cutoff
    source_col = func.coalesce(Article.original_source, Article.source)

    daily_totals = [
        {"day": row.day, "views": int(row.views)}
        for row in db.execute(
            select(ArticleViewDaily.day, func.sum(ArticleViewDaily.views).label("views"))
            .where(in_window)
            .group_by(ArticleViewDaily.day)
            .order_by(ArticleViewDaily.day)
        )
    ]

    window_views = func.sum(ArticleViewDaily.views).label("window_views")
    total_views = func.coalesce(ArticleMetrics.view_count, 0).label("total_views")
    trending_rows = db.execute(
        select(
            ArticleViewDaily.article_id.label("article_id"),
            window_views,
            Article.title.label("title"),
            source_col.label("source"),
            Topic.display_name.label("topic"),
            total_views,
        )
        .join(Article, Article.id == ArticleViewDaily.article_id)
        .outerjoin(Topic, Topic.id == Article.topic_id)
        .outerjoin(ArticleMetrics, ArticleMetrics.article_id == ArticleViewDaily.article_id)
        .where(in_window, Article.merged_into_id.is_(None))
        .group_by(
            ArticleViewDaily.article_id, Article.title, Article.original_source,
            Article.source, Topic.display_name, ArticleMetrics.view_count,
        )
        .order_by(window_views.desc(), total_views.desc())
        .limit(20)
    ).all()

    trending_ids = [row.article_id for row in trending_rows]
    sparklines: dict = {aid: [] for aid in trending_ids}
    if trending_ids:
        for row in db.execute(
            select(ArticleViewDaily.article_id, ArticleViewDaily.day, ArticleViewDaily.views)
            .where(ArticleViewDaily.article_id.in_(trending_ids), in_window)
            .order_by(ArticleViewDaily.article_id, ArticleViewDaily.day)
        ):
            sparklines[row.article_id].append({"day": row.day, "views": int(row.views)})

    trending = [
        {
            "article_id": row.article_id,
            "title": row.title,
            "source": row.source,
            "topic": row.topic,
            "window_views": int(row.window_views),
            "total_views": int(row.total_views),
            "sparkline": sparklines.get(row.article_id, []),
        }
        for row in trending_rows
    ]

    topic_label = func.coalesce(Topic.display_name, "(no topic)").label("topic")
    topic_views = func.sum(ArticleViewDaily.views).label("views")
    by_topic = [
        {"topic": row.topic, "views": int(row.views)}
        for row in db.execute(
            select(topic_label, topic_views)
            .join(Article, Article.id == ArticleViewDaily.article_id)
            .outerjoin(Topic, Topic.id == Article.topic_id)
            .where(in_window, Article.merged_into_id.is_(None))
            .group_by(topic_label)
            .order_by(topic_views.desc())
        )
    ]

    all_time_top = [
        {
            "article_id": row.article_id,
            "title": row.title,
            "source": row.source,
            "topic": row.topic,
            "total_views": int(row.total_views),
        }
        for row in db.execute(
            select(
                ArticleMetrics.article_id.label("article_id"),
                ArticleMetrics.view_count.label("total_views"),
                Article.title.label("title"),
                source_col.label("source"),
                Topic.display_name.label("topic"),
            )
            .join(Article, Article.id == ArticleMetrics.article_id)
            .outerjoin(Topic, Topic.id == Article.topic_id)
            .where(Article.merged_into_id.is_(None), ArticleMetrics.view_count > 0)
            .order_by(ArticleMetrics.view_count.desc())
            .limit(10)
        )
    ]

    return {
        "days": days,
        "daily_totals": daily_totals,
        "trending": trending,
        "by_topic": by_topic,
        "all_time_top": all_time_top,
    }


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
