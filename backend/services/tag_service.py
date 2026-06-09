from typing import List, Optional
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import func, distinct, text
from sqlalchemy.orm import Session

from backend.schemas.tag import TagOut, SimilarGroupOut


def embed_text(content: str) -> Optional[list]:
    import os
    api_key = os.environ.get("GEMINI_API_KEY", "")
    if not api_key:
        return None
    try:
        from google import genai
        from google.genai import types
        client = genai.Client(api_key=api_key)
        result = client.models.embed_content(
            model="gemini-embedding-001",
            contents=content,
            config=types.EmbedContentConfig(task_type="SEMANTIC_SIMILARITY"),
        )
        return result.embeddings[0].values
    except Exception:
        return None


def get_similar_groups(db: Session, group_id: UUID, topic_id: UUID, threshold: float = 0.90) -> List[SimilarGroupOut]:
    rows = db.execute(text("""
        SELECT b.id, 1 - (a.embedding <=> b.embedding) AS score
        FROM tag_group_definitions a
        JOIN tag_group_definitions b
          ON b.topic_id = a.topic_id AND b.id != a.id
        WHERE a.id = :group_id
          AND a.embedding IS NOT NULL
          AND b.embedding IS NOT NULL
          AND 1 - (a.embedding <=> b.embedding) >= :threshold
        ORDER BY score DESC
        LIMIT 5
    """), {"group_id": str(group_id), "threshold": threshold}).fetchall()
    return [SimilarGroupOut(id=row[0], similarity_score=float(row[1])) for row in rows]


def tag_outs_for_group(db: Session, grp) -> List[TagOut]:
    from models.tag import Tag, article_tags as article_tags_table
    from models.article import Article
    q = (
        db.query(Tag.id, Tag.name, func.count(distinct(article_tags_table.c.article_id)).label("article_count"))
        .join(article_tags_table, article_tags_table.c.tag_id == Tag.id)
        .join(Article, Article.id == article_tags_table.c.article_id)
        .filter(Tag.tag_group_id == grp.id)
    )
    if grp.topic_id:
        q = q.filter(Article.topic_id == grp.topic_id)
    rows = q.group_by(Tag.id, Tag.name).order_by(Tag.name).all()
    return [TagOut(id=r.id, name=r.name, article_count=r.article_count) for r in rows]


def ungrouped_tag_outs(db: Session, topic_id: UUID) -> List[TagOut]:
    from models.tag import Tag, article_tags as article_tags_table
    from models.article import Article
    q = (
        db.query(Tag.id, Tag.name, func.count(distinct(article_tags_table.c.article_id)).label("article_count"))
        .join(article_tags_table, article_tags_table.c.tag_id == Tag.id)
        .join(Article, Article.id == article_tags_table.c.article_id)
        .filter(Tag.tag_group_id.is_(None))
        .filter(Article.topic_id == topic_id)
    )
    rows = q.group_by(Tag.id, Tag.name).order_by(Tag.name).all()
    return [TagOut(id=r.id, name=r.name, article_count=r.article_count) for r in rows]


def merge_tag_groups(
    db: Session,
    group_a_id: UUID,
    group_b_id: UUID,
    result_name: str,
    result_display_name: str,
    result_color_hex: Optional[str],
    result_description: Optional[str],
):
    from models.tag_group import TagGroupDefinition
    from models.tag import Tag
    from models.topic import Topic  # noqa: F401 — registers mapper for FK resolution

    group_a = db.query(TagGroupDefinition).filter_by(id=group_a_id).first()
    group_b = db.query(TagGroupDefinition).filter_by(id=group_b_id).first()
    if not group_a or not group_b:
        raise HTTPException(status_code=404, detail="Tag group not found")
    if group_a.topic_id != group_b.topic_id:
        raise HTTPException(status_code=400, detail="Groups must belong to the same topic")

    existing_result = (
        db.query(TagGroupDefinition)
        .filter(
            TagGroupDefinition.name == result_name,
            TagGroupDefinition.topic_id == group_a.topic_id,
            TagGroupDefinition.id.notin_([group_a.id, group_b.id]),
        )
        .first()
    )

    if result_name == group_a.name:
        result_group = group_a
        groups_to_delete = [group_b]
    elif result_name == group_b.name:
        result_group = group_b
        groups_to_delete = [group_a]
    elif existing_result:
        result_group = existing_result
        groups_to_delete = [group_a, group_b]
    else:
        result_group = TagGroupDefinition(
            name=result_name,
            display_name=result_display_name,
            color_hex=result_color_hex,
            description=result_description,
            topic_id=group_a.topic_id,
        )
        db.add(result_group)
        db.flush()
        groups_to_delete = [group_a, group_b]

    result_group.display_name = result_display_name
    result_group.color_hex = result_color_hex
    result_group.description = result_description

    source_ids = [g.id for g in groups_to_delete]

    source_tags = db.query(Tag).filter(Tag.tag_group_id.in_(source_ids)).all()
    seen: dict = {}
    for t in source_tags:
        if t.name in seen:
            keep, drop = seen[t.name], t
            db.execute(text("""
                INSERT INTO article_tags (article_id, tag_id)
                SELECT article_id, :keep FROM article_tags WHERE tag_id = :drop
                ON CONFLICT DO NOTHING
            """), {"keep": str(keep.id), "drop": str(drop.id)})
            db.execute(text("DELETE FROM article_tags WHERE tag_id = :drop"), {"drop": str(drop.id)})
            db.execute(text("DELETE FROM tags WHERE id = :drop"), {"drop": str(drop.id)})
        else:
            seen[t.name] = t
    db.flush()

    existing_result_tags = {
        t.name: t for t in db.query(Tag).filter(Tag.tag_group_id == result_group.id).all()
    }
    for name, existing_t in existing_result_tags.items():
        if name in seen:
            drop = seen.pop(name)
            db.execute(text("""
                INSERT INTO article_tags (article_id, tag_id)
                SELECT article_id, :keep FROM article_tags WHERE tag_id = :drop
                ON CONFLICT DO NOTHING
            """), {"keep": str(existing_t.id), "drop": str(drop.id)})
            db.execute(text("DELETE FROM article_tags WHERE tag_id = :drop"), {"drop": str(drop.id)})
            db.execute(text("DELETE FROM tags WHERE id = :drop"), {"drop": str(drop.id)})
    db.flush()

    db.query(Tag).filter(
        Tag.tag_group_id.in_(source_ids)
    ).update({"tag_group_id": result_group.id}, synchronize_session=False)

    for grp in groups_to_delete:
        db.delete(grp)

    db.commit()
    db.refresh(result_group)
    return result_group
