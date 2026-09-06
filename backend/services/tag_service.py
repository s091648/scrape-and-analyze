from typing import List, Optional
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import func, distinct, text
from sqlalchemy.orm import Session

from backend.schemas.tag import TagOut, SimilarGroupOut, TagGroupOut
from backend.config import GEMINI_API_KEY


def embed_text(content: str) -> Optional[list]:
    api_key = GEMINI_API_KEY
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


def tag_outs_for_groups(db: Session, groups: list) -> dict:
    """Batched equivalent of calling tag_outs_for_group() once per group in a loop — a
    single query for every group's tags instead of one query per group (was an N+1:
    GET /tag-groups with N groups issued 1 + N queries). TagGroupDefinition.topic_id is
    NOT NULL (see models/tag_group.py), so joining it in lets each row's article count
    stay scoped to its own group's topic — same semantics as tag_outs_for_group()'s
    per-group `Article.topic_id == grp.topic_id` filter, just correlated per-row instead
    of re-run once per group."""
    from models.tag import Tag, article_tags as article_tags_table
    from models.article import Article
    from models.tag_group import TagGroupDefinition

    result: dict = {grp.id: [] for grp in groups}
    if not groups:
        return result

    rows = (
        db.query(
            Tag.tag_group_id, Tag.id, Tag.name,
            func.count(distinct(article_tags_table.c.article_id)).label("article_count"),
        )
        .join(article_tags_table, article_tags_table.c.tag_id == Tag.id)
        .join(Article, Article.id == article_tags_table.c.article_id)
        .join(TagGroupDefinition, TagGroupDefinition.id == Tag.tag_group_id)
        .filter(Tag.tag_group_id.in_([grp.id for grp in groups]))
        .filter(Article.topic_id == TagGroupDefinition.topic_id)
        .group_by(Tag.tag_group_id, Tag.id, Tag.name)
        .order_by(Tag.name)
        .all()
    )
    for tag_group_id, tag_id, tag_name, article_count in rows:
        result[tag_group_id].append(TagOut(id=tag_id, name=tag_name, article_count=article_count))
    return result


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


def build_tag_groups_payload(
    db: Session,
    *,
    topic_id: Optional[UUID] = None,
    include_similarity: bool = False,
) -> List[dict]:
    """The GET /tag-groups response body — extracted from routers/tags.py's list_tag_groups()
    so backend/cache_warmup.py (020-redis-caching-layer follow-up) can call it directly."""
    from models.tag_group import TagGroupDefinition

    q = db.query(TagGroupDefinition)
    if topic_id:
        q = q.filter(TagGroupDefinition.topic_id == topic_id)
    groups = q.order_by(TagGroupDefinition.sort_order, TagGroupDefinition.name).all()

    tags_by_group = tag_outs_for_groups(db, groups)

    result = []
    for grp in groups:
        similar = (
            get_similar_groups(db, grp.id, grp.topic_id)
            if include_similarity and topic_id
            else []
        )
        result.append(TagGroupOut(
            id=grp.id, name=grp.name, display_name=grp.display_name,
            description=grp.description, color_hex=grp.color_hex,
            topic_id=grp.topic_id, tags=tags_by_group[grp.id],
            similar_groups=similar,
        ))

    if topic_id:
        ungrouped = ungrouped_tag_outs(db, topic_id)
        if ungrouped:
            result.append(TagGroupOut(
                id=None, name="ungrouped", display_name="Ungrouped",
                description=None, color_hex=None,
                topic_id=topic_id, tags=ungrouped,
                similar_groups=[],
            ))

    return [g.model_dump(mode="json") for g in result]


def lock_tags_for_update(db: Session, tag_ids) -> None:
    """Row-lock the given tag ids before any concurrent-unsafe merge/delete logic
    touches them (approve_suggestion(s_batch), merge_tag_groups). Always locks in a
    stable id order — two transactions locking the same tags in different orders is
    exactly how you deadlock instead of just serializing."""
    ids = sorted({str(t) for t in tag_ids if t is not None})
    if not ids:
        return
    db.execute(
        text("SELECT id FROM tags WHERE id = ANY(CAST(:ids AS uuid[])) ORDER BY id FOR UPDATE"),
        {"ids": ids},
    )


