from datetime import datetime, timezone, timedelta
from typing import Optional
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified

from backend.schemas.scraper_setting import ScraperSettingCreate, ScraperSettingUpdate

_ACTIVITY_SQL = text("""
    SELECT topic_id, source, DATE(scraped_at AT TIME ZONE 'UTC') AS day, COUNT(*) AS cnt
    FROM articles
    WHERE scraped_at >= NOW() - INTERVAL '14 days'
    GROUP BY topic_id, source, day
""")

# These scrapers write a fixed literal to articles.source regardless of the
# ScraperSetting's (user-editable) display name, and each topic has at most one
# setting of each type — so the activity join must key on source_type, not name.
# RSS/Blog settings write setting.name as articles.source instead (one row per
# distinct feed), so those must keep keying on name.
_SINGLETON_SOURCE_TYPES = {'arxiv', 'semantic_scholar', 'openalex'}


def _activity_key(setting) -> tuple:
    join_value = setting.source_type if setting.source_type in _SINGLETON_SOURCE_TYPES else setting.name
    return (setting.topic_id, join_value)


def get_all_settings(db: Session, topic_id: Optional[UUID] = None):
    from models.scraper_setting import ScraperSetting

    q = db.query(ScraperSetting)
    if topic_id is not None:
        q = q.filter(ScraperSetting.topic_id == topic_id)
    settings = q.all()

    today = datetime.now(timezone.utc).date()
    cutoff = today - timedelta(days=13)
    activity_map: dict[tuple, list[int]] = {_activity_key(s): [0] * 14 for s in settings}

    for row in db.execute(_ACTIVITY_SQL):
        key = (row.topic_id, row.source)
        if key in activity_map:
            offset = (row.day - cutoff).days
            if 0 <= offset <= 13:
                activity_map[key][offset] = int(row.cnt)

    for s in settings:
        s.activity = activity_map.get(_activity_key(s), [0] * 14)

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
        if field == 'selector_config' and value is not None:
            existing = {}
            raw = obj.selector_config
            if isinstance(raw, dict):
                existing = raw
            elif raw is not None and hasattr(raw, 'model_dump'):
                existing = raw.model_dump()
            existing.update(value)
            obj.selector_config = existing
            flag_modified(obj, 'selector_config')
        else:
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
