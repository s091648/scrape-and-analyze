"""Unit tests for AsyncGeminiProvider — mirrors test_gemini_provider.py's
coverage, adapted for the async .aio call path."""
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


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


def _patch_genai():
    return patch("src.infrastructure.intelligence.llm.providers.async_gemini_provider.genai")


def test_async_gemini_provider_inherits_from_async_base_provider():
    from src.infrastructure.intelligence.llm.providers.async_gemini_provider import AsyncGeminiProvider
    from src.infrastructure.intelligence.llm.providers.async_base_provider import AsyncBaseProvider
    assert issubclass(AsyncGeminiProvider, AsyncBaseProvider)


@pytest.mark.asyncio
async def test_async_gemini_provider_calls_api_and_returns_analysis_tuple():
    with _patch_genai() as mock_genai:
        from src.infrastructure.intelligence.llm.providers.async_gemini_provider import AsyncGeminiProvider
        mock_genai.Client.return_value.aio.models.generate_content = AsyncMock(
            return_value=_make_mock_response(_make_valid_payload())
        )
        provider = AsyncGeminiProvider(api_key="test-key", model="gemini-3-flash-preview")
        result = await provider.analyze("article content", "analyze this")

    assert result is not None
    content, metadata = result
    assert metadata.input_tokens == 100
    assert metadata.output_tokens == 50


@pytest.mark.asyncio
async def test_async_gemini_provider_strips_markdown_fences():
    with _patch_genai() as mock_genai:
        from src.infrastructure.intelligence.llm.providers.async_gemini_provider import AsyncGeminiProvider
        response = MagicMock()
        response.text = "```json\n" + json.dumps(_make_valid_payload()) + "\n```"
        usage = MagicMock(prompt_token_count=10, candidates_token_count=5)
        response.usage_metadata = usage
        mock_genai.Client.return_value.aio.models.generate_content = AsyncMock(return_value=response)

        provider = AsyncGeminiProvider(api_key="test-key", model="gemini-3-flash-preview")
        result = await provider.analyze("content", "prompt")

    assert result is not None


@pytest.mark.asyncio
async def test_async_gemini_provider_returns_none_on_invalid_json():
    with _patch_genai() as mock_genai:
        from src.infrastructure.intelligence.llm.providers.async_gemini_provider import AsyncGeminiProvider
        response = MagicMock()
        response.text = "not valid json"
        response.usage_metadata = MagicMock(prompt_token_count=1, candidates_token_count=1)
        mock_genai.Client.return_value.aio.models.generate_content = AsyncMock(return_value=response)

        provider = AsyncGeminiProvider(api_key="test-key", model="gemini-3-flash-preview")
        result = await provider.analyze("content", "prompt")

    assert result is None


@pytest.mark.asyncio
async def test_async_gemini_provider_translate():
    with _patch_genai() as mock_genai:
        from src.infrastructure.intelligence.llm.providers.async_gemini_provider import AsyncGeminiProvider
        response = MagicMock()
        response.candidates = [MagicMock(finish_reason=MagicMock(name="STOP"))]
        response.candidates[0].finish_reason.name = "STOP"
        response.text = "translated text"
        mock_genai.Client.return_value.aio.models.generate_content = AsyncMock(return_value=response)

        provider = AsyncGeminiProvider(api_key="test-key", model="gemini-3-flash-preview")
        result = await provider.translate("content", "translate this")

    assert result == "translated text"


@pytest.mark.asyncio
async def test_async_gemini_provider_returns_none_when_no_candidates():
    with _patch_genai() as mock_genai:
        from src.infrastructure.intelligence.llm.providers.async_gemini_provider import AsyncGeminiProvider
        response = MagicMock()
        response.candidates = []
        mock_genai.Client.return_value.aio.models.generate_content = AsyncMock(return_value=response)

        provider = AsyncGeminiProvider(api_key="test-key", model="gemini-3-flash-preview")
        result = await provider.translate("content", "translate this")

    assert result is None


@pytest.mark.asyncio
async def test_async_gemini_provider_returns_none_when_blocked():
    with _patch_genai() as mock_genai:
        from src.infrastructure.intelligence.llm.providers.async_gemini_provider import AsyncGeminiProvider
        response = MagicMock()
        response.candidates = [MagicMock(finish_reason=MagicMock(name="SAFETY"))]
        response.candidates[0].finish_reason.name = "SAFETY"
        response.text = "should be ignored"
        mock_genai.Client.return_value.aio.models.generate_content = AsyncMock(return_value=response)

        provider = AsyncGeminiProvider(api_key="test-key", model="gemini-3-flash-preview")
        result = await provider.translate("content", "translate this")

    assert result is None


