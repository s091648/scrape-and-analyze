import pytest

from src.modules.collection.domain.value_objects.scraper_keyword import (
    build_scraper_keyword,
    RssKeyword,
    ArxivKeyword,
    ArxivCategory,
    SemanticScholarKeyword,
    OpenAlexKeyword,
)
from src.modules.collection.domain.exceptions import InvalidScraperKeywordTypeError


@pytest.mark.parametrize("keyword_type, expected_cls", [
    ("rss", RssKeyword),
    ("arxiv_keyword", ArxivKeyword),
    ("arxiv_category", ArxivCategory),
    ("semantic_scholar_keyword", SemanticScholarKeyword),
    ("openalex_keyword", OpenAlexKeyword),
])
def test_build_scraper_keyword_returns_matching_type(keyword_type, expected_cls):
    result = build_scraper_keyword(keyword_type, "digital twin")
    assert isinstance(result, expected_cls)
    assert result.keyword == "digital twin"


def test_build_scraper_keyword_raises_for_unknown_type():
    with pytest.raises(InvalidScraperKeywordTypeError):
        build_scraper_keyword("unknown_type", "x")
