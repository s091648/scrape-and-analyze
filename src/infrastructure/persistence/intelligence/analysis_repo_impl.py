from uuid import uuid4
from datetime import datetime, timedelta, timezone
from typing import List

from sqlalchemy import not_

from src.modules.intelligence.domain.entities import Analysis
from src.modules.intelligence.domain.repositories import AnalysisRepository
from src.shared.logging import get_logger

logger = get_logger(__name__)


class SqlAlchemyAnalysisRepository(AnalysisRepository):

    def __init__(self, session) -> None:
        self._session = session

    def save(self, analysis: Analysis) -> None:
        from models.analysis import Analysis as AnalysisModel
        from models.analyses_translation import AnalysesTranslation as AnalysesTranslationModel
        from models.article import Article as ArticleModel
        from models.tag import Tag

        content = analysis.analysis_content
        metadata = analysis.analysis_metadata

        row = AnalysisModel(
            article_id=analysis.article_id,
            correlation_id=uuid4(),  # legacy NOT NULL column; no longer in domain model
            model_used=metadata.model_used,
            input_tokens=metadata.input_tokens,
            output_tokens=metadata.output_tokens,
        )
        self._session.add(row)
        self._session.flush()

        # Backfill the DB-generated id into the domain entity
        analysis.id = row.id

        # Create English translation row with content
        translation_row = AnalysesTranslationModel(
            analysis_id=row.id,
            language='en',
            summary=content.summary,
            pain_points=content.pain_points,
            insights=content.insights,
            innovations=content.innovations,
        )
        self._session.add(translation_row)

        # Resolve tag_groups into Tag rows
        article_row = self._session.query(ArticleModel).filter_by(
            id=analysis.article_id
        ).first()

        if article_row and content.tag_groups:
            for tg in content.tag_groups:
                group_name = tg.display_name
                for tag_name in tg.description.split(", "):
                    if not tag_name or not group_name:
                        continue
                    tag = self._session.query(Tag).filter_by(
                        name=tag_name, tag_group_name=group_name
                    ).first()
                    if not tag:
                        tag = Tag(name=tag_name, tag_group_name=group_name)
                        self._session.add(tag)
                        self._session.flush()
                    if tag not in article_row.tags:
                        article_row.tags.append(tag)

        try:
            self._session.commit()
        except Exception:
            self._session.rollback()
            raise
        logger.info("analysis_saved", article_id=str(analysis.article_id), model=metadata.model_used)

    def find_missing_analyses(self) -> List:
        """Find articles that have no analysis."""
        from models.article import Article
        from models.analysis import Analysis as AnalysisModel

        analyzed_ids = self._session.query(AnalysisModel.article_id).all()
        analyzed_ids = [aid[0] for aid in analyzed_ids]

        if not analyzed_ids:
            return self._session.query(Article).all()

        return self._session.query(Article).filter(
            not_(Article.id.in_(analyzed_ids))
        ).all()

    def scan_missing_analyses(self, min_age_hours: int = 1) -> List:
        """Find articles older than min_age_hours that have no analysis (zombie detection)."""
        from models.article import Article
        from models.analysis import Analysis as AnalysisModel

        cutoff = datetime.now(timezone.utc) - timedelta(hours=min_age_hours)

        analyzed_ids = self._session.query(AnalysisModel.article_id).all()
        analyzed_ids = [aid[0] for aid in analyzed_ids]

        query = self._session.query(Article).filter(
            Article.scraped_at < cutoff
        )

        if analyzed_ids:
            query = query.filter(not_(Article.id.in_(analyzed_ids)))

        return query.all()