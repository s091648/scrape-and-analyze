import re
from datetime import datetime, timezone
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, field_validator
from sqlalchemy import func, distinct, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.auth.guards import require_admin, require_user

router = APIRouter()


# ── Name helpers ─────────────────────────────────────────────────────────────

def _to_slug(v: str) -> str:
    """Normalise to snake_case slug: lowercase, non-alphanumerics → underscores."""
    v = v.lower().strip()
    v = re.sub(r'[^a-z0-9]+', '_', v)
    return v.strip('_')


def _to_title(v: str) -> str:
    """Title-case: capitalise first letter of each word, preserve spacing."""
    return ' '.join(w.capitalize() for w in v.strip().split())


# ── Schemas ──────────────────────────────────────────────────────────────────

class TagOut(BaseModel):
    id: UUID
    name: str
    article_count: int

    class Config:
        from_attributes = True


class TagGroupOut(BaseModel):
    id: Optional[UUID] = None  # None for virtual "Ungrouped"
    name: str
    display_name: str
    description: Optional[str]
    color_hex: Optional[str]
    topic_id: Optional[UUID] = None  # None for virtual "Ungrouped"
    tags: List[TagOut]
    similar_groups: List['SimilarGroupOut'] = []

    class Config:
        from_attributes = True


class SimilarGroupOut(BaseModel):
    id: UUID
    similarity_score: float


class TagGroupCreate(BaseModel):
    name: str
    display_name: str
    color_hex: Optional[str] = None
    topic_id: UUID
    description: Optional[str] = None
    sort_order: Optional[int] = None

    @field_validator('name')
    @classmethod
    def normalize_name(cls, v: str) -> str:
        return _to_slug(v)

    @field_validator('display_name')
    @classmethod
    def normalize_display_name(cls, v: str) -> str:
        return _to_title(v)


class TagGroupUpdate(BaseModel):
    name: Optional[str] = None
    display_name: Optional[str] = None
    color_hex: Optional[str] = None
    description: Optional[str] = None
    sort_order: Optional[int] = None

    @field_validator('name')
    @classmethod
    def normalize_name(cls, v: str) -> str:
        return _to_slug(v)

    @field_validator('display_name')
    @classmethod
    def normalize_display_name(cls, v: str) -> str:
        return _to_title(v)


class TagUpdate(BaseModel):
    name: Optional[str] = None
    tag_group_id: Optional[UUID] = None
    ungroup: Optional[bool] = None  # set tag_group_id to NULL


class TagMoveItem(BaseModel):
    tag_id: UUID
    tag_group_id: UUID


class BatchMoveResult(BaseModel):
    succeeded: List[str]
    failed: List[dict]


class SuggestionOut(BaseModel):
    id: UUID
    new_tag_id: UUID
    new_tag_name: str
    existing_tag_id: UUID
    existing_tag_name: str
    group_name: str
    similarity_score: float
    article_id: Optional[UUID]

    class Config:
        from_attributes = True


class TagGroupMergeRequest(BaseModel):
    group_a_id: UUID
    group_b_id: UUID
    result_name: str
    result_display_name: str
    result_color_hex: Optional[str] = None
    result_description: Optional[str] = None

    @field_validator('result_name')
    @classmethod
    def normalize_result_name(cls, v: str) -> str:
        return _to_slug(v)

    @field_validator('result_display_name')
    @classmethod
    def normalize_result_display_name(cls, v: str) -> str:
        return _to_title(v)


class TagGroupReorderItem(BaseModel):
    id: UUID
    sort_order: int

    class Config:
        from_attributes = True


# ── Helpers ──────────────────────────────────────────────────────────────────

def _embed_text(text: str) -> Optional[list]:
    """Generate a 768-dim embedding via Gemini. Returns None on any failure."""
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
            contents=text,
            config=types.EmbedContentConfig(task_type="SEMANTIC_SIMILARITY"),
        )
        return result.embeddings[0].values
    except Exception:
        return None


def _similar_groups(db: Session, group_id: UUID, topic_id: UUID, threshold: float = 0.90) -> List[SimilarGroupOut]:
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


def _tag_outs_for_group(db: Session, grp) -> List[TagOut]:
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


def _ungrouped_tag_outs(db: Session, topic_id: UUID) -> List[TagOut]:
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


# ── Routes ───────────────────────────────────────────────────────────────────

