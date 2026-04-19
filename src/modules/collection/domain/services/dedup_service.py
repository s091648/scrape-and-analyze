"""
DedupService — URL deduplication business logic.

Extracted from main.py:process_article() where it was inline.
Depends only on domain interfaces; no infrastructure imports.

Business rules encoded here:
  1. A URL is a duplicate if its hash already exists in the article store.
  2. A duplicate article still needs analysis if it has no Analysis record.
"""
from typing import Optional

from src.shared.domain.entities import Article
from src.shared.domain.repositories import ArticleRepository
from src.modules.collection.domain.value_objects import UrlHash


class DedupService:

    def __init__(self, article_repo: ArticleRepository) -> None:
        self._repo = article_repo

    def find_existing(self, url: str) -> Optional[Article]:
        """
        Return the existing Article if *url* has been seen before,
        else None.
        """
        url_hash = UrlHash.from_url(url).value
        return self._repo.find_by_url_hash(url_hash)

    def needs_analysis(self, article: Article) -> bool:
        """
        Return True if *article* exists in the store but has no Analysis yet.
        Returns False for unsaved articles (id is None).
        """
        if article.id is None:
            return False
        return not self._repo.has_analysis(article.id)
