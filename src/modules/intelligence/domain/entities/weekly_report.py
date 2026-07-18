from dataclasses import dataclass
from datetime import date, datetime
from typing import List, Optional
from uuid import UUID


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