@router.get("/tag-groups", response_model=List[TagGroupOut])
def list_tag_groups(
    topic_id: Optional[UUID] = Query(default=None),
    include_similarity: bool = Query(default=False),
    db: Session = Depends(get_db),
):
    from models.tag_group import TagGroupDefinition

    q = db.query(TagGroupDefinition)
    if topic_id:
        q = q.filter(TagGroupDefinition.topic_id == topic_id)
    groups = q.order_by(TagGroupDefinition.sort_order, TagGroupDefinition.name).all()

    result = []
    for grp in groups:
        similar = (
            _similar_groups(db, grp.id, grp.topic_id)
            if include_similarity and topic_id
            else []
        )
        result.append(TagGroupOut(
            id=grp.id, name=grp.name, display_name=grp.display_name,
            description=grp.description, color_hex=grp.color_hex,
            topic_id=grp.topic_id, tags=_tag_outs_for_group(db, grp),
            similar_groups=similar,
        ))

    # Append virtual "Ungrouped" group if there are ungrouped tags
    if topic_id:
        ungrouped_tags = _ungrouped_tag_outs(db, topic_id)
        if ungrouped_tags:
            result.append(TagGroupOut(
                id=None, name="ungrouped", display_name="Ungrouped",
                description=None, color_hex=None,
                topic_id=topic_id, tags=ungrouped_tags,
                similar_groups=[],
            ))

    return result


@router.post("/tag-groups", response_model=TagGroupOut, status_code=201)
def create_tag_group(
    body: TagGroupCreate,
    db: Session = Depends(get_db),
    _: dict = Depends(require_admin),
):
    from models.tag_group import TagGroupDefinition
    from sqlalchemy import text as sa_text

    grp = TagGroupDefinition(**body.model_dump())
    db.add(grp)
    db.commit()
    db.refresh(grp)

    vec = _embed_text(grp.name)
    if vec is not None:
        vec_str = "[" + ",".join(str(x) for x in vec) + "]"
        db.execute(
            sa_text(
                "UPDATE tag_group_definitions SET embedding = CAST(:vec AS vector) WHERE id = :id"
            ),
            {"vec": vec_str, "id": str(grp.id)},
        )
        db.commit()

    return TagGroupOut(id=grp.id, name=grp.name, display_name=grp.display_name,
                       description=grp.description, color_hex=grp.color_hex,
                       topic_id=grp.topic_id, tags=[])


@router.post("/tag-groups/merge", response_model=TagGroupOut)
def merge_tag_groups(
    body: TagGroupMergeRequest,
    db: Session = Depends(get_db),
    _: dict = Depends(require_admin),
):
    from models.tag_group import TagGroupDefinition
    from models.tag import Tag
    from models.topic import Topic  # noqa: F401 — register table for FK resolution
    from sqlalchemy import text as sa_text

    group_a = db.query(TagGroupDefinition).filter_by(id=body.group_a_id).first()
    group_b = db.query(TagGroupDefinition).filter_by(id=body.group_b_id).first()
    if not group_a or not group_b:
        raise HTTPException(status_code=404, detail="Tag group not found")
    if group_a.topic_id != group_b.topic_id:
        raise HTTPException(status_code=400, detail="Groups must belong to the same topic")

    existing_result = (
        db.query(TagGroupDefinition)
        .filter(
            TagGroupDefinition.name == body.result_name,
            TagGroupDefinition.topic_id == group_a.topic_id,
            TagGroupDefinition.id.notin_([group_a.id, group_b.id]),
        )
        .first()
    )

    if body.result_name == group_a.name:
        result_group = group_a
        groups_to_delete = [group_b]
    elif body.result_name == group_b.name:
        result_group = group_b
        groups_to_delete = [group_a]
    elif existing_result:
        result_group = existing_result
        groups_to_delete = [group_a, group_b]
    else:
        result_group = TagGroupDefinition(
            name=body.result_name,
            display_name=body.result_display_name,
            color_hex=body.result_color_hex,
            description=body.result_description,
            topic_id=group_a.topic_id,
        )
        db.add(result_group)
        db.flush()
        groups_to_delete = [group_a, group_b]

    result_group.display_name = body.result_display_name
    result_group.color_hex = body.result_color_hex
    result_group.description = body.result_description

    source_ids = [g.id for g in groups_to_delete]

    # Deduplicate within source tags (same name across two source groups)
    source_tags = db.query(Tag).filter(Tag.tag_group_id.in_(source_ids)).all()
    seen: dict = {}
    for t in source_tags:
        if t.name in seen:
            keep, drop = seen[t.name], t
            db.execute(sa_text("""
                INSERT INTO article_tags (article_id, tag_id)
                SELECT article_id, :keep FROM article_tags WHERE tag_id = :drop
                ON CONFLICT DO NOTHING
            """), {"keep": str(keep.id), "drop": str(drop.id)})
            db.execute(sa_text("DELETE FROM article_tags WHERE tag_id = :drop"), {"drop": str(drop.id)})
            db.execute(sa_text("DELETE FROM tags WHERE id = :drop"), {"drop": str(drop.id)})
        else:
            seen[t.name] = t
    db.flush()

    # Deduplicate source tags against existing tags already in result group
    existing_result_tags = {
        t.name: t for t in db.query(Tag).filter(Tag.tag_group_id == result_group.id).all()
    }
    for name, existing_t in existing_result_tags.items():
        if name in seen:
            drop = seen.pop(name)
            db.execute(sa_text("""
                INSERT INTO article_tags (article_id, tag_id)
                SELECT article_id, :keep FROM article_tags WHERE tag_id = :drop
                ON CONFLICT DO NOTHING
            """), {"keep": str(existing_t.id), "drop": str(drop.id)})
            db.execute(sa_text("DELETE FROM article_tags WHERE tag_id = :drop"), {"drop": str(drop.id)})
            db.execute(sa_text("DELETE FROM tags WHERE id = :drop"), {"drop": str(drop.id)})
    db.flush()

    db.query(Tag).filter(
        Tag.tag_group_id.in_(source_ids)
    ).update({"tag_group_id": result_group.id}, synchronize_session=False)

    for grp in groups_to_delete:
        db.delete(grp)

    db.commit()
    db.refresh(result_group)

    return TagGroupOut(
        id=result_group.id, name=result_group.name, display_name=result_group.display_name,
        description=result_group.description, color_hex=result_group.color_hex,
        topic_id=result_group.topic_id, tags=_tag_outs_for_group(db, result_group),
        similar_groups=[],
    )