# ── _classify_rate_limit branch coverage ───────────────────────────────────────
# Mirrors test_gemini_provider.py's regression tests for the same logic,
# duplicated for the async sibling per async_base_provider.py's docstring.

def _make_client_error(details: dict, response=None):
    from google.genai.errors import ClientError
    return ClientError(code=429, response_json=details, response=response)


@pytest.mark.asyncio
async def test_async_gemini_provider_detects_daily_quota_exhaustion_and_raises():
    from src.infrastructure.intelligence.llm.rate_limit import RateLimitExhausted

    with _patch_genai() as mock_genai:
        from src.infrastructure.intelligence.llm.providers.async_gemini_provider import AsyncGeminiProvider
        quota_error = _make_client_error({
            "status": "RESOURCE_EXHAUSTED",
            "message": "Quota exceeded",
            "details": [{"quotaId": "GenerateRequestsPerDayPerProjectPerModel-FreeTier"}],
        })
        mock_genai.Client.return_value.aio.models.generate_content = AsyncMock(side_effect=quota_error)
        provider = AsyncGeminiProvider(api_key="test-key", model="gemini-3-flash-preview")

        with pytest.raises(RateLimitExhausted):
            await provider.analyze("content", "prompt")


@pytest.mark.asyncio
async def test_async_gemini_provider_short_retry_delay_overrides_perday_quota_id():
    """RetryInfo.retryDelay wins over a "PerDay"-labelled quota id when the
    delay itself is short — the quota clears in seconds, not at midnight."""
    with _patch_genai() as mock_genai:
        from src.infrastructure.intelligence.llm.providers.async_gemini_provider import AsyncGeminiProvider
        real_world_error = _make_client_error({
            "error": {
                "code": 429,
                "message": "You exceeded your current quota... Please retry in 26.99s.",
                "status": "RESOURCE_EXHAUSTED",
                "details": [
                    {
                        "@type": "type.googleapis.com/google.rpc.QuotaFailure",
                        "violations": [{
                            "quotaId": "GenerateRequestsPerDayPerProjectPerModel-FreeTier",
                        }],
                    },
                    {
                        "@type": "type.googleapis.com/google.rpc.RetryInfo",
                        "retryDelay": "26s",
                    },
                ],
            },
        })
        ok_response = _make_mock_response(_make_valid_payload())
        mock_genai.Client.return_value.aio.models.generate_content = AsyncMock(
            side_effect=[real_world_error, ok_response]
        )
        provider = AsyncGeminiProvider(api_key="test-key", model="gemini-3-flash-preview")
        result = await provider.analyze("content", "prompt")

    assert result is not None
    assert mock_genai.Client.return_value.aio.models.generate_content.await_count == 2


@pytest.mark.asyncio
async def test_async_gemini_provider_long_retry_delay_classified_as_rpd():
    """A RetryInfo delay longer than the short-wait threshold means "come back
    much later" — treated as RPD (abort) regardless of the quota id."""
    from src.infrastructure.intelligence.llm.rate_limit import RateLimitExhausted

    with _patch_genai() as mock_genai:
        from src.infrastructure.intelligence.llm.providers.async_gemini_provider import AsyncGeminiProvider
        long_delay_error = _make_client_error({
            "error": {
                "status": "RESOURCE_EXHAUSTED",
                "message": "Quota exceeded",
                "details": [
                    {
                        "@type": "type.googleapis.com/google.rpc.RetryInfo",
                        "retryDelay": "120s",
                    },
                ],
            },
        })
        mock_genai.Client.return_value.aio.models.generate_content = AsyncMock(side_effect=long_delay_error)
        provider = AsyncGeminiProvider(api_key="test-key", model="gemini-3-flash-preview")

        with pytest.raises(RateLimitExhausted):
            await provider.analyze("content", "prompt")


