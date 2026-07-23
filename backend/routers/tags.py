from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy import func, distinct, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from src.shared.domain.exceptions import NotFoundError, ConflictError
from backend.database import get_db
from backend.auth.guards import require_admin, require_user, require_any_token
from backend.schemas.error import error_responses
from backend.schemas.tag import (
    TagOut,
    TagGroupOut,
    TagGroupCreate,
    TagGroupUpdate,
    TagUpdate,
    TagMoveItem,
    BatchMoveResult,
    SuggestionOut,
    TagGroupMergeRequest,
    TagGroupReorderItem,
)
from backend.services.tag_service import (
    embed_text,
    get_similar_groups,
    tag_outs_for_group,
    ungrouped_tag_outs,
    merge_tag_groups,
)

router = APIRouter(tags=["tags"])


@router.get("/tag-groups", response_model=List[TagGroupOut], responses=error_responses(401))
def list_tag_groups(
    topic_id: Optional[UUID] = Query(default=None),
    include_similarity: bool = Query(default=False),
    db: Session = Depends(get_db),
    _token: dict = Depends(require_any_token),
):
    from models.tag_group import TagGroupDefinition

    q = db.query(TagGroupDefinition)
    if topic_id:
        q = q.filter(TagGroupDefinition.topic_id == topic_id)
    groups = q.order_by(TagGroupDefinition.sort_order, TagGroupDefinition.name).all()

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
            topic_id=grp.topic_id, tags=tag_outs_for_group(db, grp),
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

    return result


@router.post("/tag-groups", response_model=TagGroupOut, status_code=201, responses=error_responses(401, 403))
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

    vec = embed_text(grp.name)
    if vec is not None:
        vec_str = "[" + ",".join(str(x) for x in vec) + "]"
        db.execute(
            sa_text("UPDATE tag_group_definitions SET embedding = CAST(:vec AS vector) WHERE id = :id"),
            {"vec": vec_str, "id": str(grp.id)},
        )
        db.commit()

    return TagGroupOut(
        id=grp.id, name=grp.name, display_name=grp.display_name,
        description=grp.description, color_hex=grp.color_hex,
        topic_id=grp.topic_id, tags=[],
    )


@router.post("/tag-groups/merge", response_model=TagGroupOut, responses=error_responses(401, 403))
def merge_tag_groups_endpoint(
    body: TagGroupMergeRequest,
    db: Session = Depends(get_db),
    _: dict = Depends(require_admin),
):
    result_group = merge_tag_groups(
        db,
        body.group_a_id, body.group_b_id,
        body.result_name, body.result_display_name,
        body.result_color_hex, body.result_description,
    )
    return TagGroupOut(
        id=result_group.id, name=result_group.name, display_name=result_group.display_name,
        description=result_group.description, color_hex=result_group.color_hex,
        topic_id=result_group.topic_id, tags=tag_outs_for_group(db, result_group),
        similar_groups=[],
    )


@router.post("/tag-groups/reorder", status_code=204, responses=error_responses(401, 403))
def reorder_tag_groups(
    body: List[TagGroupReorderItem],
    db: Session = Depends(get_db),
    _: dict = Depends(require_admin),
):
    from models.tag_group import TagGroupDefinition
    for item in body:
        db.query(TagGroupDefinition).filter_by(id=item.id).update({"sort_order": item.sort_order})
    db.commit()


@router.get("/tag-groups/{group_id}", response_model=TagGroupOut, responses=error_responses(401, 404))
def get_tag_group(group_id: UUID, db: Session = Depends(get_db), _token: dict = Depends(require_any_token)):
    from models.tag_group import TagGroupDefinition
    grp = db.query(TagGroupDefinition).filter_by(id=group_id).first()
    if not grp:
        raise NotFoundError("Tag group not found")
    return TagGroupOut(
        id=grp.id, name=grp.name, display_name=grp.display_name,
        description=grp.description, color_hex=grp.color_hex,
        topic_id=grp.topic_id, tags=tag_outs_for_group(db, grp),
    )


