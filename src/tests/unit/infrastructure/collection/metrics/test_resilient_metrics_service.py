from unittest.mock import MagicMock

from src.infrastructure.collection.metrics.resilient_metrics_service import (
    ResilientMetricsService,
    MetricHandler,
    build_resilient_metrics_service,
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
