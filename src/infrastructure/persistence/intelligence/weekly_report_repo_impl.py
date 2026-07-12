import uuid
from datetime import date, timedelta
from typing import Dict, List, Optional
from uuid import UUID

from sqlalchemy import func
from sqlalchemy.orm import Session

from src.modules.intelligence.domain.entities.weekly_report import WeeklyReport
from src.modules.intelligence.domain.repositories.weekly_report_repository import WeeklyReportRepository
from src.modules.intelligence.domain.value_objects.article_summary_for_report import ArticleSummaryForReport


class WeeklyReportRepoImpl(WeeklyReportRepository):
    def __init__(self, session: Session) -> None:
        self._session = session

    def fetch_top_articles(self, topic_id: UUID, week_start: date, limit: int = 20) -> List[ArticleSummaryForReport]:
        from models.article import Article
        from models.article_metrics import ArticleMetrics
        from models.article_metric_value import ArticleMetricValue
        from models.analysis import Analysis
        from models.analyses_translation import AnalysesTranslation

        week_end = week_start + timedelta(days=7)
        # Ranking of the top-N candidate pool is intentionally still keyed on citation_count
        # specifically — that's a separate concern (which articles even make it into the prompt)
        # from what each selected article's ArticleSummaryForReport.metrics carries (all of that
        # article's catalog metrics, for the LLM's own judgment — see weekly_report_prompt.py).
        sort_citations = func.coalesce(ArticleMetricValue.value, 0)
        sort_views = func.coalesce(ArticleMetrics.view_count, 0)

        rows = (
            self._session.query(Article, AnalysesTranslation, ArticleMetrics)
            .outerjoin(ArticleMetrics, ArticleMetrics.article_id == Article.id)
            .outerjoin(
                ArticleMetricValue,
                (ArticleMetricValue.article_id == Article.id) & (ArticleMetricValue.metric_key == "citation_count"),
            )
            .outerjoin(Analysis, Analysis.article_id == Article.id)
            .outerjoin(
                AnalysesTranslation,
                (AnalysesTranslation.analysis_id == Analysis.id) & (AnalysesTranslation.language == 'en'),
            )
            .filter(
                Article.topic_id == topic_id,
                Article.scraped_at >= week_start,
                Article.scraped_at < week_end,
            )
            .order_by(sort_citations.desc(), sort_views.desc(), Article.published_at.desc().nulls_last())
            .limit(limit)
            .all()
        )

        article_ids = [article.id for article, _, _ in rows]
        metrics_by_article: Dict[UUID, Dict[str, float]] = {}
        if article_ids:
            metric_rows = (
                self._session.query(ArticleMetricValue)
                .filter(ArticleMetricValue.article_id.in_(article_ids), ArticleMetricValue.value.isnot(None))
                .all()
            )
            for mv in metric_rows:
                metrics_by_article.setdefault(mv.article_id, {})[mv.metric_key] = float(mv.value)

        results = []
        for article, translation, article_metrics in rows:
            results.append(ArticleSummaryForReport(
                article_id=article.id,
                title=article.title or "",
                summary=translation.summary if translation else None,
                pain_points=translation.pain_points if translation else None,
                insights=translation.insights if translation else None,
                innovations=translation.innovations if translation else None,
                tags=[tag.name for tag in article.tags],
                metrics=metrics_by_article.get(article.id, {}),
                view_count=(article_metrics.view_count if article_metrics else 0) or 0,
                published_at=article.published_at,
            ))
        return results

    def save(self, report: WeeklyReport) -> WeeklyReport:
        from models.weekly_report import WeeklyReport as WeeklyReportModel

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
        return self._to_domain(row) if row else None

    def find_by_topic_and_week(self, topic_id: UUID, week_start: date) -> Optional[WeeklyReport]:
        from models.weekly_report import WeeklyReport as WeeklyReportModel
        row = (
            self._session.query(WeeklyReportModel)
            .filter(
                WeeklyReportModel.topic_id == topic_id,
                WeeklyReportModel.week_start_date == week_start,
            )
            .first()
        )
        return self._to_domain(row) if row else None

    @staticmethod
    def _to_domain(row) -> WeeklyReport:
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
