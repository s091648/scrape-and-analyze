from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.auth.guards import require_admin
from backend.schemas.scraper_setting import ScraperSettingCreate, ScraperSettingUpdate, ScraperSettingOut
from backend.services.scraper_settings_service import (
    get_all_settings,
    create_setting,
    update_setting,
    delete_setting,
)

router = APIRouter(prefix="/scraper-settings", tags=["scraper-settings"])


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
    if not delete_setting(db, setting_id):
        raise HTTPException(status_code=404, detail="Setting not found")
    return Response(status_code=204)
