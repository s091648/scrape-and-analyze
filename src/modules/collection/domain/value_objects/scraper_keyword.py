from __future__ import annotations
from typing import Annotated, Literal, Union
from pydantic import BaseModel, Field

from src.modules.collection.domain.exceptions import InvalidScraperKeywordTypeError


class RssKeyword(BaseModel):
    """Keyword for filtering RSS feed entries by regex pattern."""
    type: Literal["rss"] = "rss"
    keyword: str  # regex pattern used to filter RSS entries


class ArxivKeyword(BaseModel):
    """Keyword for searching ArXiv by query string (e.g. ti:"digital twin")."""
    type: Literal["arxiv_keyword"] = "arxiv_keyword"
    keyword: str  # arXiv query string, e.g. ti:"digital twin" or abs:NeRF


class ArxivCategory(BaseModel):
    """Keyword for filtering ArXiv by category code (e.g. cs.GR)."""
    type: Literal["arxiv_category"] = "arxiv_category"
    keyword: str  # arXiv category code, e.g. cs.GR — stored as keyword in DB


class SemanticScholarKeyword(BaseModel):
    """Keyword for searching Semantic Scholar by free-text query."""
    type: Literal["semantic_scholar_keyword"] = "semantic_scholar_keyword"
    keyword: str  # free-text search keyword, e.g. "digital twin"


class OpenAlexKeyword(BaseModel):
    """Keyword for searching OpenAlex by free-text query."""
    type: Literal["openalex_keyword"] = "openalex_keyword"
    keyword: str  # free-text search keyword, e.g. "digital twin"


ScraperKeywordVO = Annotated[
    Union[RssKeyword, ArxivKeyword, ArxivCategory, SemanticScholarKeyword, OpenAlexKeyword],
    Field(discriminator="type"),
]

def build_scraper_keyword(keyword_type: str, keyword: str) -> RssKeyword | ArxivKeyword | ArxivCategory | SemanticScholarKeyword | OpenAlexKeyword:
    """Factory function that constructs the correct keyword VO based on the type string."""
    if keyword_type == "rss":
        return RssKeyword(keyword=keyword)
    if keyword_type == "arxiv_keyword":
        return ArxivKeyword(keyword=keyword)
    if keyword_type == "arxiv_category":
        return ArxivCategory(keyword=keyword)
    if keyword_type == "semantic_scholar_keyword":
        return SemanticScholarKeyword(keyword=keyword)
    if keyword_type == "openalex_keyword":
        return OpenAlexKeyword(keyword=keyword)
    raise InvalidScraperKeywordTypeError(f"Unknown keyword_type: {keyword_type!r}")
