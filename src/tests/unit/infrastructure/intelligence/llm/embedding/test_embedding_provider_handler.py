from unittest.mock import MagicMock
from src.infrastructure.intelligence.llm.resilient_llm_service import EmbeddingProviderHandler
from src.infrastructure.intelligence.llm.rate_limit import QuotaStrategy


def _make_provider(vectors):
    provider = MagicMock()
    provider.embed.return_value = vectors[0]
    provider.embed_batch.return_value = vectors
    provider.count_tokens.return_value = len(vectors[0])
    return provider


def _make_handler(provider, strategy):
    return EmbeddingProviderHandler(
        provider=provider,
        strategy=strategy,
        priority=1,
        name="test",
    )


def test_embed_calls_acquire_and_record_usage():
    mock_strategy = MagicMock(spec=QuotaStrategy)
    provider = _make_provider([[0.1] * 768])
    handler = _make_handler(provider, mock_strategy)

    handler.embed("hello world")

    mock_strategy.acquire.assert_called_once()
    mock_strategy.record_usage.assert_called_once()
    provider.embed.assert_called_once_with("hello world")


def test_embed_batch_calls_acquire_and_record_usage_once():
    mock_strategy = MagicMock(spec=QuotaStrategy)
    provider = _make_provider([[0.1] * 768, [0.2] * 768])
    handler = _make_handler(provider, mock_strategy)

    handler.embed_batch(["text one", "text two"])

    mock_strategy.acquire.assert_called_once()
    mock_strategy.record_usage.assert_called_once()
    provider.embed_batch.assert_called_once_with(["text one", "text two"])


def test_acquire_token_estimate_scales_with_text_length():
    mock_strategy = MagicMock(spec=QuotaStrategy)
    provider = _make_provider([[0.1] * 768])
    handler = _make_handler(provider, mock_strategy)

    handler.embed("a" * 400)

    acquired = mock_strategy.acquire.call_args[0][0]
    assert acquired == 100  # 400 chars // 4
