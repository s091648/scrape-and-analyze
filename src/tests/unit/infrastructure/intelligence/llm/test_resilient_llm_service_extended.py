import pytest
from unittest.mock import MagicMock
from src.modules.intelligence.domain.value_objects import AnalysisContent, AnalysisMetadata
from src.infrastructure.intelligence.llm.rate_limit import RateLimitExhausted


def _make_result():
    content = AnalysisContent(tag_groups=[], pain_points='p', insights='i',
                               innovations='n', summary='s')
    metadata = AnalysisMetadata(model_used='test', input_tokens=100, output_tokens=50)
    return (content, metadata)


def _make_handler(name='test', priority=1, analyze_return=_make_result(), analyze_side_effect=None):
    from src.infrastructure.intelligence.llm.resilient_llm_service import ProviderHandler
    provider = MagicMock()
    strategy = MagicMock()
    if analyze_side_effect:
        provider.analyze.side_effect = analyze_side_effect
    else:
        provider.analyze.return_value = analyze_return
    return ProviderHandler(provider=provider, strategy=strategy, priority=priority, name=name)


class TestProviderHandlerAnalyze:
    def test_acquire_called_with_estimated_tokens(self):
        handler = _make_handler()
        handler.analyze("a" * 400, "prompt")
        handler.strategy.acquire.assert_called_once_with(estimated_tokens=100)

    def test_record_usage_called_on_success(self):
        handler = _make_handler()
        handler.analyze("content", "prompt")
        handler.strategy.record_usage.assert_called_once_with(150)  # input + output

    def test_record_usage_not_called_on_none_result(self):
        handler = _make_handler(analyze_return=None)
        handler.analyze("content", "prompt")
        handler.strategy.record_usage.assert_not_called()


class TestProviderHandlerTranslate:
    def test_translate_calls_acquire(self):
        handler = _make_handler()
        handler.provider.translate.return_value = "translated"
        handler.translate("content", "prompt")
        handler.strategy.acquire.assert_called_once()

    def test_translate_records_usage(self):
        handler = _make_handler()
        handler.provider.translate.return_value = "translated output"
        handler.translate("some content here", "prompt")
        handler.strategy.record_usage.assert_called_once()

    def test_translate_no_record_on_none(self):
        handler = _make_handler()
        handler.provider.translate.return_value = None
        handler.translate("content", "prompt")
        handler.strategy.record_usage.assert_not_called()


