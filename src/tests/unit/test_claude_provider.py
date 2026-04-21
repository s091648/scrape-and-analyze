import pytest
from unittest.mock import Mock, patch, MagicMock


def _make_response_text():
    return '{"tag_groups":[],"pain_points":"none","insights":"test","innovations":"new","summary":"s"}'


def _make_mock_response(text=None, input_tokens=100, output_tokens=50):
    mock_response = MagicMock()
    mock_response.content = [MagicMock(text=text or _make_response_text())]
    mock_response.usage.input_tokens = input_tokens
    mock_response.usage.output_tokens = output_tokens
    return mock_response


def test_claude_provider_inherits_from_base_provider():
    from src.infrastructure.intelligence.llm.providers.claude_provider import ClaudeProvider
    from src.infrastructure.intelligence.llm.providers.base_provider import BaseProvider
    assert issubclass(ClaudeProvider, BaseProvider)


def test_claude_provider_calls_anthropic_api():
    with patch('src.infrastructure.intelligence.llm.providers.claude_provider.anthropic') as mock_anthropic:
        from src.infrastructure.intelligence.llm.providers.claude_provider import ClaudeProvider
        mock_anthropic.Anthropic.return_value.messages.create.return_value = _make_mock_response(
            '{"tag_groups":[{"display_name":"DT","description":"d"}],"pain_points":"none","insights":"test","innovations":"new","summary":"s"}'
        )
        provider = ClaudeProvider(api_key="test-key", model="claude-sonnet-4-6")
        result = provider.analyze("test content", "analyze this")
        assert result is not None
        content, metadata = result
        assert metadata.input_tokens == 100
        assert metadata.output_tokens == 50


def test_claude_provider_retries_on_transient_error():
    with patch('src.infrastructure.intelligence.llm.providers.claude_provider.anthropic') as mock_anthropic:
        from src.infrastructure.intelligence.llm.providers.claude_provider import ClaudeProvider
        mock_anthropic.Anthropic.return_value.messages.create.side_effect = [
            Exception("Temporary error"),
            _make_mock_response(),
        ]
        provider = ClaudeProvider(api_key="test-key", model="claude-sonnet-4-6")
        result = provider.analyze("test", "prompt")
        assert mock_anthropic.Anthropic.return_value.messages.create.call_count == 2
        assert result is not None


def test_claude_provider_handles_invalid_json():
    with patch('src.infrastructure.intelligence.llm.providers.claude_provider.anthropic') as mock_anthropic:
        from src.infrastructure.intelligence.llm.providers.claude_provider import ClaudeProvider
        mock_anthropic.Anthropic.return_value.messages.create.return_value = _make_mock_response("not valid json")
        provider = ClaudeProvider(api_key="test-key", model="claude-sonnet-4-6")
        result = provider.analyze("test", "prompt")
        assert result is None


def test_claude_provider_tracks_token_usage():
    with patch('src.infrastructure.intelligence.llm.providers.claude_provider.anthropic') as mock_anthropic:
        from src.infrastructure.intelligence.llm.providers.claude_provider import ClaudeProvider
        mock_anthropic.Anthropic.return_value.messages.create.return_value = _make_mock_response(
            input_tokens=500, output_tokens=200
        )
        provider = ClaudeProvider(api_key="test-key", model="claude-sonnet-4-6")
        result = provider.analyze("test content", "analyze")
        assert result is not None
        _, metadata = result
        assert metadata.input_tokens == 500
        assert metadata.output_tokens == 200


def test_claude_provider_retries_on_rate_limit():
    with patch('src.infrastructure.intelligence.llm.providers.claude_provider.anthropic') as mock_anthropic:
        from src.infrastructure.intelligence.llm.providers.claude_provider import ClaudeProvider
        import anthropic

        rate_limit_error = anthropic.RateLimitError(
            message="Rate limit exceeded",
            response=MagicMock(status_code=429),
            body={}
        )
        mock_anthropic.Anthropic.return_value.messages.create.side_effect = [
            rate_limit_error,
            rate_limit_error,
            _make_mock_response(),
        ]
        provider = ClaudeProvider(api_key="test-key", model="claude-sonnet-4-6")
        result = provider.analyze("test", "prompt")
        assert result is not None
        assert mock_anthropic.Anthropic.return_value.messages.create.call_count == 3


def test_claude_provider_gives_up_after_max_retries():
    with patch('src.infrastructure.intelligence.llm.providers.claude_provider.anthropic') as mock_anthropic:
        from src.infrastructure.intelligence.llm.providers.claude_provider import ClaudeProvider
        import anthropic

        api_error = anthropic.APIError(message="Server error", request=MagicMock(), body={})
        mock_anthropic.Anthropic.return_value.messages.create.side_effect = api_error
        provider = ClaudeProvider(api_key="test-key", model="claude-sonnet-4-6")
        result = provider.analyze("test", "prompt")
        assert result is None
        assert mock_anthropic.Anthropic.return_value.messages.create.call_count == 3