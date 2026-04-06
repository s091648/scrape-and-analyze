"""
Tests for OTel tracer helpers in src/observability/tracing.py.

The span-level tests for analyze_article / process_article were removed
when those functions were replaced by AnalyzeArticleUseCase /
ProcessArticleUseCase (Phase 9 DDD migration).
"""
from opentelemetry import trace as otel_trace


def test_get_tracer_returns_tracer_instance():
    from src.observability.tracing import get_tracer
    tracer = get_tracer()
    assert tracer is not None
    assert isinstance(tracer, otel_trace.Tracer)


def test_shutdown_tracing_does_not_raise_when_no_provider(monkeypatch):
    import src.observability.tracing as tracing_module
    monkeypatch.setattr(tracing_module, "_provider", None)
    from src.observability.tracing import shutdown_tracing
    shutdown_tracing()  # must not raise