@router.put("/tag-groups/{group_id}", response_model=TagGroupOut, responses=error_responses(401, 403, 404, 409))
def update_tag_group(
    group_id: UUID,
    body: TagGroupUpdate,
    db: Session = Depends(get_db),
    _: dict = Depends(require_admin),
):
    from models.tag_group import TagGroupDefinition
    grp = db.query(TagGroupDefinition).filter_by(id=group_id).first()
    if not grp:
        raise NotFoundError("Tag group not found")
    if body.name is not None and body.name != grp.name:
        existing = db.query(TagGroupDefinition).filter_by(
            name=body.name, topic_id=grp.topic_id
        ).first()
        if existing:
            raise ConflictError("A tag group with this name already exists in this topic")
    for field, val in body.model_dump(exclude_none=True).items():
        setattr(grp, field, val)
    db.commit()
    db.refresh(grp)
    return TagGroupOut(
        id=grp.id, name=grp.name, display_name=grp.display_name,
        description=grp.description, color_hex=grp.color_hex,
        topic_id=grp.topic_id, tags=tag_outs_for_group(db, grp),
    )


@router.delete("/tag-groups/{group_id}", status_code=204, responses=error_responses(401, 403, 404))
def delete_tag_group(
    group_id: UUID,
    db: Session = Depends(get_db),
    _: dict = Depends(require_admin),
):
    from models.tag_group import TagGroupDefinition
    grp = db.query(TagGroupDefinition).filter_by(id=group_id).first()
    if not grp:
        raise NotFoundError("Tag group not found")
    db.delete(grp)
    db.commit()


@router.put("/tags/{tag_id}", response_model=TagOut, responses=error_responses(401, 403, 404, 409))
def rename_tag(
    tag_id: UUID,
    body: TagUpdate,
    db: Session = Depends(get_db),
    _: dict = Depends(require_admin),
):
    from models.tag import Tag, article_tags as article_tags_table
    tag = db.query(Tag).filter_by(id=tag_id).first()
    if not tag:
        raise NotFoundError("Tag not found")
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
        raise ConflictError("Tag name already exists in target group")
    db.refresh(tag)
    count = (
        db.query(func.count(distinct(article_tags_table.c.article_id)))
        .filter(article_tags_table.c.tag_id == tag.id)
        .scalar()
    ) or 0
    return TagOut(id=tag.id, name=tag.name, article_count=count)


@router.delete("/tags/{tag_id}", status_code=204, responses=error_responses(401, 403, 404))
def delete_tag(
    tag_id: UUID,
    db: Session = Depends(get_db),
    _: dict = Depends(require_admin),
):
    from models.tag import Tag
    tag = db.query(Tag).filter_by(id=tag_id).first()
    if not tag:
        raise NotFoundError("Tag not found")
    db.execute(text("DELETE FROM article_tags WHERE tag_id = :id"), {"id": str(tag_id)})
    db.delete(tag)
    db.commit()


@router.post("/tags/batch-move", response_model=BatchMoveResult, responses=error_responses(401, 403))
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


@router.get("/tag-normalization-suggestions", response_model=List[SuggestionOut], responses=error_responses(401, 403))
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
            group_name=new_tag.group_def.name if new_tag.group_def else "ungrouped",
            similarity_score=r.similarity_score,
            article_id=r.article_id,
        ))
    return result


@router.post("/tag-normalization-suggestions/{suggestion_id}/approve", status_code=200, responses=error_responses(401, 403, 404))
def approve_suggestion(
    suggestion_id: UUID,
    db: Session = Depends(get_db),
    admin: dict = Depends(require_admin),
):
    from models.tag_normalization_suggestion import TagNormalizationSuggestion
    suggestion = db.query(TagNormalizationSuggestion).filter_by(id=suggestion_id).first()
    if not suggestion:
        raise NotFoundError("Suggestion not found")

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


@router.post("/tag-normalization-suggestions/{suggestion_id}/reject", status_code=200, responses=error_responses(401, 403, 404))
def reject_suggestion(
    suggestion_id: UUID,
    db: Session = Depends(get_db),
    admin: dict = Depends(require_admin),
):
    from datetime import datetime, timezone
    from models.tag_normalization_suggestion import TagNormalizationSuggestion
    suggestion = db.query(TagNormalizationSuggestion).filter_by(id=suggestion_id).first()
    if not suggestion:
        raise NotFoundError("Suggestion not found")
    suggestion.status = "rejected"
    suggestion.resolved_at = datetime.now(timezone.utc)
    suggestion.resolved_by = UUID(admin["sub"])
    db.commit()
    return {"status": "rejected"}
