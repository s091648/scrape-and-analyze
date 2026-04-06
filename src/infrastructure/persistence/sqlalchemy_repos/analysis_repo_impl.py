"""
SQLAlchemy implementation of AnalysisRepository.

Maps AnalysisEntity → ORM Analysis + Tag M2M relationship.
The tag_groups list [{group: str, tags: [str]}] is resolved here into
Tag rows, matching the existing main.py logic.
"""
from src.domain.entities.analysis import AnalysisEntity
from src.domain.repositories.analysis_repository import AnalysisRepository
from src.utils.logging import get_logger

logger = get_logger(__name__)


class SqlAlchemyAnalysisRepository(AnalysisRepository):

    def __init__(self, session) -> None:
        self._session = session

    # ── interface ─────────────────────────────────────────────────────────

    def save(self, analysis: AnalysisEntity) -> AnalysisEntity:
        from models.analysis import Analysis
        from models.article import Article
        from models.tag import Tag

        row = Analysis(
            article_id=analysis.article_id,
            correlation_id=analysis.correlation_id,
            pain_points=analysis.pain_points,
            insights=analysis.insights,
            innovations=analysis.innovations,
            model_used=analysis.model_used,
            input_tokens=analysis.input_tokens,
            output_tokens=analysis.output_tokens,
        )
        self._session.add(row)
        self._session.flush()  # populate row.id

        # Resolve tag_groups into Tag rows + article_tags association
        article_row = self._session.query(Article).filter_by(
            id=analysis.article_id
        ).first()

        if article_row is not None:
            for tg in (analysis.tag_groups or []):
                group_name = tg.get("group", "")
                for tag_name in tg.get("tags", []):
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

        self._session.commit()
        logger.info(
            "analysis_row_saved",
            article_id=str(analysis.article_id),
            analysis_id=str(row.id),
            model=analysis.model_used,
        )

        analysis.id = row.id
        analysis.analyzed_at = row.analyzed_at
        return analysis
