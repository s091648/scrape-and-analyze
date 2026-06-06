from typing import List, Optional
from uuid import UUID

from src.modules.collection.domain.entities import ScraperSetting
from src.modules.collection.domain.repositories import ScraperSettingRepository
from src.shared.logging import get_logger

logger = get_logger(__name__)

# 30-minute tolerance window: a source with frequency=24h fires when >=23.5h have elapsed.
# This prevents cron jitter from causing a source to be skipped if the previous run
# finished slightly late (e.g. 23h 55m elapsed instead of exactly 24h).
# We intentionally avoid "frequency - 1h" because that breaks sources with frequency=1h.
_TOLERANCE_MINUTES = 30


class SqlAlchemyScraperSettingRepository(ScraperSettingRepository):

    def __init__(self, session) -> None:
        self._session = session

    def get_active_due(self) -> List[ScraperSetting]:
        from models.scraper_setting import ScraperSetting as ScraperSettingModel
        from sqlalchemy import or_, func

        # Filter at the DB level: active AND (never scraped OR enough time has elapsed).
        # func.make_interval() is PostgreSQL-specific but avoids raw text() and
        # integrates with SQLAlchemy's expression layer (type-checked, composable).
        # The app already commits to PostgreSQL via JSONB/UUID dialect usage.
        rows = (
            self._session.query(ScraperSettingModel)
            .filter(
                ScraperSettingModel.is_active == True,  # noqa: E712
                or_(
                    ScraperSettingModel.last_scraped_at.is_(None),
                    func.now() - ScraperSettingModel.last_scraped_at
                    > func.make_interval(0, 0, 0, 0, ScraperSettingModel.frequency, 0, 0)
                    - func.make_interval(0, 0, 0, 0, 0, _TOLERANCE_MINUTES, 0),
                ),
            )
            .all()
        )

        return [self._to_entity(row) for row in rows]

    def mark_scraped(self, setting_id: UUID) -> None:
        from models.scraper_setting import ScraperSetting as ScraperSettingModel
        from datetime import datetime, timezone

        row = self._session.query(ScraperSettingModel).filter_by(id=setting_id).first()
        if row:
            row.last_scraped_at = datetime.now(timezone.utc)
            try:
                self._session.commit()
            except Exception:
                self._session.rollback()
                raise

    def _to_entity(self, row) -> ScraperSetting:
        # prompt_override lives on the related Topic, not on ScraperSetting itself.
        # Resolve it here to keep the entity self-contained.
        prompt_override: Optional[str] = None
        if row.topic_id:
            from models.topic import Topic as TopicModel
            topic = self._session.query(TopicModel).filter_by(id=row.topic_id).first()
            if topic:
                prompt_override = topic.prompt_override

        # Keyword items are topic-scoped: shared by all scrapers for the same topic.
        # Each row is typed (rss | arxiv_keyword | arxiv_category) via keyword_type.
        from models.scraper_keyword import ScraperKeyword as ScraperKeywordModel
        from src.modules.collection.domain.value_objects import build_scraper_keyword
        keyword_rows = (
            self._session.query(ScraperKeywordModel)
            .filter_by(topic_id=row.topic_id)
            .order_by(ScraperKeywordModel.created_at)
            .all()
        )
        keyword_items = (
            [build_scraper_keyword(k.keyword_type, k.keyword) for k in keyword_rows]
            if keyword_rows else None
        )

        # selector_config may be a typed SelectorConfig (new data with 'type' field),
        # a raw dict (legacy data), or None. build_selector_config() handles all cases.
        from src.modules.collection.domain.value_objects import (
            build_selector_config,
            RssConfig, BlogConfig, ArxivConfig, SemanticScholarConfig, OpenAlexConfig,
        )
        raw_cfg = row.selector_config
        if isinstance(raw_cfg, (RssConfig, BlogConfig, ArxivConfig, SemanticScholarConfig, OpenAlexConfig)):
            selector_config = raw_cfg
        else:
            selector_config = build_selector_config(row.source_type, raw_cfg)

        return ScraperSetting(
            id=row.id,
            source=row.name,               # ORM: name → entity: source
            source_type=row.source_type,
            url=row.url,
            interval_hours=row.frequency,  # ORM: frequency → entity: interval_hours
            topic_id=row.topic_id,
            prompt_override=prompt_override,
            selector_config=selector_config,
            keyword_items=keyword_items,
            last_scraped_at=row.last_scraped_at,
            is_active=row.is_active,
        )
