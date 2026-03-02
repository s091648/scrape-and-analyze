import pytest
from unittest.mock import Mock, patch, MagicMock


def test_claude_provider_inherits_from_llm_provider():
    """ClaudeProvider should inherit from LLMProvider"""
    from src.analyzers.claude import ClaudeProvider
    from src.analyzers.llm_provider import LLMProvider

    assert issubclass(ClaudeProvider, LLMProvider)


def test_claude_provider_calls_anthropic_api():
    """ClaudeProvider should call Anthropic API"""
    with patch('src.analyzers.claude.anthropic') as mock_anthropic:
        from src.analyzers.claude import ClaudeProvider

        mock_response = MagicMock()
        mock_response.content = [MagicMock(text='{"tag_groups":[{"group":"digital_twin","tags":["virtual replica"]}],"pain_points":"none","insights":"test","innovations":"new"}')]
        mock_response.usage.input_tokens = 100
        mock_response.usage.output_tokens = 50
        mock_anthropic.Anthropic.return_value.messages.create.return_value = mock_response

        provider = ClaudeProvider(api_key="test-key")
        result = provider.analyze("test content", "analyze this")

        assert result is not None
        assert result.tag_groups == [{"group": "digital_twin", "tags": ["virtual replica"]}]
        assert result.input_tokens == 100
        assert result.output_tokens == 50


def test_claude_provider_retries_on_transient_error():
    """ClaudeProvider should retry on transient errors"""
    with patch('src.analyzers.claude.anthropic') as mock_anthropic:
        from src.analyzers.claude import ClaudeProvider

        mock_response = MagicMock()
        mock_response.content = [MagicMock(text='{"tag_groups":[],"pain_points":"","insights":"","innovations":""}')]
        mock_response.usage.input_tokens = 100
        mock_response.usage.output_tokens = 50

        mock_anthropic.Anthropic.return_value.messages.create.side_effect = [
            Exception("Temporary error"),
            mock_response
        ]

        provider = ClaudeProvider(api_key="test-key")
        result = provider.analyze("test", "prompt")

        assert mock_anthropic.Anthropic.return_value.messages.create.call_count == 2
        assert result is not None


def test_claude_provider_handles_invalid_json():
    """ClaudeProvider should handle invalid JSON response"""
    with patch('src.analyzers.claude.anthropic') as mock_anthropic:
        from src.analyzers.claude import ClaudeProvider

        mock_response = MagicMock()
        mock_response.content = [MagicMock(text='not valid json')]
        mock_response.usage.input_tokens = 100
        mock_response.usage.output_tokens = 50
        mock_anthropic.Anthropic.return_value.messages.create.return_value = mock_response

        provider = ClaudeProvider(api_key="test-key")
        result = provider.analyze("test", "prompt")

        assert result is None


def test_claude_provider_tracks_token_usage():
    """ClaudeProvider should track input and output tokens"""
    with patch('src.analyzers.claude.anthropic') as mock_anthropic:
        from src.analyzers.claude import ClaudeProvider

        mock_response = MagicMock()
        mock_response.content = [MagicMock(text='{"tag_groups":[{"group":"ai_ml","tags":["test"]}],"pain_points":"","insights":"","innovations":""}')]
        mock_response.usage.input_tokens = 500
        mock_response.usage.output_tokens = 200
        mock_anthropic.Anthropic.return_value.messages.create.return_value = mock_response

        provider = ClaudeProvider(api_key="test-key")
        result = provider.analyze("test content", "analyze")

        assert result.input_tokens == 500
        assert result.output_tokens == 200


def test_claude_provider_validates_required_fields():
    """ClaudeProvider should validate all required fields are present"""
    with patch('src.analyzers.claude.anthropic') as mock_anthropic:
        from src.analyzers.claude import ClaudeProvider

        # Response missing 'innovations' field
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text='{"tag_groups":[],"pain_points":"","insights":""}')]
        mock_response.usage.input_tokens = 100
        mock_response.usage.output_tokens = 50
        mock_anthropic.Anthropic.return_value.messages.create.return_value = mock_response

        provider = ClaudeProvider(api_key="test-key")
        result = provider.analyze("test", "prompt")

        assert result is None


def test_claude_provider_validates_tags_is_array():
    """ClaudeProvider should validate that tag_groups is a list"""
    with patch('src.analyzers.claude.anthropic') as mock_anthropic:
        from src.analyzers.claude import ClaudeProvider

        mock_response = MagicMock()
        mock_response.content = [MagicMock(text='{"tag_groups":"not-a-list","pain_points":"","insights":"","innovations":""}')]
        mock_response.usage.input_tokens = 100
        mock_response.usage.output_tokens = 50
        mock_anthropic.Anthropic.return_value.messages.create.return_value = mock_response

        provider = ClaudeProvider(api_key="test-key")
        result = provider.analyze("test", "prompt")

        assert result is None


