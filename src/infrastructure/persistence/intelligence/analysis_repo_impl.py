from uuid import uuid4

from src.modules.intelligence.domain.entities import Analysis
from src.modules.intelligence.domain.repositories import AnalysisRepository
from src.shared.logging import get_logger

logger = get_logger(__name__)


class SqlAlchemyAnalysisRepository(AnalysisRepository):

    def __init__(self, session) -> None:
        self._session = session

    def save(self, analysis: Analysis) -> None:
        from models.analysis import Analysis as AnalysisModel
        from models.article import Article as ArticleModel
        from models.tag import Tag

        content = analysis.analysis_content
        metadata = analysis.analysis_metadata

        row = AnalysisModel(
            article_id=analysis.article_id,
            correlation_id=uuid4(),  # legacy NOT NULL column; no longer in domain model
            pain_points=content.pain_points,
            insights=content.insights,
            innovations=content.innovations,
            summary=content.summary,
            model_used=metadata.model_used,
            input_tokens=metadata.input_tokens,
            output_tokens=metadata.output_tokens,
        )
        self._session.add(row)
        self._session.flush()

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

        self._session.commit()
        logger.info("analysis_saved", article_id=str(analysis.article_id), model=metadata.model_used)
