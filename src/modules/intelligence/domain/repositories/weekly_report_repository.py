from abc import ABC, abstractmethod
from datetime import date
from typing import List, Optional
from uuid import UUID

from src.modules.intelligence.domain.entities.weekly_report import WeeklyReport
from src.modules.intelligence.domain.value_objects.article_summary_for_report import ArticleSummaryForReport


class WeeklyReportRepository(ABC):
    @abstractmethod
    def fetch_top_articles(self, topic_id: UUID, week_start: date, limit: int = 20) -> List[ArticleSummaryForReport]:
        """Fetch top articles for report using COALESCE(citation_count,0) DESC, view_count DESC, published_at DESC."""

    @abstractmethod
    def save(self, report: WeeklyReport) -> WeeklyReport:
        """Upsert a WeeklyReport. Returns saved entity with id populated."""

    @abstractmethod
    def get_latest(self, topic_id: UUID) -> Optional[WeeklyReport]:
        """Return the most recent completed report for a topic, or None."""
