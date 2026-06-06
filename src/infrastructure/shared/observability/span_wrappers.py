"""
Span wrapper factories for event-handler tracing in bootstrap.py.

with_span           — runs fn inside a named span with error recording.
                       Use for handlers that don't publish events (e.g. failed-task persistence).

with_span_deferred   — runs fn inside a span, but defers any event_bus.publish()
                       calls until AFTER the span closes. This makes downstream
                       handler spans siblings of the current span rather than
                       deeply nested children.

with_article_pipeline_span — creates an article.pipeline parent span with article
                              metadata, then delegates to with_span_deferred for
                              the article.scraped.handle child.
"""
from opentelemetry import trace as _otel
from opentelemetry.trace import StatusCode
from src.infrastructure.shared.logging import bind_topic_id


def with_span(span_name: str, fn, tracer):
    """
    Returns a wrapper that runs fn inside a named span.
    Records exceptions and sets ERROR status on failure.
    Use for handlers that don't need event-bus deferral.
    """
    def _wrapper(event):
        with tracer.start_as_current_span(span_name) as span:
            try:
                return fn(event)
            except Exception as e:
                span.record_exception(e)
                span.set_status(StatusCode.ERROR, str(e))
                raise
    return _wrapper


def with_span_deferred(span_name: str, fn, bus, tracer):
    """
    Returns a wrapper that runs fn inside a named span.
    Any event_bus.publish() calls made by fn are collected and replayed
    after the span closes, so downstream spans share the same parent context.
    """
    def _wrapper(event):
        deferred = []
        orig = bus.publish
        bus.publish = lambda e: deferred.append(e)
        with tracer.start_as_current_span(span_name) as span:
            try:
                result = fn(event)
            except Exception as e:
                span.record_exception(e)
                span.set_status(StatusCode.ERROR, str(e))
                raise
            finally:
                bus.publish = orig
        for evt in deferred:
            bus.publish(evt)
        return result
    return _wrapper


def with_article_pipeline_span(fn, bus, tracer, pipeline_span_name: str, scraped_span_name: str):
    """
    Creates an article.pipeline parent span with article.url, article.source, and
    article.topic_id, then wraps fn with with_span_deferred under that parent.
    Only used for ArticleScrapedEvent (which has .url, .source, .topic_id directly).
    """
    def _wrapper(event):
        topic_id = getattr(event, 'topic_id', None)
        if topic_id:
            bind_topic_id(str(topic_id))
        with tracer.start_as_current_span(pipeline_span_name) as ps:
            ps.set_attribute("article.url", event.url)
            ps.set_attribute("article.source", event.source)
            if topic_id:
                ps.set_attribute("article.topic_id", str(topic_id))
            original_source = (getattr(event, 'metadata', None) or {}).get('original_source')
            if original_source:
                ps.set_attribute("article.original_source", original_source)
            return with_span_deferred(scraped_span_name, fn, bus, tracer)(event)
    return _wrapper