class TestResilientLLMServiceAnalyze:
    def test_returns_first_successful_result(self):
        from src.infrastructure.intelligence.llm.resilient_llm_service import ResilientLLMService
        h1 = _make_handler(name='p1', priority=1, analyze_return=_make_result())
        service = ResilientLLMService([h1])
        result = service.analyze("content", "prompt")
        assert result is not None
        content, _ = result
        assert content.pain_points == 'p'

    def test_falls_back_on_rate_limit_exhausted(self):
        from src.infrastructure.intelligence.llm.resilient_llm_service import ResilientLLMService
        h1 = _make_handler(name='p1', priority=1, analyze_side_effect=RateLimitExhausted("limit"))
        h2 = _make_handler(name='p2', priority=2, analyze_return=_make_result())
        service = ResilientLLMService([h1, h2])
        result = service.analyze("content", "prompt")
        assert result is not None

    def test_falls_back_on_generic_exception(self):
        from src.infrastructure.intelligence.llm.resilient_llm_service import ResilientLLMService
        h1 = _make_handler(name='p1', priority=1, analyze_side_effect=RuntimeError("fail"))
        h2 = _make_handler(name='p2', priority=2, analyze_return=_make_result())
        service = ResilientLLMService([h1, h2])
        result = service.analyze("content", "prompt")
        assert result is not None

    def test_falls_back_on_none_result(self):
        from src.infrastructure.intelligence.llm.resilient_llm_service import ResilientLLMService
        h1 = _make_handler(name='p1', priority=1, analyze_return=None)
        h2 = _make_handler(name='p2', priority=2, analyze_return=_make_result())
        service = ResilientLLMService([h1, h2])
        result = service.analyze("content", "prompt")
        assert result is not None

    def test_returns_none_when_all_exhausted(self):
        from src.infrastructure.intelligence.llm.resilient_llm_service import ResilientLLMService
        h1 = _make_handler(name='p1', priority=1, analyze_side_effect=RateLimitExhausted("limit"))
        h2 = _make_handler(name='p2', priority=2, analyze_side_effect=RateLimitExhausted("limit"))
        service = ResilientLLMService([h1, h2])
        result = service.analyze("content", "prompt")
        assert result is None

    def test_rate_limited_handler_moved_to_end(self):
        from src.infrastructure.intelligence.llm.resilient_llm_service import ResilientLLMService
        h1 = _make_handler(name='p1', priority=1, analyze_side_effect=RateLimitExhausted("limit"))
        h2 = _make_handler(name='p2', priority=2, analyze_return=_make_result())
        service = ResilientLLMService([h1, h2])
        service.analyze("content", "prompt")
        assert service._handlers[0].name == 'p2'
        assert service._handlers[1].name == 'p1'

    def test_handlers_sorted_by_priority(self):
        from src.infrastructure.intelligence.llm.resilient_llm_service import ResilientLLMService
        h2 = _make_handler(name='p2', priority=2)
        h1 = _make_handler(name='p1', priority=1)
        service = ResilientLLMService([h2, h1])
        assert service._handlers[0].name == 'p1'
        assert service._handlers[1].name == 'p2'


class TestResilientLLMServiceTranslate:
    def test_translate_returns_first_success(self):
        from src.infrastructure.intelligence.llm.resilient_llm_service import ResilientLLMService
        h1 = _make_handler(name='p1', priority=1)
        h1.provider.translate.return_value = "hello"
        service = ResilientLLMService([h1])
        result = service.translate("content", "prompt")
        assert result == "hello"

    def test_translate_falls_back_on_rate_limit(self):
        from src.infrastructure.intelligence.llm.resilient_llm_service import ResilientLLMService
        h1 = _make_handler(name='p1', priority=1)
        h1.provider.translate.side_effect = RateLimitExhausted("limit")
        h2 = _make_handler(name='p2', priority=2)
        h2.provider.translate.return_value = "fallback"
        service = ResilientLLMService([h1, h2])
        result = service.translate("content", "prompt")
        assert result == "fallback"

    def test_translate_returns_none_when_all_fail(self):
        from src.infrastructure.intelligence.llm.resilient_llm_service import ResilientLLMService
        h1 = _make_handler(name='p1', priority=1)
        h1.provider.translate.side_effect = RuntimeError("fail")
        service = ResilientLLMService([h1])
        result = service.translate("content", "prompt")
        assert result is None


