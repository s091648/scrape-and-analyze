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
    """The SDK raises a typed ClientError (google.genai.errors) on 4xx, not a
    bare Exception — code=429 + status="RESOURCE_EXHAUSTED" + a quota-id
    naming "PerDay" is what a real daily-quota 429 looks like."""
    from google.genai.errors import ClientError
    from src.infrastructure.intelligence.llm.rate_limit import RateLimitExhausted

    with patch("src.infrastructure.intelligence.llm.providers.gemini_provider.genai") as mock_genai:
        from src.infrastructure.intelligence.llm.providers.gemini_provider import GeminiProvider
        quota_error = ClientError(
            code=429,
            response_json={
                "status": "RESOURCE_EXHAUSTED",
                "message": "Quota exceeded",
                "details": [{"quotaId": "GenerateRequestsPerDayPerProjectPerModel-FreeTier"}],
            },
        )
        mock_genai.Client.return_value.models.generate_content.side_effect = quota_error
        provider = GeminiProvider(api_key="test-key", model="gemini-3-flash-preview")

        import pytest
        with pytest.raises(RateLimitExhausted):
            provider.analyze("content", "prompt")


def test_gemini_provider_retries_when_retry_info_delay_is_short_despite_perday_quota_id():
    """Regression test for a real 429 observed against the live API
    (scripts/verify_gemini_rate_limit_classification.py, 2026-08-12): quotaId
    said "...PerDay..." but the response also carried a
    google.rpc.RetryInfo.retryDelay of "26s" — the quota is a rolling/leaky
    bucket that clears in seconds, not a hard midnight reset. RetryInfo must
    win over the quota-id label, so this should retry, not abort."""
    from google.genai.errors import ClientError

    with patch("src.infrastructure.intelligence.llm.providers.gemini_provider.genai") as mock_genai:
        from src.infrastructure.intelligence.llm.providers.gemini_provider import GeminiProvider
        real_world_error = ClientError(
            code=429,
            response_json={
                "error": {
                    "code": 429,
                    "message": (
                        "You exceeded your current quota... "
                        "Please retry in 26.996214407s."
                    ),
                    "status": "RESOURCE_EXHAUSTED",
                    "details": [
                        {
                            "@type": "type.googleapis.com/google.rpc.QuotaFailure",
                            "violations": [{
                                "quotaMetric": "generativelanguage.googleapis.com/generate_content_free_tier_requests",
                                "quotaId": "GenerateRequestsPerDayPerProjectPerModel-FreeTier",
                                "quotaValue": "20",
                            }],
                        },
                        {
                            "@type": "type.googleapis.com/google.rpc.RetryInfo",
                            "retryDelay": "26s",
                        },
                    ],
                },
            },
        )
        ok_response = _make_mock_response(_make_valid_payload())
        mock_genai.Client.return_value.models.generate_content.side_effect = [real_world_error, ok_response]
        provider = GeminiProvider(api_key="test-key", model="gemini-3-flash-preview")
        result = provider.analyze("content", "prompt")

    assert result is not None
    assert mock_genai.Client.return_value.models.generate_content.call_count == 2


def test_gemini_provider_retries_on_rpm_quota_error():
    """A RESOURCE_EXHAUSTED 429 whose quota-id has no PerDay/Token marker (a
    plain per-minute request quota) should retry, not abort immediately."""
    from google.genai.errors import ClientError

    with patch("src.infrastructure.intelligence.llm.providers.gemini_provider.genai") as mock_genai:
        from src.infrastructure.intelligence.llm.providers.gemini_provider import GeminiProvider
        rpm_error = ClientError(
            code=429,
            response_json={
                "status": "RESOURCE_EXHAUSTED",
                "message": "Quota exceeded",
                "details": [{"quotaId": "GenerateRequestsPerMinutePerProjectPerModel-FreeTier"}],
            },
        )
        ok_response = _make_mock_response(_make_valid_payload())
        mock_genai.Client.return_value.models.generate_content.side_effect = [rpm_error, ok_response]
        provider = GeminiProvider(api_key="test-key", model="gemini-3-flash-preview")
        result = provider.analyze("content", "prompt")

    assert result is not None
    assert mock_genai.Client.return_value.models.generate_content.call_count == 2


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
