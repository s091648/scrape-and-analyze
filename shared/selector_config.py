from __future__ import annotations
from typing import Annotated, Any, Literal, Union
from pydantic import BaseModel, Field, TypeAdapter, field_validator
from pydantic import ValidationError as PydanticValidationError

from shared.domain.exceptions import ValidationError


class RssConfig(BaseModel):
    type: Literal["rss"] = "rss"


class BlogConfig(BaseModel):
    type: Literal["blog"] = "blog"
    selectors: dict[str, str] = Field(default_factory=dict)

    @field_validator("selectors")
    @classmethod
    def _require_links_selector(cls, v: dict[str, str]) -> dict[str, str]:
        """Without a 'links' selector, BlogScraper silently falls back to its
        wide-open default ("a" — every anchor on the listing page, including
        nav/category links) — fail loudly at construction instead."""
        if not v.get("links"):
            raise ValueError("selectors must include a non-empty 'links' selector")
        return v


class ArxivConfig(BaseModel):
    type: Literal["arxiv"] = "arxiv"
    max_results: int = 30
    days_back: int = 7


class SemanticScholarConfig(BaseModel):
    type: Literal["semantic_scholar"] = "semantic_scholar"
    max_results: int = 20
    days_back: int = 7


class OpenAlexConfig(BaseModel):
    type: Literal["openalex"] = "openalex"
    max_results: int = 20
    days_back: int = 7


SelectorConfig = Annotated[
    Union[RssConfig, BlogConfig, ArxivConfig, SemanticScholarConfig, OpenAlexConfig],
    Field(discriminator="type"),
]

_adapter = TypeAdapter(SelectorConfig)


def build_selector_config(
    source_type: str,
    raw: dict[str, Any] | None,
) -> SelectorConfig | None:
    """Construct a typed SelectorConfig from a raw JSONB dict and source_type.

    Handles both new data (with 'type' discriminator) and legacy data (without).

    Raises:
        shared.domain.exceptions.ValidationError: if raw doesn't satisfy the
            target config type's invariants (e.g. a blog config missing its
            'links' selector). Pydantic's own ValidationError is translated
            here so callers only ever handle the shared domain exception.
    """
    if not raw:
        raw = {}

    try:
        if "type" in raw:
            return _adapter.validate_python(raw)

        if source_type == "rss":
            return RssConfig()
        if source_type == "blog":
            # The admin UI (frontend/app/admin/scraper-settings) saves a flat
            # {article_link, title, content} shape rather than nesting it under
            # a "selectors" key, and names the link field "article_link" where
            # BlogScraper expects "links". Translate that shape here so values
            # entered in the UI actually reach BlogScraper instead of being
            # silently discarded in favor of its wide-open "a" default.
            selectors = raw.get("selectors")
            if not selectors:
                selectors = {
                    k: v for k, v in {
                        "links": raw.get("article_link") or raw.get("links"),
                        "title": raw.get("title"),
                        "content": raw.get("content"),
                    }.items() if v
                }
            return BlogConfig(selectors=selectors)
        if source_type == "arxiv":
            return ArxivConfig(
                max_results=raw.get("max_results", 30),
                days_back=raw.get("days_back", 7),
            )
        if source_type == "semantic_scholar":
            return SemanticScholarConfig(
                max_results=raw.get("max_results", 20),
                days_back=raw.get("days_back", 7),
            )
        if source_type == "openalex":
            return OpenAlexConfig(
                max_results=raw.get("max_results", 20),
                days_back=raw.get("days_back", 7),
            )
        return None
    except PydanticValidationError as e:
        raise ValidationError(f"Invalid selector_config for source_type={source_type!r}: {e}") from e
