from datetime import datetime, timezone, timedelta
from typing import Optional
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy import text
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.auth.guards import require_admin
from backend.schemas.scraper_setting import ScraperSettingCreate, ScraperSettingUpdate, ScraperSettingOut

router = APIRouter(prefix="/scraper-settings", tags=["scraper-settings"])

_ACTIVITY_SQL = text("""
    SELECT source, DATE(scraped_at AT TIME ZONE 'UTC') AS day, COUNT(*) AS cnt
    FROM articles
    WHERE scraped_at >= NOW() - INTERVAL '14 days'
    GROUP BY source, day
""")


def get_all_settings(db: Session, topic_id: Optional[UUID] = None):
    from models.scraper_setting import ScraperSetting

    q = db.query(ScraperSetting)
    if topic_id is not None:
        q = q.filter(ScraperSetting.topic_id == topic_id)
    settings = q.all()

    # Build per-name activity arrays (14 slots, index 0 = 14 days ago, 13 = today)
    today = datetime.now(timezone.utc).date()
    cutoff = today - timedelta(days=13)
    activity_map: dict[str, list[int]] = {s.name: [0] * 14 for s in settings}

    for row in db.execute(_ACTIVITY_SQL):
        if row.source in activity_map:
            offset = (row.day - cutoff).days
            if 0 <= offset <= 13:
                activity_map[row.source][offset] = int(row.cnt)

    for s in settings:
        s.activity = activity_map.get(s.name, [0] * 14)

    return settings


def create_setting(db: Session, data: ScraperSettingCreate):
    from models.scraper_setting import ScraperSetting
    obj = ScraperSetting(**data.model_dump())
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj


def update_setting(db: Session, setting_id: UUID, data: ScraperSettingUpdate):
    from models.scraper_setting import ScraperSetting
    obj = db.query(ScraperSetting).filter(ScraperSetting.id == setting_id).first()
    if not obj:
        return None
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(obj, field, value)
    db.commit()
    db.refresh(obj)
    return obj


def delete_setting(db: Session, setting_id: UUID) -> bool:
    from models.scraper_setting import ScraperSetting
    obj = db.query(ScraperSetting).filter(ScraperSetting.id == setting_id).first()
    if not obj:
        return False
    db.delete(obj)
    db.commit()
    return True


@router.get("", response_model=list[ScraperSettingOut])
def list_settings(
    topic_id: Optional[UUID] = Query(None),
    db: Session = Depends(get_db),
    _=Depends(require_admin),
):
    return get_all_settings(db, topic_id=topic_id)


@router.post("", response_model=ScraperSettingOut, status_code=201)
def create(data: ScraperSettingCreate, db: Session = Depends(get_db), _=Depends(require_admin)):
    return create_setting(db, data)


@router.patch("/{setting_id}", response_model=ScraperSettingOut)
def update(setting_id: UUID, data: ScraperSettingUpdate, db: Session = Depends(get_db),
           _=Depends(require_admin)):
    obj = update_setting(db, setting_id, data)
    if not obj:
        raise HTTPException(status_code=404, detail="Setting not found")
    return obj


@router.delete("/{setting_id}", status_code=204)
def delete(setting_id: UUID, db: Session = Depends(get_db), _=Depends(require_admin)):
    deleted = delete_setting(db, setting_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Setting not found")
    return Response(status_code=204)
