from dataclasses import dataclass
from typing import Optional
from uuid import UUID


@dataclass
class AnalysesTranslationContent:
    """Translated content of an article analysis."""
    summary: Optional[str]
    pain_points: Optional[str]
    insights: Optional[str]
    innovations: Optional[str]


@dataclass
class AnalysesTranslationResult:
    """Return value of TranslateArticleUseCase.execute() on success — a failure raises instead."""
    analysis_id: UUID
    language: str
    content: AnalysesTranslationContent


@dataclass
class ArticleBodyTranslationContent:
    """Translated title and content of an article."""
    title: Optional[str]
    content: Optional[str]


@dataclass
class ArticleBodyTranslationResult:
    """Return value of TranslateArticleBodyUseCase.execute() on success — a failure raises instead."""
    article_id: UUID
    language: str
    content: ArticleBodyTranslationContent
