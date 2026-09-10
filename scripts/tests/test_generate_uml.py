"""Pipeline-flow inference in scripts/generate_uml.py, run against the real repo.

Regression guard for the 024-async-pipeline-refactor blind spots: RAG ingestion
(dispatched as the bare `dispatch_rag` callable → a detached asyncio.Task, never
`handler.handle`) and per-article translation (an inline use-case call inside
AnalysisCompletedHandler.handle(), named after its trigger event) both fell off
the auto-generated Pipeline Flow diagram. They're recovered by leaning on the
OTel span vocabulary (shared/enums/observability.py::SpanName) — see the
"Span-driven augmentation" block in generate_uml.py and site/guide/architecture/
uml.md. These tests fail loudly if that wiring regresses or the SpanName enum
drifts out from under the override list.
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

import scripts.generate_uml as gen  # noqa: E402


@pytest.fixture(scope="module")
def stages() -> list[dict]:
    result = gen.build_pipeline_from_bootstrap()
    assert result, "pipeline inference produced nothing — bootstrap.py unparseable?"
    return result


def _by_label(stages, label):
    return next((s for s in stages if s["label"] == label), None)


def test_rag_ingestion_is_a_stage(stages):
    rag = _by_label(stages, "RAG Ingestion")
    assert rag is not None, "RAG ingestion stage missing from the pipeline flow"
    assert rag["classes"][0] == "AsyncRagIngestionHandler"
    assert "AsyncIngestArticleForRagUseCase" in rag["classes"]


def test_rag_fans_out_from_article_processed(stages):
    """RAG dispatch and the analyze chain both hang off ArticleProcessedEvent —
    they must render in the same parallel (fan-out) group."""
    rag = _by_label(stages, "RAG Ingestion")
    processed = _by_label(stages, "Article Processed")
    assert rag["receives"] == ["ArticleProcessedEvent"]
    assert rag["parallel_group"]
    assert rag["parallel_group"] == processed["parallel_group"]


def test_rag_failure_branch_present(stages):
    rag = _by_label(stages, "RAG Ingestion")
    assert any("Rag Ingestion Failed" in b["label"] for b in rag["branches"])


def test_translation_stage_is_named_from_its_span_not_its_trigger(stages):
    """AnalysisCompletedHandler opens article.translate.handle — the stage should
    read "Translation", not "Analysis Completed"."""
    assert _by_label(stages, "Translation") is not None
    assert _by_label(stages, "Analysis Completed") is None
    tr = _by_label(stages, "Translation")
    assert tr["classes"][0] == "AnalysisCompletedHandler"
    assert any(c.startswith("AsyncTranslate") for c in tr["classes"])
    assert tr["icon"] == "🌐"


def test_every_subscribed_handler_appears_in_some_stage(stages):
    """No handler wired via subscribe() (or the bare-callable map) is silently
    dropped from the diagram — bare-callable RAG included."""
    staged = {c for s in stages for c in s["classes"]}
    staged |= {b_cls for s in stages for b in s["branches"] for b_cls in b["classes"]}
    expected = {"ArticleScrapedHandler", "ArticleProcessedHandler",
                "TagNormalizationHandler", "AnalysisCompletedHandler",
                "AsyncRagIngestionHandler", "FailedTaskPersistenceHandler"}
    assert expected <= staged, f"missing from pipeline: {expected - staged}"


def test_stage_order_is_stable_and_barriers_come_last(stages):
    labels = [s["label"] for s in stages]
    assert labels[0] == "Collection Pipeline"
    # text-content barrier (search + cache) before the everything-done barrier
    # (metrics / notify), matching build_collection_pipeline()'s wiring order.
    assert labels.index("Search Index Rebuild") < labels.index("Otel Metrics")
    # a second call yields byte-identical ordering (no set-iteration flake)
    assert [s["label"] for s in gen.build_pipeline_from_bootstrap()] == labels


def test_span_label_overrides_are_all_real_spans(stages):
    """Each key in _SPAN_LABEL_OVERRIDES must be a span some handler actually
    opens — otherwise the override is dead and the enum has drifted."""
    opened = {sp for spans in gen._build_class_span_map().values() for sp in spans}
    unknown = set(gen._SPAN_LABEL_OVERRIDES) - opened
    assert not unknown, f"override spans no handler opens: {unknown}"


def test_bare_callable_handlers_resolve_to_real_classes(stages):
    span_classes = set(gen._build_class_span_map())
    for _name, (cls, _related) in gen._BARE_CALLABLE_HANDLERS.items():
        assert cls in span_classes, f"{cls} not found (renamed? deleted?)"


def test_pipeline_stage_shape_is_renderable(stages):
    """UmlViewer.vue reads these keys per stage — keep the contract."""
    for s in stages:
        assert isinstance(s["id"], str) and s["id"]
        assert isinstance(s["step"], int)
        assert isinstance(s["receives"], list)
        assert isinstance(s["emits"], list)
        assert isinstance(s["branches"], list)
        assert isinstance(s["classes"], list)
        for b in s["branches"]:
            assert isinstance(b["emits"], list) and b["emits"]
