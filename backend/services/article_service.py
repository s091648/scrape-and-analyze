from datetime import date
from typing import List, Optional
from uuid import UUID

from sqlalchemy.orm import Session

from backend.schemas.article import ArticleOut


def build_article_out(article, translation=None) -> ArticleOut:
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
):
    from models.article import Article

    query = db.query(Article)

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

    col = getattr(Article, sort, None)
    if col is not None:
        query = query.order_by(col.desc() if order == "desc" else col.asc())

    total = query.count()
    items = query.offset((page - 1) * size).limit(size).all()
    return total, items


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
