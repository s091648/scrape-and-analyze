"""Integration tests for the DB-driven config loaders in shared/ — llm_provider.py
(LLM / embedding / multimodal provider rows) and metric_definition.py (the
metric_definitions ⋈ metric_providers join). Both are pure DB reads that every
scheduled entrypoint's bootstrap depends on (see src/bootstrap.py), so they're
exercised against the real test schema rather than mocked.

Rows are only flushed on the per-test db_session, which rolls back afterwards, so
nothing leaks into other tests. Model names are uuid-suffixed because
LlmProvider.model is globally unique."""
import uuid

import pytest

from models.llm_provider import LlmProvider
from models.metric_definition import MetricDefinition
from models.metric_provider import MetricProvider
from shared.llm_provider import (
    load_active_embedding_providers,
    load_active_multimodal_provider,
    load_active_providers,
)
from shared.metric_definition import load_enabled_metric_definitions

pytestmark = pytest.mark.integration


def _provider(**overrides) -> LlmProvider:
    fields = dict(
        name="gemini",
        model=f"model-{uuid.uuid4().hex[:8]}",
        api_key_env="GEMINI_API_KEY",
        priority=1,
        type="llm",
        is_active=True,
    )
    fields.update(overrides)
    return LlmProvider(**fields)


class TestLoadActiveProviders:
    def test_returns_only_active_llm_rows_ordered_by_priority(self, db_session):
        second = _provider(name="claude", priority=2, rpm=5, tpm=1000, rpd=50)
        first = _provider(name="gemini", priority=1)
        inactive = _provider(name="openrouter", priority=0, is_active=False)
        embedding = _provider(name="gemini", priority=0, type="embedding")
        db_session.add_all([second, first, inactive, embedding])
        db_session.flush()

        result = load_active_providers(db_session)

        assert [r["model"] for r in result] == [first.model, second.model]

    def test_builds_sliding_window_strategy_only_when_all_limits_set(self, db_session):
        limited = _provider(name="claude", priority=1, rpm=5, tpm=1000, rpd=50)
        partial = _provider(name="gemini", priority=2, rpm=5, tpm=None, rpd=50)
        db_session.add_all([limited, partial])
        db_session.flush()

        by_model = {r["model"]: r for r in load_active_providers(db_session)}

        assert by_model[limited.model]["strategy"] == {
            "type": "sliding_window", "rpm": 5, "tpm": 1000, "rpd": 50,
        }
        # Any missing limit means "don't rate-limit locally", not a partial window.
        assert by_model[partial.model]["strategy"] == {"type": "noop"}
        assert by_model[limited.model]["api_key_env"] == "GEMINI_API_KEY"
        assert by_model[limited.model]["priority"] == 1

    def test_embedding_loader_ignores_llm_rows(self, db_session):
        emb = _provider(name="gemini", type="embedding", priority=3)
        llm = _provider(name="gemini", type="llm", priority=1)
        db_session.add_all([emb, llm])
        db_session.flush()

        result = load_active_embedding_providers(db_session)

        assert [r["model"] for r in result] == [emb.model]


class TestLoadActiveMultimodalProvider:
    def test_returns_none_when_no_active_multimodal_row(self, db_session):
        db_session.add(_provider(type="multimodal", is_active=False))
        db_session.flush()

        assert load_active_multimodal_provider(db_session) is None

    def test_returns_highest_priority_active_row(self, db_session):
        low = _provider(name="huggingface", type="multimodal", priority=2)
        high = _provider(name="gemini", type="multimodal", priority=1)
        db_session.add_all([low, high])
        db_session.flush()

        result = load_active_multimodal_provider(db_session)

        assert result["model"] == high.model
        assert result["name"] == "gemini"


class TestLoadEnabledMetricDefinitions:
    def _definition(self, db_session, metric_key: str, enabled: bool = True) -> MetricDefinition:
        d = MetricDefinition(metric_key=metric_key, label_i18n_key=f"metrics.{metric_key}", enabled=enabled)
        db_session.add(d)
        db_session.flush()
        return d

    def test_joins_providers_of_enabled_metrics_in_key_then_priority_order(self, db_session):
        citations = self._definition(db_session, "citation_count")
        downloads = self._definition(db_session, "download_count")
        db_session.add_all([
            MetricProvider(metric_definition_id=citations.id, provider_name="semantic_scholar",
                           priority=2, extractor_type="json_path", extractor_spec={"path": "citationCount"}),
            MetricProvider(metric_definition_id=citations.id, provider_name="openalex",
                           priority=1, extractor_type="json_path", extractor_spec={"path": "cited_by_count"}),
            MetricProvider(metric_definition_id=downloads.id, provider_name="openalex",
                           priority=1, extractor_type="code", extractor_spec={"key": "downloads"}),
        ])
        db_session.flush()

        result = load_enabled_metric_definitions(db_session)

        assert [(r["metric_key"], r["provider_name"], r["priority"]) for r in result] == [
            ("citation_count", "openalex", 1),
            ("citation_count", "semantic_scholar", 2),
            ("download_count", "openalex", 1),
        ]
        assert result[0]["extractor_type"] == "json_path"
        assert result[0]["extractor_spec"] == {"path": "cited_by_count"}

    def test_excludes_providers_of_disabled_metrics(self, db_session):
        disabled = self._definition(db_session, "disabled_metric", enabled=False)
        db_session.add(MetricProvider(metric_definition_id=disabled.id, provider_name="openalex",
                                      priority=1, extractor_type="json_path", extractor_spec={"path": "x"}))
        db_session.flush()

        assert load_enabled_metric_definitions(db_session) == []
