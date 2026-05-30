"""
Unit tests for GeminiProvider — covers happy path, markdown stripping,
daily quota detection, token tracking, JSON validation, and retry.
"""
import json
from unittest.mock import MagicMock, patch


def _make_valid_payload(**overrides):
    base = {
        "tag_groups": [],
        "pain_points": "none",
        "insights": "test insight",
        "innovations": "new thing",
        "summary": "short summary",
    }
    base.update(overrides)
    return base


def _make_mock_response(payload: dict, input_tokens: int = 100, output_tokens: int = 50):
    response = MagicMock()
    response.text = json.dumps(payload)
    usage = MagicMock()
    usage.prompt_token_count = input_tokens
    usage.candidates_token_count = output_tokens
    response.usage_metadata = usage
    return response


def _make_provider():
    with patch("src.infrastructure.intelligence.llm.providers.gemini_provider.genai"):
        from src.infrastructure.intelligence.llm.providers.gemini_provider import GeminiProvider
        provider = GeminiProvider(api_key="test-key", model="gemini-3-flash-preview")
        return provider


# ── Happy path ────────────────────────────────────────────────────────────────

def test_gemini_provider_calls_api_and_returns_analysis_tuple():
    with patch("src.infrastructure.intelligence.llm.providers.gemini_provider.genai") as mock_genai:
        from src.infrastructure.intelligence.llm.providers.gemini_provider import GeminiProvider
        mock_genai.Client.return_value.models.generate_content.return_value = (
            _make_mock_response(_make_valid_payload())
        )
        provider = GeminiProvider(api_key="test-key", model="gemini-3-flash-preview")
        result = provider.analyze("article content", "analyze this")

    assert result is not None
    content, metadata = result
    assert content.summary == "short summary"
    assert metadata.model_used == "gemini-3-flash-preview"


# ── Markdown stripping ────────────────────────────────────────────────────────

def test_gemini_provider_strips_markdown_code_block_before_parsing():
    payload = _make_valid_payload(summary="stripped correctly")
    wrapped = f"```json\n{json.dumps(payload)}\n```"

    with patch("src.infrastructure.intelligence.llm.providers.gemini_provider.genai") as mock_genai:
        from src.infrastructure.intelligence.llm.providers.gemini_provider import GeminiProvider
        mock_response = _make_mock_response(payload)
        mock_response.text = wrapped
        mock_genai.Client.return_value.models.generate_content.return_value = mock_response
        provider = GeminiProvider(api_key="test-key", model="gemini-3-flash-preview")
        result = provider.analyze("content", "prompt")

    assert result is not None
    content, _ = result
    assert content.summary == "stripped correctly"


# ── Daily quota detection ─────────────────────────────────────────────────────

def test_gemini_provider_detects_daily_quota_exhaustion_and_raises():
    from src.infrastructure.intelligence.llm.rate_limit import RateLimitExhausted

    with patch("src.infrastructure.intelligence.llm.providers.gemini_provider.genai") as mock_genai:
        from src.infrastructure.intelligence.llm.providers.gemini_provider import GeminiProvider
        mock_genai.Client.return_value.models.generate_content.side_effect = Exception(
            "RESOURCE_EXHAUSTED: PerDay quota exceeded"
        )
        provider = GeminiProvider(api_key="test-key", model="gemini-3-flash-preview")

        import pytest
        with pytest.raises(RateLimitExhausted):
            provider.analyze("content", "prompt")


# ── Token tracking ────────────────────────────────────────────────────────────

def test_gemini_provider_tracks_input_and_output_tokens():
    with patch("src.infrastructure.intelligence.llm.providers.gemini_provider.genai") as mock_genai:
        from src.infrastructure.intelligence.llm.providers.gemini_provider import GeminiProvider
        mock_genai.Client.return_value.models.generate_content.return_value = (
            _make_mock_response(_make_valid_payload(), input_tokens=800, output_tokens=300)
        )
        provider = GeminiProvider(api_key="test-key", model="gemini-3-flash-preview")
        result = provider.analyze("content", "prompt")

    assert result is not None
    _, metadata = result
    assert metadata.input_tokens == 800
    assert metadata.output_tokens == 300


# ── Invalid JSON ──────────────────────────────────────────────────────────────

def test_gemini_provider_returns_none_on_invalid_json():
    with patch("src.infrastructure.intelligence.llm.providers.gemini_provider.genai") as mock_genai:
        from src.infrastructure.intelligence.llm.providers.gemini_provider import GeminiProvider
        mock_response = MagicMock()
        mock_response.text = "this is not json at all"
        mock_response.usage_metadata = None
        mock_genai.Client.return_value.models.generate_content.return_value = mock_response
        provider = GeminiProvider(api_key="test-key", model="gemini-3-flash-preview")
        result = provider.analyze("content", "prompt")

    assert result is None


# ── Missing required fields ───────────────────────────────────────────────────

def test_gemini_provider_returns_none_on_missing_required_fields():
    incomplete = {"tag_groups": [], "summary": "ok"}  # missing pain_points, insights, innovations

    with patch("src.infrastructure.intelligence.llm.providers.gemini_provider.genai") as mock_genai:
        from src.infrastructure.intelligence.llm.providers.gemini_provider import GeminiProvider
        mock_genai.Client.return_value.models.generate_content.return_value = (
            _make_mock_response(incomplete)
        )
        provider = GeminiProvider(api_key="test-key", model="gemini-3-flash-preview")
        result = provider.analyze("content", "prompt")

    assert result is None


# ── Retry on transient error ──────────────────────────────────────────────────

def test_gemini_provider_retries_on_transient_api_error():
    with patch("src.infrastructure.intelligence.llm.providers.gemini_provider.genai") as mock_genai:
        from src.infrastructure.intelligence.llm.providers.gemini_provider import GeminiProvider
        ok_response = _make_mock_response(_make_valid_payload())
        mock_genai.Client.return_value.models.generate_content.side_effect = [
            Exception("transient network error"),
            ok_response,
        ]
        provider = GeminiProvider(api_key="test-key", model="gemini-3-flash-preview")
        result = provider.analyze("content", "prompt")

    assert result is not None
    assert mock_genai.Client.return_value.models.generate_content.call_count == 2
