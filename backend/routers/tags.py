from datetime import datetime, timezone
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import func, distinct, text
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


class SimilarGroupOut(BaseModel):
    id: UUID
    similarity_score: float


class TagGroupOut(BaseModel):
    id: UUID
    name: str
    display_name: str
    description: Optional[str]
    color_hex: Optional[str]
    topic_id: UUID
    tags: List[TagOut]
    similar_groups: List[SimilarGroupOut] = []

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


def _similar_groups(db: Session, group_id: UUID, topic_id: UUID, threshold: float = 0.80) -> List[SimilarGroupOut]:
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


# ── Routes ───────────────────────────────────────────────────────────────────

@router.get("/tag-groups", response_model=List[TagGroupOut])
def list_tag_groups(
    topic_id: Optional[UUID] = Query(default=None),
    include_similarity: bool = Query(default=False),
    db: Session = Depends(get_db),
):
    # ... (existing group query unchanged) ...

    result = []
    for grp in groups:
        # ... (existing tag_outs logic unchanged) ...

        similar = (
            _similar_groups(db, grp.id, grp.topic_id)
            if include_similarity and topic_id
            else []
        )
        result.append(TagGroupOut(
            id=grp.id, name=grp.name, display_name=grp.display_name,
            description=grp.description, color_hex=grp.color_hex,
            topic_id=grp.topic_id, tags=tag_outs,
            similar_groups=similar,
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

    embed_text = f"{grp.name} - {grp.display_name}. {grp.description or ''}"
    vec = _embed_text(embed_text)
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


@router.put("/tag-groups/{group_id}", response_model=TagGroupOut)
def update_tag_group(
    group_id: UUID,
    body: TagGroupUpdate,
    db: Session = Depends(get_db),
    _: dict = Depends(require_admin),
):
    from models.tag_group import TagGroupDefinition
    from models.tag import Tag, article_tags as article_tags_table
    from models.article import Article
    grp = db.query(TagGroupDefinition).filter_by(id=group_id).first()
    if not grp:
        raise HTTPException(status_code=404, detail="Tag group not found")
    for field, val in body.model_dump(exclude_none=True).items():
        setattr(grp, field, val)
    db.commit()
    db.refresh(grp)
    rows = (
        db.query(Tag.id, Tag.name, func.count(distinct(article_tags_table.c.article_id)).label("article_count"))
        .join(article_tags_table, article_tags_table.c.tag_id == Tag.id)
        .join(Article, Article.id == article_tags_table.c.article_id)
        .filter(Tag.tag_group_name == grp.name, Article.topic_id == grp.topic_id)
        .group_by(Tag.id, Tag.name)
        .order_by(Tag.name)
        .all()
    )
    tag_outs = [TagOut(id=r.id, name=r.name, article_count=r.article_count) for r in rows]
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
    from models.tag import Tag, article_tags as article_tags_table
    tag = db.query(Tag).filter_by(id=tag_id).first()
    if not tag:
        raise HTTPException(status_code=404, detail="Tag not found")
    if body.name is not None:
        tag.name = body.name
    if body.tag_group_name is not None:
        tag.tag_group_name = body.tag_group_name
    db.commit()
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