def repoint_pending_suggestions_before_tag_delete(
    db: Session,
    dropped_tag_id,
    keep_tag_id,
    exclude_suggestion_id=None,
) -> None:
    """Call before deleting `dropped_tag_id` (whether via suggestion-approval merge or
    tag-group-merge dedup). Both tag_normalization_suggestions FK columns are
    ON DELETE CASCADE onto tags.id, so deleting a tag silently deletes every
    suggestion that still references it — including *other* still-pending
    suggestions that happen to share that tag (e.g. one created earlier in the same
    run that got auto-merged into it, or a genuine duplicate). Repointing/dropping
    them here first is what stops that cascade from destroying merge intent that
    was never actually resolved.
    """
    dropped_id = str(dropped_tag_id)
    keep_id = str(keep_tag_id)
    exclude_clause = "AND id != :exclude_id" if exclude_suggestion_id is not None else ""
    params = {"existing_id": keep_id, "new_id": dropped_id}
    if exclude_suggestion_id is not None:
        params["exclude_id"] = str(exclude_suggestion_id)

    # A reciprocal pending suggestion (new_tag_id = keep_tag, existing_tag_id =
    # dropped_tag) would be turned into a self-referential row — both IDs = keep_tag
    # — by the repoint below, and later approval of that row would then delete
    # keep_tag itself along with its article links. This merge already resolves the
    # pair, so drop those rows outright before repointing.
    db.execute(text(f"""
        DELETE FROM tag_normalization_suggestions
        WHERE existing_tag_id = :new_id AND new_tag_id = :existing_id
          AND status = 'pending' {exclude_clause}
    """), params)

    # Any other pending suggestion pointing at dropped_tag as ITS existing_tag would
    # otherwise be cascade-deleted when dropped_tag is removed — repoint it at
    # keep_tag so it survives to be approved/rejected later.
    db.execute(text(f"""
        UPDATE tag_normalization_suggestions
        SET existing_tag_id = :existing_id
        WHERE existing_tag_id = :new_id AND status = 'pending' {exclude_clause}
    """), params)

    # Any other pending suggestion for the very same dropped_tag is redundant — this
    # merge already resolves that tag, so drop it rather than let the cascade below
    # silently remove it without ever recording a decision.
    db.execute(text(f"""
        DELETE FROM tag_normalization_suggestions
        WHERE new_tag_id = :new_id AND status = 'pending' {exclude_clause}
    """), params)


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

    # Lock both groups up front, in stable id order, so a concurrent merge/delete
    # touching either group serializes instead of racing with this one.
    group_ids_sorted = sorted([str(group_a_id), str(group_b_id)])
    db.execute(
        text("SELECT id FROM tag_group_definitions WHERE id = ANY(CAST(:ids AS uuid[])) ORDER BY id FOR UPDATE"),
        {"ids": group_ids_sorted},
    )

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

    # Lock every tag under the source groups and the destination group up front (stable
    # id order) so a concurrent approve/merge touching one of the same tags can't
    # interleave with the raw DELETE/INSERT statements below.
    candidate_tag_ids = [
        row[0] for row in db.query(Tag.id).filter(
            Tag.tag_group_id.in_(source_ids + [result_group.id])
        ).all()
    ]
    lock_tags_for_update(db, candidate_tag_ids)

    source_tags = db.query(Tag).filter(Tag.tag_group_id.in_(source_ids)).all()
    seen: dict = {}
    for t in source_tags:
        if t.name in seen:
            keep, drop = seen[t.name], t
            repoint_pending_suggestions_before_tag_delete(db, dropped_tag_id=drop.id, keep_tag_id=keep.id)
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
            repoint_pending_suggestions_before_tag_delete(db, dropped_tag_id=drop.id, keep_tag_id=existing_t.id)
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
