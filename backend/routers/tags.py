from datetime import datetime, timezone
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.auth.guards import require_admin, require_user

router = APIRouter()


# ── Schemas ──────────────────────────────────────────────────────────────────

class TagOut(BaseModel):
    id: UUID
    name: str
    article_count: int

    class Config:
        from_attributes = True


class TagGroupOut(BaseModel):
    id: UUID
    name: str
    display_name: str
    description: Optional[str]
    color_hex: Optional[str]
    topic_id: UUID
    tags: List[TagOut]

    class Config:
        from_attributes = True


class TagGroupCreate(BaseModel):
    name: str
    display_name: str
    color_hex: Optional[str] = None
    topic_id: UUID
    description: Optional[str] = None
    sort_order: Optional[int] = None


class TagGroupUpdate(BaseModel):
    display_name: Optional[str] = None
    color_hex: Optional[str] = None
    description: Optional[str] = None
    sort_order: Optional[int] = None


class TagUpdate(BaseModel):
    name: Optional[str] = None
    tag_group_name: Optional[str] = None


class TagMoveItem(BaseModel):
    tag_id: UUID
    tag_group_name: str


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


# ── Helpers ──────────────────────────────────────────────────────────────────

def _tag_article_count(db: Session, tag_id: UUID) -> int:
    from sqlalchemy import text
    row = db.execute(
        text("""
            SELECT COUNT(*) FROM article_tags at
            INNER JOIN articles a ON a.id = at.article_id
            WHERE at.tag_id = :id
        """),
        {"id": str(tag_id)},
    ).fetchone()
    return row[0] if row else 0


# ── Routes ───────────────────────────────────────────────────────────────────

@router.get("/tag-groups", response_model=List[TagGroupOut])
def list_tag_groups(
    topic_id: Optional[UUID] = Query(default=None),
    db: Session = Depends(get_db),
):
    from models.tag_group import TagGroupDefinition
    from models.tag import Tag

    query = db.query(TagGroupDefinition)
    if topic_id:
        query = query.filter(TagGroupDefinition.topic_id == topic_id)
    groups = query.order_by(TagGroupDefinition.sort_order, TagGroupDefinition.display_name).all()

    result = []
    for grp in groups:
        tags = db.query(Tag).filter_by(tag_group_name=grp.name).order_by(Tag.name).all()
        tag_outs = [
            TagOut(id=t.id, name=t.name, article_count=_tag_article_count(db, t.id))
            for t in tags
        ]
        result.append(TagGroupOut(
            id=grp.id, name=grp.name, display_name=grp.display_name,
            description=grp.description, color_hex=grp.color_hex,
            topic_id=grp.topic_id, tags=tag_outs,
        ))
    return result


@router.post("/tag-groups", response_model=TagGroupOut, status_code=201)
def create_tag_group(
    body: TagGroupCreate,
    db: Session = Depends(get_db),
    _: dict = Depends(require_admin),
):
    from models.tag_group import TagGroupDefinition
    grp = TagGroupDefinition(**body.model_dump())
    db.add(grp)
    db.commit()
    db.refresh(grp)
    return TagGroupOut(id=grp.id, name=grp.name, display_name=grp.display_name,
                       description=grp.description, color_hex=grp.color_hex,
                       topic_id=grp.topic_id, tags=[])


@router.put("/tag-groups/{group_id}", response_model=TagGroupOut)
def update_tag_group(
    group_id: UUID,
    body: TagGroupUpdate,
    db: Session = Depends(get_db),
    _: dict = Depends(require_admin),
):
    from models.tag_group import TagGroupDefinition
    from models.tag import Tag
    grp = db.query(TagGroupDefinition).filter_by(id=group_id).first()
    if not grp:
        raise HTTPException(status_code=404, detail="Tag group not found")
    for field, val in body.model_dump(exclude_none=True).items():
        setattr(grp, field, val)
    db.commit()
    db.refresh(grp)
    tags = db.query(Tag).filter_by(tag_group_name=grp.name).order_by(Tag.name).all()
    tag_outs = [TagOut(id=t.id, name=t.name, article_count=_tag_article_count(db, t.id)) for t in tags]
    return TagGroupOut(id=grp.id, name=grp.name, display_name=grp.display_name,
                       description=grp.description, color_hex=grp.color_hex,
                       topic_id=grp.topic_id, tags=tag_outs)


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
    from models.tag import Tag
    tag = db.query(Tag).filter_by(id=tag_id).first()
    if not tag:
        raise HTTPException(status_code=404, detail="Tag not found")
    if body.name is not None:
        tag.name = body.name
    if body.tag_group_name is not None:
        tag.tag_group_name = body.tag_group_name
    db.commit()
    db.refresh(tag)
    return TagOut(id=tag.id, name=tag.name, article_count=_tag_article_count(db, tag.id))


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
            tag.tag_group_name = item.tag_group_name
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
            group_name=new_tag.tag_group_name, similarity_score=r.similarity_score,
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

    # Expunge before deleting the tag — new_tag_id FK has ondelete=CASCADE which
    # would also delete this suggestion row, causing a StaleDataError if SQLAlchemy
    # still holds a reference to it.
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
