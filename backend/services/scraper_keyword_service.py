from typing import Optional
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy.orm import Session


def list_keywords(db: Session, topic_id: UUID, keyword_type: Optional[str] = None) -> list:
    from models.scraper_keyword import ScraperKeyword
    q = db.query(ScraperKeyword).filter_by(topic_id=topic_id)
    if keyword_type is not None:
        q = q.filter_by(keyword_type=keyword_type)
    return q.order_by(ScraperKeyword.created_at).all()


def create_keyword(db: Session, topic_id: UUID, keyword_type: str, keyword: str):
    from models.scraper_keyword import ScraperKeyword
    if db.query(ScraperKeyword).filter_by(
        topic_id=topic_id, keyword_type=keyword_type, keyword=keyword
    ).first():
        raise HTTPException(status_code=409, detail="Keyword already exists")
    row = ScraperKeyword(topic_id=topic_id, keyword_type=keyword_type, keyword=keyword)
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def delete_keyword(db: Session, keyword_id: UUID) -> bool:
    from models.scraper_keyword import ScraperKeyword
    row = db.query(ScraperKeyword).filter_by(id=keyword_id).first()
    if not row:
        return False
    db.delete(row)
    db.commit()
    return True
