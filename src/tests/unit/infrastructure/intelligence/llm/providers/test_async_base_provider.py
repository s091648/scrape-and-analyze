import pytest
import tenacity
from unittest.mock import AsyncMock

from src.infrastructure.intelligence.llm.rate_limit import RateLimitExhausted, RateLimitKind
from src.infrastructure.intelligence.llm.providers.async_base_provider import AsyncBaseProvider


class _DummyProvider(AsyncBaseProvider):
    """Minimal concrete AsyncBaseProvider for exercising the base template
    methods directly, independent of any real SDK."""

    def __init__(self, model="dummy-model", classify_result=None):
        super().__init__(model=model)
        self._classify_result = classify_result
        self.call_api = AsyncMock()
        self.call_api_raw = AsyncMock()

    async def _call_api(self, content, prompt):
        return await self.call_api(content, prompt)

    async def _call_api_raw(self, content, prompt):
        return await self.call_api_raw(content, prompt)

    def _classify_rate_limit(self, exc):
        if self._classify_result is not None:
            return self._classify_result
        return super()._classify_rate_limit(exc)


def _valid_result():
    return {
        "tag_groups": [],
        "pain_points": "p",
        "insights": "i",
        "innovations": "n",
        "summary": "s",
    }


def test_default_classify_rate_limit_returns_none():
    provider = _DummyProvider()
    assert provider._classify_rate_limit(Exception("boom")) is None


def test_is_translate_retryable_false_for_rate_limit_exhausted():
    provider = _DummyProvider()
    assert provider._is_translate_retryable(RateLimitExhausted("x")) is False


def test_is_translate_retryable_true_for_other_errors():
    provider = _DummyProvider()
    assert provider._is_translate_retryable(ValueError("x")) is True


def test_is_translate_retryable_false_when_classified_rpd():
    provider = _DummyProvider(classify_result=RateLimitKind.RPD)
    assert provider._is_translate_retryable(ValueError("x")) is False


@pytest.mark.asyncio
async def test_analyze_propagates_rate_limit_exhausted():
    provider = _DummyProvider()
    provider.call_api.side_effect = RateLimitExhausted("done")
    with pytest.raises(RateLimitExhausted):
        await provider.analyze("content", "prompt")


@pytest.mark.asyncio
async def test_analyze_raises_rate_limit_exhausted_when_classified_rpd():
    provider = _DummyProvider(classify_result=RateLimitKind.RPD)
    provider.call_api.side_effect = ValueError("quota gone")
    with pytest.raises(RateLimitExhausted):
        await provider.analyze("content", "prompt")


@pytest.mark.asyncio
async def test_analyze_returns_none_for_invalid_result():
    provider = _DummyProvider()
    provider.call_api.return_value = {"pain_points": "p"}
    result = await provider.analyze("content", "prompt")
    assert result is None


@pytest.mark.asyncio
async def test_analyze_returns_parsed_result_on_success():
    provider = _DummyProvider()
    provider.call_api.return_value = _valid_result()
    result = await provider.analyze("content", "prompt")
    assert result is not None
    content, metadata = result
    assert metadata.model_used == "dummy-model"


@pytest.mark.asyncio
async def test_translate_propagates_rate_limit_exhausted():
    provider = _DummyProvider()
    provider.call_api_raw.side_effect = RateLimitExhausted("done")
    with pytest.raises(RateLimitExhausted):
        await provider.translate("content", "prompt")


@pytest.mark.asyncio
async def test_translate_raises_rate_limit_exhausted_when_classified_rpd():
    provider = _DummyProvider(classify_result=RateLimitKind.RPD)
    provider.call_api_raw.side_effect = ValueError("quota gone")
    with pytest.raises(RateLimitExhausted):
        await provider.translate("content", "prompt")


@pytest.mark.asyncio
async def test_translate_returns_none_on_generic_error():
    provider = _DummyProvider()
    provider._translate_retry.wait = tenacity.wait_none()
    provider.call_api_raw.side_effect = ValueError("boom")
    result = await provider.translate("content", "prompt")
    assert result is None


@pytest.mark.asyncio
async def test_translate_returns_none_for_empty_text():
    provider = _DummyProvider()
    provider.call_api_raw.return_value = "   "
    result = await provider.translate("content", "prompt")
    assert result is None


@pytest.mark.asyncio
async def test_generate_returns_text_on_success():
    provider = _DummyProvider()
    provider.call_api_raw.return_value = "generated text"
    result = await provider.generate("prompt")
    assert result == "generated text"
    provider.call_api_raw.assert_awaited_once_with("", "prompt")


@pytest.mark.asyncio
async def test_generate_propagates_rate_limit_exhausted():
    provider = _DummyProvider()
    provider.call_api_raw.side_effect = RateLimitExhausted("done")
    with pytest.raises(RateLimitExhausted):
        await provider.generate("prompt")


@pytest.mark.asyncio
async def test_generate_raises_rate_limit_exhausted_when_classified_rpd():
    provider = _DummyProvider(classify_result=RateLimitKind.RPD)
    provider.call_api_raw.side_effect = ValueError("quota gone")
    with pytest.raises(RateLimitExhausted):
        await provider.generate("prompt")


@pytest.mark.asyncio
async def test_generate_returns_none_on_generic_error():
    provider = _DummyProvider()
    provider._translate_retry.wait = tenacity.wait_none()
    provider.call_api_raw.side_effect = ValueError("boom")
    result = await provider.generate("prompt")
    assert result is None


@pytest.mark.asyncio
async def test_generate_returns_none_for_empty_text():
    provider = _DummyProvider()
    provider.call_api_raw.return_value = ""
    result = await provider.generate("prompt")
    assert result is None
