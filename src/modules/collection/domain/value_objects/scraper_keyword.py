from __future__ import annotations
from typing import Annotated, Literal, Union
from pydantic import BaseModel, Field


class RssKeyword(BaseModel):
    type: Literal["rss"] = "rss"
    keyword: str  # regex pattern used to filter RSS entries


class ArxivKeyword(BaseModel):
    type: Literal["arxiv_keyword"] = "arxiv_keyword"
    keyword: str  # arXiv query string, e.g. ti:"digital twin" or abs:NeRF


class ArxivCategory(BaseModel):
    type: Literal["arxiv_category"] = "arxiv_category"
    keyword: str  # arXiv category code, e.g. cs.GR — stored as keyword in DB


ScraperKeywordVO = Annotated[
    Union[RssKeyword, ArxivKeyword, ArxivCategory],
    Field(discriminator="type"),
]

def build_scraper_keyword(keyword_type: str, keyword: str) -> RssKeyword | ArxivKeyword | ArxivCategory:
    if keyword_type == "rss":
        return RssKeyword(keyword=keyword)
    if keyword_type == "arxiv_keyword":
        return ArxivKeyword(keyword=keyword)
    if keyword_type == "arxiv_category":
        return ArxivCategory(keyword=keyword)
    raise ValueError(f"Unknown keyword_type: {keyword_type!r}")
