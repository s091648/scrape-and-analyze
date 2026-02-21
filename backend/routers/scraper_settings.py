from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.auth.guards import require_admin
from backend.schemas.scraper_setting import ScraperSettingCreate, ScraperSettingUpdate, ScraperSettingOut

router = APIRouter(prefix="/scraper-settings", tags=["scraper-settings"])


def get_all_settings(db: Session):
    from backend.models.scraper_setting import ScraperSetting
    return db.query(ScraperSetting).all()


def create_setting(db: Session, data: ScraperSettingCreate):
    from backend.models.scraper_setting import ScraperSetting
    obj = ScraperSetting(**data.model_dump())
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj


def update_setting(db: Session, setting_id: UUID, data: ScraperSettingUpdate):
    from backend.models.scraper_setting import ScraperSetting
    obj = db.query(ScraperSetting).filter(ScraperSetting.id == setting_id).first()
    if not obj:
        return None
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(obj, field, value)
    db.commit()
    db.refresh(obj)
    return obj


def delete_setting(db: Session, setting_id: UUID) -> bool:
    from backend.models.scraper_setting import ScraperSetting
    obj = db.query(ScraperSetting).filter(ScraperSetting.id == setting_id).first()
    if not obj:
        return False
    db.delete(obj)
    db.commit()
    return True


@router.get("", response_model=list[ScraperSettingOut])
def list_settings(db: Session = Depends(get_db), _=Depends(require_admin)):
    return get_all_settings(db)


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
