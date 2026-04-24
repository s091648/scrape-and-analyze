from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import UUID, uuid4


@dataclass
class ScraperSetting:
    source: str
    source_type: str
    url: str
    interval_hours: int
    id: UUID = field(default_factory=uuid4)
    topic_id: Optional[UUID] = None
    prompt_override: Optional[str] = None
    selector_config: Dict[str, Any] = field(default_factory=dict)
    keywords: Optional[List[str]] = None
    last_scraped_at: Optional[datetime] = None
    is_active: bool = True

    def is_due(self, now: Optional[datetime] = None) -> bool:
        """Return True if this source has never been scraped or its interval has elapsed."""
        if not self.last_scraped_at:
            return True
        reference = now or datetime.now(timezone.utc)
        elapsed = (reference - self.last_scraped_at).total_seconds()
        return elapsed >= self.interval_hours * 3600