class TestEmbeddingProviderHandler:
    def test_embed_calls_acquire_and_record(self):
        from src.infrastructure.intelligence.llm.resilient_llm_service import EmbeddingProviderHandler
        provider = MagicMock()
        provider.embed.return_value = [0.1] * 768
        provider.count_tokens.return_value = 10
        strategy = MagicMock()
        handler = EmbeddingProviderHandler(provider=provider, strategy=strategy, priority=1, name='test')
        result = handler.embed("hello world")
        strategy.acquire.assert_called_once()
        strategy.record_usage.assert_called_once_with(10)
        assert result == [0.1] * 768

    def test_embed_falls_back_to_char_estimate_on_count_tokens_failure(self):
        from src.infrastructure.intelligence.llm.resilient_llm_service import EmbeddingProviderHandler
        provider = MagicMock()
        provider.embed.return_value = [0.1] * 768
        provider.count_tokens.side_effect = RuntimeError("unsupported")
        strategy = MagicMock()
        handler = EmbeddingProviderHandler(provider=provider, strategy=strategy, priority=1, name='test')
        handler.embed("a" * 400)
        # Falls back to len(text)//4 = 100
        strategy.record_usage.assert_called_once_with(100)

    def test_embed_batch_calls_acquire_and_record(self):
        from src.infrastructure.intelligence.llm.resilient_llm_service import EmbeddingProviderHandler
        provider = MagicMock()
        provider.embed_batch.return_value = [[0.1] * 768, [0.2] * 768]
        provider.count_tokens.return_value = 20
        strategy = MagicMock()
        handler = EmbeddingProviderHandler(provider=provider, strategy=strategy, priority=1, name='test')
        result = handler.embed_batch(["text one", "text two"])
        strategy.acquire.assert_called_once()
        strategy.record_usage.assert_called_once_with(20)
        assert len(result) == 2

    def test_embed_disables_count_tokens_after_second_failure(self):
        from src.infrastructure.intelligence.llm.resilient_llm_service import EmbeddingProviderHandler
        provider = MagicMock()
        provider.embed.return_value = [0.1] * 768
        provider.count_tokens.side_effect = RuntimeError("unsupported")
        strategy = MagicMock()
        handler = EmbeddingProviderHandler(provider=provider, strategy=strategy, priority=1, name='test')
        # First call: tries count_tokens, fails
        handler.embed("a" * 400)
        assert handler._can_count_tokens is False
        # Second call: skips count_tokens, uses estimate
        provider.count_tokens.reset_mock()
        handler.embed("b" * 800)
        provider.count_tokens.assert_not_called()
        strategy.record_usage.assert_called_with(200)  # 800//4


class TestResilientEmbeddingService:
    def test_embed_returns_first_success(self):
        from src.infrastructure.intelligence.llm.resilient_llm_service import ResilientEmbeddingService, EmbeddingProviderHandler
        provider = MagicMock()
        provider.embed.return_value = [0.1] * 768
        provider.count_tokens.return_value = 10
        strategy = MagicMock()
        handler = EmbeddingProviderHandler(provider=provider, strategy=strategy, priority=1, name='test')
        service = ResilientEmbeddingService([handler])
        result = service.embed("hello")
        assert result == [0.1] * 768

    def test_embed_falls_back_on_rate_limit(self):
        from src.infrastructure.intelligence.llm.resilient_llm_service import ResilientEmbeddingService, EmbeddingProviderHandler
        h1_provider = MagicMock()
        h1_provider.embed.side_effect = RateLimitExhausted("limit")
        h1 = EmbeddingProviderHandler(provider=h1_provider, strategy=MagicMock(), priority=1, name='p1')
        h2_provider = MagicMock()
        h2_provider.embed.return_value = [0.2] * 768
        h2_provider.count_tokens.return_value = 5
        h2 = EmbeddingProviderHandler(provider=h2_provider, strategy=MagicMock(), priority=2, name='p2')
        service = ResilientEmbeddingService([h1, h2])
        result = service.embed("hello")
        assert result == [0.2] * 768

    def test_embed_batch_returns_first_success(self):
        from src.infrastructure.intelligence.llm.resilient_llm_service import ResilientEmbeddingService, EmbeddingProviderHandler
        provider = MagicMock()
        provider.embed_batch.return_value = [[0.1] * 768, [0.2] * 768]
        provider.count_tokens.return_value = 20
        handler = EmbeddingProviderHandler(provider=provider, strategy=MagicMock(), priority=1, name='test')
        service = ResilientEmbeddingService([handler])
        result = service.embed_batch(["a", "b"])
        assert len(result) == 2

    def test_embed_returns_none_when_all_fail(self):
        from src.infrastructure.intelligence.llm.resilient_llm_service import ResilientEmbeddingService, EmbeddingProviderHandler
        provider = MagicMock()
        provider.embed.side_effect = RuntimeError("fail")
        handler = EmbeddingProviderHandler(provider=provider, strategy=MagicMock(), priority=1, name='test')
        service = ResilientEmbeddingService([handler])
        result = service.embed("hello")
        assert result is None
