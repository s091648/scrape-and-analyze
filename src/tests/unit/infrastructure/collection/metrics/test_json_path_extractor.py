from unittest.mock import MagicMock

from src.infrastructure.collection.metrics.json_path_extractor import JsonPathMetricExtractor


def test_extract_reads_field_via_jmespath():
    extractor = JsonPathMetricExtractor(provider_name="openalex", fetcher=MagicMock())
    raw = {"cited_by_count": 42, "title": "Some Paper"}

    value = extractor.extract(raw, {"path": "cited_by_count"})

    assert value == 42


def test_extract_returns_none_for_missing_field():
    extractor = JsonPathMetricExtractor(provider_name="semantic_scholar", fetcher=MagicMock())
    raw = {"citationCount": None}

    value = extractor.extract(raw, {"path": "nonexistent_field"})

    assert value is None


def test_extract_returns_none_when_spec_has_no_path():
    extractor = JsonPathMetricExtractor(provider_name="openalex", fetcher=MagicMock())

    value = extractor.extract({"cited_by_count": 5}, {})

    assert value is None


def test_fetch_delegates_to_fetcher_callable():
    fetcher = MagicMock(return_value={"citationCount": 7})
    extractor = JsonPathMetricExtractor(provider_name="semantic_scholar", fetcher=fetcher)

    result = extractor.fetch({"doi": "10.1234/abc"})

    fetcher.assert_called_once_with({"doi": "10.1234/abc"})
    assert result == {"citationCount": 7}
