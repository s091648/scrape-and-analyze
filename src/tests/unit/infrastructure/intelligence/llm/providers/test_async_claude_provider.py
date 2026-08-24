import pytest
from unittest.mock import AsyncMock, MagicMock, patch


def _make_response_text():
    return '{"tag_groups":[],"pain_points":"none","insights":"test","innovations":"new","summary":"s"}'


def _make_mock_response(text=None, input_tokens=100, output_tokens=50):
    mock_response = MagicMock()
    mock_response.content = [MagicMock(text=text or _make_response_text())]
    mock_response.usage.input_tokens = input_tokens
    mock_response.usage.output_tokens = output_tokens
    return mock_response


def _patch_anthropic():
    return patch('src.infrastructure.intelligence.llm.providers.async_claude_provider.anthropic')


def test_async_claude_provider_inherits_from_async_base_provider():
    from src.infrastructure.intelligence.llm.providers.async_claude_provider import AsyncClaudeProvider
    from src.infrastructure.intelligence.llm.providers.async_base_provider import AsyncBaseProvider
    assert issubclass(AsyncClaudeProvider, AsyncBaseProvider)


@pytest.mark.asyncio
async def test_async_claude_provider_calls_anthropic_api():
    with _patch_anthropic() as mock_anthropic:
        from src.infrastructure.intelligence.llm.providers.async_claude_provider import AsyncClaudeProvider
        mock_anthropic.AsyncAnthropic.return_value.messages.create = AsyncMock(
            return_value=_make_mock_response()
        )
        provider = AsyncClaudeProvider(api_key="test-key", model="claude-sonnet-4-6")
        result = await provider.analyze("test content", "analyze this")
        assert result is not None
        content, metadata = result
        assert metadata.input_tokens == 100
        assert metadata.output_tokens == 50


@pytest.mark.asyncio
async def test_async_claude_provider_retries_on_transient_error():
    with _patch_anthropic() as mock_anthropic:
        from src.infrastructure.intelligence.llm.providers.async_claude_provider import AsyncClaudeProvider
        mock_anthropic.AsyncAnthropic.return_value.messages.create = AsyncMock(
            side_effect=[Exception("Temporary error"), _make_mock_response()]
        )
        provider = AsyncClaudeProvider(api_key="test-key", model="claude-sonnet-4-6")
        result = await provider.analyze("test", "prompt")
        assert mock_anthropic.AsyncAnthropic.return_value.messages.create.await_count == 2
        assert result is not None


@pytest.mark.asyncio
async def test_async_claude_provider_handles_invalid_json():
    with _patch_anthropic() as mock_anthropic:
        from src.infrastructure.intelligence.llm.providers.async_claude_provider import AsyncClaudeProvider
        mock_anthropic.AsyncAnthropic.return_value.messages.create = AsyncMock(
            return_value=_make_mock_response("not valid json")
        )
        provider = AsyncClaudeProvider(api_key="test-key", model="claude-sonnet-4-6")
        result = await provider.analyze("test", "prompt")
        assert result is None


@pytest.mark.asyncio
async def test_async_claude_provider_retries_on_rate_limit():
    with _patch_anthropic() as mock_anthropic:
        from src.infrastructure.intelligence.llm.providers.async_claude_provider import AsyncClaudeProvider
        import anthropic

        rate_limit_error = anthropic.RateLimitError(
            message="Rate limit exceeded",
            response=MagicMock(status_code=429),
            body={}
        )
        mock_anthropic.AsyncAnthropic.return_value.messages.create = AsyncMock(
            side_effect=[rate_limit_error, rate_limit_error, _make_mock_response()]
        )
        provider = AsyncClaudeProvider(api_key="test-key", model="claude-sonnet-4-6")
        result = await provider.analyze("test", "prompt")
        assert result is not None
        assert mock_anthropic.AsyncAnthropic.return_value.messages.create.await_count == 3


@pytest.mark.asyncio
async def test_async_claude_provider_translate():
    with _patch_anthropic() as mock_anthropic:
        from src.infrastructure.intelligence.llm.providers.async_claude_provider import AsyncClaudeProvider
        mock_anthropic.AsyncAnthropic.return_value.messages.create = AsyncMock(
            return_value=_make_mock_response(text="translated text")
        )
        provider = AsyncClaudeProvider(api_key="test-key", model="claude-sonnet-4-6")
        result = await provider.translate("test", "translate this")
        assert result == "translated text"