@router.post("/tag-groups/reorder", status_code=204)
def reorder_tag_groups(
    body: List[TagGroupReorderItem],
    db: Session = Depends(get_db),
    _: dict = Depends(require_admin),
):
    from models.tag_group import TagGroupDefinition
    for item in body:
        db.query(TagGroupDefinition).filter_by(id=item.id).update({"sort_order": item.sort_order})
    db.commit()


@router.get("/tag-groups/{group_id}", response_model=TagGroupOut)
def get_tag_group(
    group_id: UUID,
    db: Session = Depends(get_db),
):
    from models.tag_group import TagGroupDefinition
    grp = db.query(TagGroupDefinition).filter_by(id=group_id).first()
    if not grp:
        raise HTTPException(status_code=404, detail="Tag group not found")
    return TagGroupOut(id=grp.id, name=grp.name, display_name=grp.display_name,
                       description=grp.description, color_hex=grp.color_hex,
                       topic_id=grp.topic_id, tags=_tag_outs_for_group(db, grp))


@router.put("/tag-groups/{group_id}", response_model=TagGroupOut)
def update_tag_group(
    group_id: UUID,
    body: TagGroupUpdate,
    db: Session = Depends(get_db),
    _: dict = Depends(require_admin),
):
    from models.tag_group import TagGroupDefinition
    grp = db.query(TagGroupDefinition).filter_by(id=group_id).first()
    if not grp:
        raise HTTPException(status_code=404, detail="Tag group not found")
    if body.name is not None and body.name != grp.name:
        existing = db.query(TagGroupDefinition).filter_by(
            name=body.name, topic_id=grp.topic_id
        ).first()
        if existing:
            raise HTTPException(status_code=409, detail="A tag group with this name already exists in this topic")
    for field, val in body.model_dump(exclude_none=True).items():
        setattr(grp, field, val)
    db.commit()
    db.refresh(grp)
    return TagGroupOut(id=grp.id, name=grp.name, display_name=grp.display_name,
                       description=grp.description, color_hex=grp.color_hex,
                       topic_id=grp.topic_id, tags=_tag_outs_for_group(db, grp))


@router.delete("/tag-groups/{group_id}", status_code=204)
def delete_tag_group(
    group_id: UUID,
    db: Session = Depends(get_db),
    _: dict = Depends(require_admin),
):
    from models.tag_group import TagGroupDefinition
    grp = db.query(TagGroupDefinition).filter_by(id=group_id).first()
    if not grp:
        raise HTTPException(status_code=404, detail="Tag group not found")
    db.delete(grp)
    db.commit()


@router.put("/tags/{tag_id}", response_model=TagOut)
def rename_tag(
    tag_id: UUID,
    body: TagUpdate,
    db: Session = Depends(get_db),
    _: dict = Depends(require_admin),
):
    from models.tag import Tag, article_tags as article_tags_table
    tag = db.query(Tag).filter_by(id=tag_id).first()
    if not tag:
        raise HTTPException(status_code=404, detail="Tag not found")
    if body.name is not None:
        tag.name = body.name
    if body.ungroup:
        tag.tag_group_id = None
    elif body.tag_group_id is not None:
        tag.tag_group_id = body.tag_group_id
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="Tag name already exists in target group")
    db.refresh(tag)
    count = (
        db.query(func.count(distinct(article_tags_table.c.article_id)))
        .filter(article_tags_table.c.tag_id == tag.id)
        .scalar()
    ) or 0
    return TagOut(id=tag.id, name=tag.name, article_count=count)