@pytest.mark.asyncio
async def test_async_gemini_provider_retries_on_rpm_quota_error():
    with _patch_genai() as mock_genai:
        from src.infrastructure.intelligence.llm.providers.async_gemini_provider import AsyncGeminiProvider
        rpm_error = _make_client_error({
            "status": "RESOURCE_EXHAUSTED",
            "message": "Quota exceeded",
            "details": [{"quotaId": "GenerateRequestsPerMinutePerProjectPerModel-FreeTier"}],
        })
        ok_response = _make_mock_response(_make_valid_payload())
        mock_genai.Client.return_value.aio.models.generate_content = AsyncMock(
            side_effect=[rpm_error, ok_response]
        )
        provider = AsyncGeminiProvider(api_key="test-key", model="gemini-3-flash-preview")
        result = await provider.analyze("content", "prompt")

    assert result is not None
    assert mock_genai.Client.return_value.aio.models.generate_content.await_count == 2


@pytest.mark.asyncio
async def test_async_gemini_provider_token_quota_classified_as_tpm():
    with _patch_genai() as mock_genai:
        from src.infrastructure.intelligence.llm.providers.async_gemini_provider import AsyncGeminiProvider
        tpm_error = _make_client_error({
            "status": "RESOURCE_EXHAUSTED",
            "message": "Quota exceeded",
            "details": [{"quotaId": "GenerateTokensPerMinutePerProjectPerModel-FreeTier"}],
        })
        ok_response = _make_mock_response(_make_valid_payload())
        mock_genai.Client.return_value.aio.models.generate_content = AsyncMock(
            side_effect=[tpm_error, ok_response]
        )
        provider = AsyncGeminiProvider(api_key="test-key", model="gemini-3-flash-preview")
        result = await provider.analyze("content", "prompt")

    assert result is not None
    assert mock_genai.Client.return_value.aio.models.generate_content.await_count == 2


@pytest.mark.asyncio
async def test_async_gemini_provider_non_resource_exhausted_status_returns_none_and_retries():
    with _patch_genai() as mock_genai:
        from src.infrastructure.intelligence.llm.providers.async_gemini_provider import AsyncGeminiProvider
        other_error = _make_client_error({
            "status": "INVALID_ARGUMENT",
            "message": "Bad request",
        })
        ok_response = _make_mock_response(_make_valid_payload())
        mock_genai.Client.return_value.aio.models.generate_content = AsyncMock(
            side_effect=[other_error, ok_response]
        )
        provider = AsyncGeminiProvider(api_key="test-key", model="gemini-3-flash-preview")
        result = await provider.analyze("content", "prompt")

    assert result is not None
    assert mock_genai.Client.return_value.aio.models.generate_content.await_count == 2


@pytest.mark.asyncio
async def test_async_gemini_provider_uses_retry_after_header_when_no_retry_info():
    with _patch_genai() as mock_genai:
        from src.infrastructure.intelligence.llm.providers.async_gemini_provider import AsyncGeminiProvider
        mock_response = MagicMock()
        mock_response.headers = {"retry-after": "45"}
        header_error = _make_client_error(
            {"status": "RESOURCE_EXHAUSTED", "message": "Quota exceeded", "details": []},
            response=mock_response,
        )
        ok_response = _make_mock_response(_make_valid_payload())
        mock_genai.Client.return_value.aio.models.generate_content = AsyncMock(
            side_effect=[header_error, ok_response]
        )
        provider = AsyncGeminiProvider(api_key="test-key", model="gemini-3-flash-preview")
        result = await provider.analyze("content", "prompt")

    assert result is not None
    assert mock_genai.Client.return_value.aio.models.generate_content.await_count == 2


@pytest.mark.asyncio
async def test_async_gemini_provider_malformed_retry_after_header_falls_back_to_quota_id():
    """A non-numeric retry-after header must not crash — classification falls
    back to the quota-id heuristic (here: PerDay -> RPD -> immediate abort)."""
    from src.infrastructure.intelligence.llm.rate_limit import RateLimitExhausted

    with _patch_genai() as mock_genai:
        from src.infrastructure.intelligence.llm.providers.async_gemini_provider import AsyncGeminiProvider
        mock_response = MagicMock()
        mock_response.headers = {"retry-after": "not-a-number"}
        header_error = _make_client_error(
            {
                "status": "RESOURCE_EXHAUSTED",
                "message": "Quota exceeded",
                "details": [{"quotaId": "GenerateRequestsPerDayPerProjectPerModel-FreeTier"}],
            },
            response=mock_response,
        )
        mock_genai.Client.return_value.aio.models.generate_content = AsyncMock(side_effect=header_error)
        provider = AsyncGeminiProvider(api_key="test-key", model="gemini-3-flash-preview")

        with pytest.raises(RateLimitExhausted):
            await provider.analyze("content", "prompt")
