import uuid
from unittest.mock import MagicMock, patch
from src.shared.domain.entities import Article
from src.modules.collection.application.use_cases import ArticleOutcome, PipelineStats
from src.modules.collection.application.events import ArticleScrapedEvent


def _make_dto(source="arxiv") -> ArticleScrapedEvent:
    return ArticleScrapedEvent(url="https://example.com", title="T", content="C", source=source)


def _make_article():
    return Article(url="https://example.com", url_hash="a" * 64, source="arxiv", title="T", content="C")


def test_handle_new_article_records_new_publishes_event_and_returns_true():
    from src.modules.collection.application.event_handlers import ArticleScrapedHandler
    use_case = MagicMock()
    use_case.execute.return_value = (ArticleOutcome.NEW, _make_article())
    stats = PipelineStats()
    event_bus = MagicMock()

    handler = ArticleScrapedHandler(use_case=use_case, pipeline_stats=stats, event_bus=event_bus)
    result = handler.handle(_make_dto("arxiv"))

    assert result is True
    assert stats.get_results()[0].new == 1
    assert stats.get_results()[0].duplicate == 0
    event_bus.publish.assert_called_once()


def test_handle_duplicate_article_records_duplicate_and_returns_true():
    from src.modules.collection.application.event_handlers import ArticleScrapedHandler
    use_case = MagicMock()
    use_case.execute.return_value = (ArticleOutcome.DUPLICATE, None)
    stats = PipelineStats()
    event_bus = MagicMock()

    handler = ArticleScrapedHandler(use_case=use_case, pipeline_stats=stats, event_bus=event_bus)
    result = handler.handle(_make_dto("rss"))

    assert result is True
    assert stats.get_results()[0].duplicate == 1
    event_bus.publish.assert_not_called()


def test_handle_failed_article_records_failed_and_returns_false():
    from src.modules.collection.application.event_handlers import ArticleScrapedHandler
    use_case = MagicMock()
    use_case.execute.return_value = (ArticleOutcome.FAILED, None)
    stats = PipelineStats()
    event_bus = MagicMock()

    handler = ArticleScrapedHandler(use_case=use_case, pipeline_stats=stats, event_bus=event_bus)
    result = handler.handle(_make_dto("blog"))

    assert result is False
    assert stats.get_results()[0].failed == 1
    event_bus.publish.assert_not_called()


def test_handle_duplicate_needs_analysis_publishes_event_and_returns_true():
    from src.modules.collection.application.event_handlers import ArticleScrapedHandler
    use_case = MagicMock()
    use_case.execute.return_value = (ArticleOutcome.DUPLICATE_NEEDS_ANALYSIS, _make_article())
    stats = PipelineStats()
    event_bus = MagicMock()

    handler = ArticleScrapedHandler(use_case=use_case, pipeline_stats=stats, event_bus=event_bus)
    result = handler.handle(_make_dto("arxiv"))

    assert result is True
    event_bus.publish.assert_called_once()


# ── Span attribute tests ──────────────────────────────────────────────────────

def _make_handler():
    from src.modules.collection.application.event_handlers import ArticleScrapedHandler
    use_case = MagicMock()
    event_bus = MagicMock()
    return ArticleScrapedHandler(use_case=use_case, pipeline_stats=PipelineStats(), event_bus=event_bus), use_case


def test_span_records_article_url_and_source():
    handler, use_case = _make_handler()
    article = _make_article()
    use_case.execute.return_value = (ArticleOutcome.NEW, article)
    event = ArticleScrapedEvent(url="https://feed.example.com/post/1", title="T", content="C", source="rss")
    mock_span = MagicMock()

    with patch("opentelemetry.trace.get_current_span", return_value=mock_span):
        handler.handle(event)

    mock_span.set_attribute.assert_any_call("article.url", "https://feed.example.com/post/1")
    mock_span.set_attribute.assert_any_call("article.source", "rss")


def test_span_records_outcome_new():
    handler, use_case = _make_handler()
    article = _make_article()
    use_case.execute.return_value = (ArticleOutcome.NEW, article)
    mock_span = MagicMock()

    with patch("opentelemetry.trace.get_current_span", return_value=mock_span):
        handler.handle(_make_dto())

    mock_span.set_attribute.assert_any_call("article.outcome", "new")


def test_span_records_article_id_when_new():
    handler, use_case = _make_handler()
    article = _make_article()
    use_case.execute.return_value = (ArticleOutcome.NEW, article)
    mock_span = MagicMock()

    with patch("opentelemetry.trace.get_current_span", return_value=mock_span):
        handler.handle(_make_dto())

    mock_span.set_attribute.assert_any_call("article.id", str(article.id))


def test_span_records_outcome_duplicate():
    handler, use_case = _make_handler()
    use_case.execute.return_value = (ArticleOutcome.DUPLICATE, None)
    mock_span = MagicMock()

    with patch("opentelemetry.trace.get_current_span", return_value=mock_span):
        handler.handle(_make_dto())

    mock_span.set_attribute.assert_any_call("article.outcome", "duplicate")
