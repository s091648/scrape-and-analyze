from __future__ import annotations
from typing import Annotated, Any, Literal, Union
from pydantic import BaseModel, Field, TypeAdapter


class RssConfig(BaseModel):
    type: Literal["rss"] = "rss"


class BlogConfig(BaseModel):
    type: Literal["blog"] = "blog"
    selectors: dict[str, str] = Field(default_factory=dict)


class ArxivConfig(BaseModel):
    type: Literal["arxiv"] = "arxiv"
    max_results: int = 30
    days_back: int = 7
    # Deprecated: prefer scraper_keywords table (keyed by topic_id).
    # Kept for backward compat with existing selector_config JSONB data.
    keywords: list[str] | None = None
    categories: list[str] | None = None


SelectorConfig = Annotated[
    Union[RssConfig, BlogConfig, ArxivConfig],
    Field(discriminator="type"),
]

_adapter = TypeAdapter(SelectorConfig)


def build_selector_config(
    source_type: str,
    raw: dict[str, Any] | None,
) -> SelectorConfig | None:
    """Construct a typed SelectorConfig from a raw JSONB dict and source_type.

    Handles both new data (with 'type' discriminator) and legacy data (without).
    """
    if not raw:
        raw = {}

    if "type" in raw:
        return _adapter.validate_python(raw)

    if source_type == "rss":
        return RssConfig()
    if source_type == "blog":
        return BlogConfig(selectors=raw.get("selectors") or {})
    if source_type == "arxiv":
        return ArxivConfig(
            max_results=raw.get("max_results", 30),
            days_back=raw.get("days_back", 7),
            keywords=raw.get("keywords") or None,
            categories=raw.get("categories") or None,
        )
    return None
