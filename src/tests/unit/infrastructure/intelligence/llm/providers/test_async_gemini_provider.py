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
