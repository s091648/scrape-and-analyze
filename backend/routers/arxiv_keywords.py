from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.auth.guards import require_admin
from backend.schemas.arxiv_keyword import ArxivKeywordCreate, ArxivKeywordOut

router = APIRouter(prefix="/arxiv-keywords", tags=["arxiv-keywords"])


@router.get("", response_model=list[ArxivKeywordOut])
def list_keywords(db: Session = Depends(get_db), _=Depends(require_admin)):
    from models.arxiv_keyword import ArxivKeyword
    return db.query(ArxivKeyword).order_by(ArxivKeyword.created_at).all()


@router.post("", response_model=ArxivKeywordOut, status_code=201)
def create_keyword(data: ArxivKeywordCreate, db: Session = Depends(get_db), _=Depends(require_admin)):
    from models.arxiv_keyword import ArxivKeyword
    existing = db.query(ArxivKeyword).filter(ArxivKeyword.keyword == data.keyword).first()
    if existing:
        raise HTTPException(status_code=409, detail="Keyword already exists")
    obj = ArxivKeyword(keyword=data.keyword)
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj


@router.delete("/{keyword_id}", status_code=204)
def delete_keyword(keyword_id: UUID, db: Session = Depends(get_db), _=Depends(require_admin)):
    from models.arxiv_keyword import ArxivKeyword
    obj = db.query(ArxivKeyword).filter(ArxivKeyword.id == keyword_id).first()
    if not obj:
        raise HTTPException(status_code=404, detail="Keyword not found")
    db.delete(obj)
    db.commit()
    return Response(status_code=204)