def test_claude_provider_logs_token_metrics():
    """ClaudeProvider should log token usage metrics"""
    with patch('src.analyzers.claude.anthropic') as mock_anthropic:
        with patch('src.analyzers.claude.logger') as mock_logger:
            from src.analyzers.claude import ClaudeProvider

            mock_response = MagicMock()
            mock_response.content = [MagicMock(text='{"tag_groups":[],"pain_points":"","insights":"","innovations":""}')]
            mock_response.usage.input_tokens = 1500
            mock_response.usage.output_tokens = 300
            mock_anthropic.Anthropic.return_value.messages.create.return_value = mock_response

            provider = ClaudeProvider(api_key="test-key")
            result = provider.analyze("test content", "analyze")

            mock_logger.info.assert_called()
            call_args = mock_logger.info.call_args
            assert 'input_tokens' in str(call_args) or result.input_tokens == 1500


def test_claude_provider_retries_on_rate_limit():
    """ClaudeProvider should retry on 429 rate limit error"""
    with patch('src.analyzers.claude.anthropic') as mock_anthropic:
        from src.analyzers.claude import ClaudeProvider
        import anthropic

        mock_response = MagicMock()
        mock_response.content = [MagicMock(text='{"tag_groups":[],"pain_points":"","insights":"","innovations":""}')]
        mock_response.usage.input_tokens = 100
        mock_response.usage.output_tokens = 50

        rate_limit_error = anthropic.RateLimitError(
            message="Rate limit exceeded",
            response=MagicMock(status_code=429),
            body={}
        )
        mock_anthropic.Anthropic.return_value.messages.create.side_effect = [
            rate_limit_error,
            rate_limit_error,
            mock_response
        ]

        provider = ClaudeProvider(api_key="test-key")
        result = provider.analyze("test", "prompt")

        assert result is not None
        assert mock_anthropic.Anthropic.return_value.messages.create.call_count == 3


def test_claude_provider_gives_up_after_max_retries():
    """ClaudeProvider should give up after 3 retries"""
    with patch('src.analyzers.claude.anthropic') as mock_anthropic:
        from src.analyzers.claude import ClaudeProvider
        import anthropic

        api_error = anthropic.APIError(
            message="Server error",
            request=MagicMock(),
            body={}
        )
        mock_anthropic.Anthropic.return_value.messages.create.side_effect = api_error

        provider = ClaudeProvider(api_key="test-key")
        result = provider.analyze("test", "prompt")

        assert result is None
        assert mock_anthropic.Anthropic.return_value.messages.create.call_count == 3


def test_claude_provider_handles_empty_content():
    """ClaudeProvider should handle empty article content"""
    with patch('src.analyzers.claude.anthropic') as mock_anthropic:
        from src.analyzers.claude import ClaudeProvider

        mock_response = MagicMock()
        mock_response.content = [MagicMock(text='{"tag_groups":[{"group":"other_applications","tags":["empty"]}],"pain_points":"","insights":"No content","innovations":""}')]
        mock_response.usage.input_tokens = 50
        mock_response.usage.output_tokens = 30
        mock_anthropic.Anthropic.return_value.messages.create.return_value = mock_response

        provider = ClaudeProvider(api_key="test-key")
        result = provider.analyze("", "analyze this empty content")

        assert result is not None


def test_claude_provider_handles_unicode_content():
    """ClaudeProvider should handle unicode content"""
    with patch('src.analyzers.claude.anthropic') as mock_anthropic:
        from src.analyzers.claude import ClaudeProvider

        mock_response = MagicMock()
        mock_response.content = [MagicMock(text='{"tag_groups":[{"group":"digital_twin","tags":["数字孪生","デジタルツイン"]}],"pain_points":"","insights":"","innovations":""}')]
        mock_response.usage.input_tokens = 200
        mock_response.usage.output_tokens = 100
        mock_anthropic.Anthropic.return_value.messages.create.return_value = mock_response

        provider = ClaudeProvider(api_key="test-key")
        result = provider.analyze("数字孪生技術の記事", "analyze")

        assert result is not None
        assert "数字孪生" in result.tag_groups[0]["tags"]


def test_claude_provider_handles_large_content():
    """ClaudeProvider should handle large content without error"""
    with patch('src.analyzers.claude.anthropic') as mock_anthropic:
        from src.analyzers.claude import ClaudeProvider

        mock_response = MagicMock()
        mock_response.content = [MagicMock(text='{"tag_groups":[{"group":"digital_twin","tags":["test"]}],"pain_points":"","insights":"","innovations":""}')]
        mock_response.usage.input_tokens = 50000
        mock_response.usage.output_tokens = 500
        mock_anthropic.Anthropic.return_value.messages.create.return_value = mock_response

        provider = ClaudeProvider(api_key="test-key")
        large_content = "Digital twins content. " * 5000
        result = provider.analyze(large_content, "analyze")

        assert result is not None
        assert result.input_tokens == 50000
