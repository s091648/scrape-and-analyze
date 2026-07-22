from dataclasses import dataclass
from datetime import date, datetime
from typing import List, Optional
from uuid import UUID

from src.modules.intelligence.domain.exceptions import InvalidWeeklyReportStatusError

_VALID_STATUSES = frozenset({"pending", "completed", "failed"})


@dataclass
class WeeklyReport:
    id: Optional[UUID]
    topic_id: Optional[UUID]
    week_start_date: date
    title: str
    summary_text: str
    cover_image_url: Optional[str]
    article_ids: List[str]
    article_count: int
    status: str  # 'pending' | 'completed' | 'failed'
    error_message: Optional[str] = None
    created_at: Optional[datetime] = None

    def __post_init__(self) -> None:
        if self.status not in _VALID_STATUSES:
            raise InvalidWeeklyReportStatusError(
                f"status must be one of {sorted(_VALID_STATUSES)}, got: {self.status!r}"
            )
