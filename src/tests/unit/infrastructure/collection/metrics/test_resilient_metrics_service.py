from unittest.mock import MagicMock, patch

from src.infrastructure.collection.metrics.resilient_metrics_service import (
    ResilientMetricsService,
    MetricHandler,
    build_resilient_metrics_service,
    build_provider_fetchers,
)


def _handler(metric_key, provider_name, priority, fetch_return, extract_return):
    extractor = MagicMock()
    extractor.fetch.return_value = fetch_return
    extractor.extract.return_value = extract_return
    return MetricHandler(
        metric_key=metric_key,
        provider_name=provider_name,
        priority=priority,
        extractor=extractor,
        extractor_spec={"path": "cited_by_count"},
    )


def test_fetch_all_uses_first_successful_provider_in_priority_order():
    h1 = _handler("citation_count", "openalex", 1, {"cited_by_count": 10}, 10)
    h2 = _handler("citation_count", "semantic_scholar", 2, {"citationCount": 99}, 99)

    service = ResilientMetricsService(handlers=[h2, h1])  # deliberately out of order
    result = service.fetch_all({"doi": "10.1234/x"})

    assert result == {"citation_count": 10}
    h2.extractor.fetch.assert_not_called()  # never reached, h1 already succeeded


def test_fetch_all_falls_back_when_first_provider_returns_none():
    h1 = _handler("citation_count", "openalex", 1, None, None)  # fetch() itself returns None
    h2 = _handler("citation_count", "semantic_scholar", 2, {"citationCount": 5}, 5)

    service = ResilientMetricsService(handlers=[h1, h2])
    result = service.fetch_all({"doi": "10.1234/x"})

    assert result == {"citation_count": 5}


def test_fetch_all_falls_back_when_first_provider_raises():
    h1 = _handler("citation_count", "openalex", 1, None, None)
    h1.extractor.fetch.side_effect = Exception("network error")
    h2 = _handler("citation_count", "semantic_scholar", 2, {"citationCount": 3}, 3)

    service = ResilientMetricsService(handlers=[h1, h2])
    result = service.fetch_all({"doi": "10.1234/x"})

    assert result == {"citation_count": 3}


def test_fetch_all_omits_metric_key_when_all_providers_fail():
    h1 = _handler("citation_count", "openalex", 1, None, None)
    h2 = _handler("citation_count", "semantic_scholar", 2, None, None)

    service = ResilientMetricsService(handlers=[h1, h2])
    result = service.fetch_all({"doi": "10.1234/x"})

    assert result == {}


def test_fetch_all_handles_multiple_independent_metric_keys():
    citation_handler = _handler("citation_count", "openalex", 1, {"cited_by_count": 10}, 10)
    impact_handler = _handler("impact_factor", "journal_lookup", 1, {"if": 4.5}, 4.5)

    service = ResilientMetricsService(handlers=[citation_handler, impact_handler])
    result = service.fetch_all({"doi": "10.1234/x"})

    assert result == {"citation_count": 10, "impact_factor": 4.5}


def test_tracked_metric_keys_reflects_configured_handlers():
    h1 = _handler("citation_count", "openalex", 1, None, None)
    service = ResilientMetricsService(handlers=[h1])

    assert service.tracked_metric_keys == ["citation_count"]


# ── build_resilient_metrics_service ─────────────────────────────────────────

def test_build_skips_unknown_provider_name():
    definitions = [
        {"metric_key": "citation_count", "provider_name": "unknown_provider", "priority": 1,
         "extractor_type": "json_path", "extractor_spec": {"path": "x"}},
    ]
    service = build_resilient_metrics_service(definitions)
    assert service.tracked_metric_keys == []


def test_build_skips_unknown_extractor_type():
    definitions = [
        {"metric_key": "citation_count", "provider_name": "openalex", "priority": 1,
         "extractor_type": "totally_made_up", "extractor_spec": {}},
    ]
    service = build_resilient_metrics_service(definitions)
    assert service.tracked_metric_keys == []


def test_build_wires_json_path_extractor_for_known_provider():
    definitions = [
        {"metric_key": "citation_count", "provider_name": "openalex", "priority": 1,
         "extractor_type": "json_path", "extractor_spec": {"path": "cited_by_count"}},
    ]
    service = build_resilient_metrics_service(definitions)
    assert service.tracked_metric_keys == ["citation_count"]


# ── build_provider_fetchers (2026-07-12): semantic_scholar_arxiv fallback ───

def test_provider_fetchers_includes_semantic_scholar_arxiv():
    with patch("src.infrastructure.collection.clients.openalex_client.OpenAlexClient"), \
         patch("src.infrastructure.collection.clients.semantic_scholar_client.SemanticScholarClient"):
        fetchers = build_provider_fetchers()
    assert "semantic_scholar_arxiv" in fetchers


def test_semantic_scholar_arxiv_fetcher_uses_arxiv_id_not_doi():
    mock_s2 = MagicMock()
    with patch("src.infrastructure.collection.clients.openalex_client.OpenAlexClient"), \
         patch("src.infrastructure.collection.clients.semantic_scholar_client.SemanticScholarClient", return_value=mock_s2):
        fetchers = build_provider_fetchers()

    fetchers["semantic_scholar_arxiv"]({"arxiv_id": "2501.12345"})
    mock_s2.fetch_by_arxiv_id.assert_called_once_with("2501.12345")


def test_semantic_scholar_arxiv_fetcher_returns_none_without_arxiv_id():
    mock_s2 = MagicMock()
    with patch("src.infrastructure.collection.clients.openalex_client.OpenAlexClient"), \
         patch("src.infrastructure.collection.clients.semantic_scholar_client.SemanticScholarClient", return_value=mock_s2):
        fetchers = build_provider_fetchers()

    result = fetchers["semantic_scholar_arxiv"]({"doi": "10.1234/x"})  # no arxiv_id
    assert result is None
    mock_s2.fetch_by_arxiv_id.assert_not_called()


def test_openalex_fetcher_still_ignores_arxiv_id():
    """OpenAlex genuinely cannot look up by arXiv ID — confirmed against their docs — so its
    fetcher must never be called with only an arxiv_id and no doi."""
    mock_openalex = MagicMock()
    with patch("src.infrastructure.collection.clients.openalex_client.OpenAlexClient", return_value=mock_openalex), \
         patch("src.infrastructure.collection.clients.semantic_scholar_client.SemanticScholarClient"):
        fetchers = build_provider_fetchers()

    result = fetchers["openalex"]({"arxiv_id": "2501.12345"})
    assert result is None
    mock_openalex.fetch_by_doi.assert_not_called()
