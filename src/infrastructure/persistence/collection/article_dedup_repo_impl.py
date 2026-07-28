from datetime import datetime, timezone
from typing import Optional
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.orm import Session
from sqlalchemy.dialects.postgresql import insert

from models.article import Article
from models.article_metrics import ArticleMetrics
from models.tag import article_tags
from src.modules.collection.domain.repositories.article_dedup_repository import ArticleDedupRepository
from src.shared.logging import get_logger

logger = get_logger(__name__)


class SqlAlchemyArticleDedupRepository(ArticleDedupRepository):
    def __init__(self, session: Session) -> None:
        self._session = session

    def find_by_work_id(self, work_id: str) -> Optional[UUID]:
        row = self._session.execute(
            text(
                "SELECT id FROM articles WHERE metadata->>'work_id' = :work_id "
                "AND merged_into_id IS NULL LIMIT 1"
            ),
            {"work_id": work_id},
        ).first()
        return row.id if row else None

    def heal_identifiers(self, article_id: UUID, work_id: str, doi: Optional[str]) -> None:
        article = self._session.query(Article).filter_by(id=article_id).first()
        if article is None:
            return
        metadata = dict(article.metadata_ or {})
        metadata["work_id"] = work_id
        if doi:
            metadata["doi"] = doi
        article.metadata_ = metadata
        article.last_reconciled_at = datetime.now(timezone.utc)
        self._session.commit()

    def merge(self, loser_id: UUID, survivor_id: UUID) -> None:
        loser_metrics = self._session.query(ArticleMetrics).filter_by(article_id=loser_id).first()
        if loser_metrics and loser_metrics.view_count:
            stmt = (
                insert(ArticleMetrics)
                .values(article_id=survivor_id, view_count=loser_metrics.view_count)
                .on_conflict_do_update(
                    index_elements=["article_id"],
                    set_={"view_count": ArticleMetrics.view_count + loser_metrics.view_count},
                )
            )
            self._session.execute(stmt)

        loser_tag_ids = {
            row.tag_id
            for row in self._session.query(article_tags.c.tag_id).filter(article_tags.c.article_id == loser_id)
        }
        survivor_tag_ids = {
            row.tag_id
            for row in self._session.query(article_tags.c.tag_id).filter(article_tags.c.article_id == survivor_id)
        }
        for tag_id in loser_tag_ids - survivor_tag_ids:
            self._session.execute(insert(article_tags).values(article_id=survivor_id, tag_id=tag_id))

        now = datetime.now(timezone.utc)
        self._session.query(Article).filter_by(id=loser_id).update({
            "merged_into_id": survivor_id,
            "merged_at": now,
            "last_reconciled_at": now,
        })
        self._session.commit()
        logger.info("article_merged", loser_id=str(loser_id), survivor_id=str(survivor_id))

    def mark_reconciled(self, article_id: UUID) -> None:
        self._session.query(Article).filter_by(id=article_id).update({
            "last_reconciled_at": datetime.now(timezone.utc),
        })
        self._session.commit()