@router.delete("/tags/{tag_id}", status_code=204)
def delete_tag(
    tag_id: UUID,
    db: Session = Depends(get_db),
    _: dict = Depends(require_admin),
):
    from models.tag import Tag
    from sqlalchemy import text
    tag = db.query(Tag).filter_by(id=tag_id).first()
    if not tag:
        raise HTTPException(status_code=404, detail="Tag not found")
    db.execute(text("DELETE FROM article_tags WHERE tag_id = :id"), {"id": str(tag_id)})
    db.delete(tag)
    db.commit()


@router.post("/tags/batch-move", response_model=BatchMoveResult)
def batch_move_tags(
    body: List[TagMoveItem],
    db: Session = Depends(get_db),
    _: dict = Depends(require_admin),
):
    from models.tag import Tag
    succeeded = []
    failed = []
    for item in body:
        try:
            tag = db.query(Tag).filter_by(id=item.tag_id).first()
            if not tag:
                failed.append({"tag_id": str(item.tag_id), "error": "Tag not found"})
                continue
            tag.tag_group_id = item.tag_group_id
            db.commit()
            succeeded.append(str(item.tag_id))
        except Exception as e:
            db.rollback()
            failed.append({"tag_id": str(item.tag_id), "error": str(e)})
    return BatchMoveResult(succeeded=succeeded, failed=failed)


@router.get("/tag-normalization-suggestions", response_model=List[SuggestionOut])
def list_suggestions(
    db: Session = Depends(get_db),
    _: dict = Depends(require_admin),
):
    from models.tag_normalization_suggestion import TagNormalizationSuggestion
    from models.tag import Tag
    rows = db.query(TagNormalizationSuggestion).filter_by(status="pending").all()
    result = []
    for r in rows:
        new_tag = db.query(Tag).filter_by(id=r.new_tag_id).first()
        existing_tag = db.query(Tag).filter_by(id=r.existing_tag_id).first()
        if not new_tag or not existing_tag:
            continue
        result.append(SuggestionOut(
            id=r.id, new_tag_id=r.new_tag_id, new_tag_name=new_tag.name,
            existing_tag_id=r.existing_tag_id, existing_tag_name=existing_tag.name,
            group_name=new_tag.group_def.name if new_tag.group_def else "ungrouped", similarity_score=r.similarity_score,
            article_id=r.article_id,
        ))
    return result


@router.post("/tag-normalization-suggestions/{suggestion_id}/approve", status_code=200)
def approve_suggestion(
    suggestion_id: UUID,
    db: Session = Depends(get_db),
    admin: dict = Depends(require_admin),
):
    from models.tag_normalization_suggestion import TagNormalizationSuggestion
    suggestion = db.query(TagNormalizationSuggestion).filter_by(id=suggestion_id).first()
    if not suggestion:
        raise HTTPException(status_code=404, detail="Suggestion not found")

    new_tag_id = str(suggestion.new_tag_id)
    existing_tag_id = str(suggestion.existing_tag_id)

    db.execute(text("""
        INSERT INTO article_tags (article_id, tag_id)
        SELECT at.article_id, :existing_id
        FROM article_tags at
        INNER JOIN articles a ON a.id = at.article_id
        WHERE at.tag_id = :new_id
        ON CONFLICT DO NOTHING
    """), {"existing_id": existing_tag_id, "new_id": new_tag_id})

    db.execute(text("DELETE FROM article_tags WHERE tag_id = :new_id"), {"new_id": new_tag_id})

    db.expunge(suggestion)
    db.execute(text("DELETE FROM tags WHERE id = :new_id"), {"new_id": new_tag_id})

    db.commit()
    return {"status": "approved"}


@router.post("/tag-normalization-suggestions/{suggestion_id}/reject", status_code=200)
def reject_suggestion(
    suggestion_id: UUID,
    db: Session = Depends(get_db),
    admin: dict = Depends(require_admin),
):
    from models.tag_normalization_suggestion import TagNormalizationSuggestion
    suggestion = db.query(TagNormalizationSuggestion).filter_by(id=suggestion_id).first()
    if not suggestion:
        raise HTTPException(status_code=404, detail="Suggestion not found")
    suggestion.status = "rejected"
    suggestion.resolved_at = datetime.now(timezone.utc)
    suggestion.resolved_by = UUID(admin["sub"])
    db.commit()
    return {"status": "rejected"}
