"""Integration tests for shared.metric_definition.load_enabled_metric_definitions."""
import uuid

import pytest

pytestmark = pytest.mark.integration


def _definition(db_session, *, metric_key="citation_count", enabled=True,
                label_i18n_key="metrics.citation_count", icon_name="quote"):
    from models.metric_definition import MetricDefinition
    obj = MetricDefinition(
        id=uuid.uuid4(),
        metric_key=metric_key,
        label_i18n_key=label_i18n_key,
        format_hint="integer",
        unit=None,
        icon_name=icon_name,
        enabled=enabled,
    )
    db_session.add(obj)
    db_session.flush()
    return obj


def _provider(db_session, definition, *, provider_name="openalex", priority=1,
              extractor_type="json_path", extractor_spec=None):
    from models.metric_provider import MetricProvider
    obj = MetricProvider(
        id=uuid.uuid4(),
        metric_definition_id=definition.id,
        provider_name=provider_name,
        priority=priority,
        extractor_type=extractor_type,
        extractor_spec=extractor_spec or {"path": "some.path"},
    )
    db_session.add(obj)
    db_session.flush()
    return obj


def test_returns_only_enabled_metric_definitions(db_session):
    from shared.metric_definition import load_enabled_metric_definitions
    enabled = _definition(db_session, metric_key="citation_count", enabled=True)
    _provider(db_session, enabled)
    disabled = _definition(db_session, metric_key="impact_factor", enabled=False)
    _provider(db_session, disabled, provider_name="scopus")

    result = load_enabled_metric_definitions(db_session)

    keys = [r["metric_key"] for r in result]
    assert "citation_count" in keys
    assert "impact_factor" not in keys


def test_one_row_per_provider_for_multi_provider_metric(db_session):
    from shared.metric_definition import load_enabled_metric_definitions
    d = _definition(db_session, metric_key="citation_count")
    _provider(db_session, d, provider_name="openalex", priority=1)
    _provider(db_session, d, provider_name="semantic_scholar", priority=2)

    result = load_enabled_metric_definitions(db_session)

    rows = [r for r in result if r["metric_key"] == "citation_count"]
    assert len(rows) == 2
    provider_names = {r["provider_name"] for r in rows}
    assert provider_names == {"openalex", "semantic_scholar"}


def test_sorted_by_metric_key_then_priority(db_session):
    from shared.metric_definition import load_enabled_metric_definitions
    d1 = _definition(db_session, metric_key="impact_factor")
    _provider(db_session, d1, provider_name="scopus", priority=1)
    d2 = _definition(db_session, metric_key="citation_count")
    _provider(db_session, d2, provider_name="semantic_scholar", priority=2)
    _provider(db_session, d2, provider_name="openalex", priority=1)

    result = load_enabled_metric_definitions(db_session)

    keys_and_priority = [(r["metric_key"], r["priority"]) for r in result]
    assert keys_and_priority == sorted(keys_and_priority)


def test_result_shape_contains_extraction_fields(db_session):
    from shared.metric_definition import load_enabled_metric_definitions
    d = _definition(db_session, metric_key="citation_count")
    _provider(
        db_session, d, provider_name="openalex", priority=1,
        extractor_type="json_path", extractor_spec={"path": "citation_count"},
    )

    result = load_enabled_metric_definitions(db_session)

    match = next(r for r in result if r["metric_key"] == "citation_count")
    assert match["provider_name"] == "openalex"
    assert match["priority"] == 1
    assert match["extractor_type"] == "json_path"
    assert match["extractor_spec"] == {"path": "citation_count"}


def test_metric_with_no_providers_is_excluded(db_session):
    """The INNER JOIN to metric_providers means a metric_definitions row with zero
    provider rows never appears in the output (it has nothing to extract with)."""
    from shared.metric_definition import load_enabled_metric_definitions
    _definition(db_session, metric_key="no_provider_metric", enabled=True)

    result = load_enabled_metric_definitions(db_session)

    assert "no_provider_metric" not in [r["metric_key"] for r in result]


def test_returns_empty_list_when_no_definitions(db_session):
    from shared.metric_definition import load_enabled_metric_definitions

    result = load_enabled_metric_definitions(db_session)

    assert result == []
