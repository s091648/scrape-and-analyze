import uuid
from collections import Counter
from datetime import date
from typing import List, Optional
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.orm import Session

from src.modules.intelligence.domain.entities.weekly_report import WeeklyReport
from src.modules.intelligence.domain.repositories.weekly_report_repository import WeeklyReportRepository
from src.modules.intelligence.domain.value_objects.article_summary_for_report import ArticleSummaryForReport


class WeeklyReportRepoImpl(WeeklyReportRepository):
    def __init__(self, session: Session) -> None:
        self._session = session

    def fetch_top_articles(self, topic_id: UUID, week_start: date, limit: int = 20) -> List[ArticleSummaryForReport]:
        week_end = date(week_start.year, week_start.month, week_start.day)
        sql = text("""
            SELECT
                a.title,
                at2.pain_points,
                at2.insights,
                at2.innovations,
                at2.summary,
                am.citation_count,
                am.view_count,
                a.published_at,
                COALESCE(am.citation_count, 0) AS sort_citations,
                COALESCE(am.view_count, 0) AS sort_views
            FROM articles a
            LEFT JOIN article_metrics am ON am.article_id = a.id
            LEFT JOIN (
                SELECT DISTINCT ON (an.article_id) an.article_id, ant.pain_points, ant.insights, ant.innovations, ant.summary
                FROM analyses an
                LEFT JOIN analyses_translation ant ON ant.analysis_id = an.id AND ant.language = 'en'
                ORDER BY an.article_id, an.created_at DESC
            ) at2 ON at2.article_id = a.id
            WHERE a.topic_id = :topic_id
              AND a.scraped_at >= :week_start
            ORDER BY sort_citations DESC, sort_views DESC, a.published_at DESC NULLS LAST
            LIMIT :limit
        """)
        rows = self._session.execute(sql, {
            "topic_id": str(topic_id),
            "week_start": week_start,
            "limit": limit,
        }).fetchall()

        article_ids_for_tags = []
        from models.article import Article
        tag_sql = text("""
            SELECT at2.article_id, t.name
            FROM article_tags at2
            JOIN tags t ON t.id = at2.tag_id
            WHERE at2.article_id IN (
                SELECT a.id FROM articles a
                WHERE a.topic_id = :topic_id AND a.scraped_at >= :week_start
                ORDER BY (COALESCE((SELECT am.citation_count FROM article_metrics am WHERE am.article_id = a.id), 0)) DESC
                LIMIT :limit
            )
        """)
        tag_rows = self._session.execute(tag_sql, {
            "topic_id": str(topic_id),
            "week_start": week_start,
            "limit": limit,
        }).fetchall()
        tags_by_title: dict = {}
        for row in tag_rows:
            tags_by_title.setdefault(str(row[0]), []).append(row[1])

        results = []
        for row in rows:
            results.append(ArticleSummaryForReport(
                title=row[0] or "",
                summary=row[4],
                pain_points=row[1],
                insights=row[2],
                innovations=row[3],
                citation_count=row[5],
                view_count=row[6] or 0,
                published_at=row[7],
            ))
        return results

    def save(self, report: WeeklyReport) -> WeeklyReport:
        from models.weekly_report import WeeklyReport as WeeklyReportModel
        import json

        existing = (
            self._session.query(WeeklyReportModel)
            .filter(
                WeeklyReportModel.topic_id == report.topic_id,
                WeeklyReportModel.week_start_date == report.week_start_date,
            )
            .first()
        )
        if existing:
            existing.title = report.title
            existing.summary_text = report.summary_text
            existing.cover_image_url = report.cover_image_url
            existing.article_ids = report.article_ids
            existing.article_count = report.article_count
            existing.status = report.status
            existing.error_message = report.error_message
            self._session.commit()
            report.id = existing.id
        else:
            orm_obj = WeeklyReportModel(
                id=report.id or uuid.uuid4(),
                topic_id=report.topic_id,
                week_start_date=report.week_start_date,
                title=report.title,
                summary_text=report.summary_text,
                cover_image_url=report.cover_image_url,
                article_ids=report.article_ids,
                article_count=report.article_count,
                status=report.status,
                error_message=report.error_message,
            )
            self._session.add(orm_obj)
            self._session.commit()
            report.id = orm_obj.id
        return report

    def get_latest(self, topic_id: UUID) -> Optional[WeeklyReport]:
        from models.weekly_report import WeeklyReport as WeeklyReportModel
        row = (
            self._session.query(WeeklyReportModel)
            .filter(
                WeeklyReportModel.topic_id == topic_id,
                WeeklyReportModel.status == "completed",
            )
            .order_by(WeeklyReportModel.week_start_date.desc())
            .first()
        )
        if not row:
            return None
        return WeeklyReport(
            id=row.id,
            topic_id=row.topic_id,
            week_start_date=row.week_start_date,
            title=row.title,
            summary_text=row.summary_text,
            cover_image_url=row.cover_image_url,
            article_ids=row.article_ids or [],
            article_count=row.article_count,
            status=row.status,
            error_message=row.error_message,
            created_at=row.created_at,
        )
