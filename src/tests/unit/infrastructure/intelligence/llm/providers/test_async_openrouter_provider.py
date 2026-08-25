import json
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest


def _mock_response(content: str, input_tokens=100, output_tokens=50, status_code=200):
    mock = MagicMock()
    mock.status_code = status_code
    mock.json.return_value = {
        'choices': [{'message': {'content': content}}],
        'usage': {'prompt_tokens': input_tokens, 'completion_tokens': output_tokens}
    }
    return mock


def _patch_async_client(post_side_effect=None, post_return_value=None):
    """Patch httpx.AsyncClient so `async with httpx.AsyncClient(...) as client`
    yields a client whose `.post()` is an AsyncMock configured as given."""
    client = AsyncMock()
    if post_side_effect is not None:
        client.post = AsyncMock(side_effect=post_side_effect)
    else:
        client.post = AsyncMock(return_value=post_return_value)

    ctx = MagicMock()
    ctx.__aenter__ = AsyncMock(return_value=client)
    ctx.__aexit__ = AsyncMock(return_value=False)

    return patch(
        'src.infrastructure.intelligence.llm.providers.async_openrouter_provider.httpx.AsyncClient',
        return_value=ctx,
    ), client


@pytest.mark.asyncio
async def test_async_openrouter_provider_analyze_returns_tuple():
    from src.infrastructure.intelligence.llm.providers.async_openrouter_provider import AsyncOpenRouterProvider
    payload = json.dumps({
        'tag_groups': [],
        'pain_points': 'p', 'insights': 'i', 'innovations': 'n', 'summary': 's'
    })
    patcher, _client = _patch_async_client(post_return_value=_mock_response(payload))
    with patcher:
        provider = AsyncOpenRouterProvider(api_key='test', model='deepseek/deepseek-chat')
        result = await provider.analyze('content', 'prompt')

    assert result is not None
    content, metadata = result
    assert content.pain_points == 'p'
    assert metadata.input_tokens == 100


@pytest.mark.asyncio
async def test_async_openrouter_provider_returns_none_on_http_error():
    from src.infrastructure.intelligence.llm.providers.async_openrouter_provider import AsyncOpenRouterProvider
    mock_resp = MagicMock()
    mock_resp.status_code = 429
    mock_resp.raise_for_status.side_effect = httpx.HTTPStatusError(
        "rate limited", request=MagicMock(), response=mock_resp
    )

    patcher, _client = _patch_async_client(post_return_value=mock_resp)
    with patcher:
        provider = AsyncOpenRouterProvider(api_key='test', model='deepseek/deepseek-chat')
        result = await provider.analyze('content', 'prompt')

    assert result is None


@pytest.mark.asyncio
async def test_async_openrouter_provider_returns_none_on_invalid_json():
    from src.infrastructure.intelligence.llm.providers.async_openrouter_provider import AsyncOpenRouterProvider
    patcher, _client = _patch_async_client(post_return_value=_mock_response('not valid json'))
    with patcher:
        provider = AsyncOpenRouterProvider(api_key='test', model='deepseek/deepseek-chat')
        result = await provider.analyze('content', 'prompt')

    assert result is None


@pytest.mark.asyncio
async def test_async_openrouter_provider_retries_on_transient_http_error():
    from src.infrastructure.intelligence.llm.providers.async_openrouter_provider import AsyncOpenRouterProvider

    payload = json.dumps({
        'tag_groups': [], 'pain_points': 'p', 'insights': 'i',
        'innovations': 'n', 'summary': 's'
    })
    error_resp = MagicMock()
    error_resp.status_code = 500
    error_resp.raise_for_status.side_effect = httpx.HTTPStatusError(
        "Server error 500", request=MagicMock(), response=error_resp
    )
    ok_resp = _mock_response(payload)

    patcher, _client = _patch_async_client(post_side_effect=[error_resp, ok_resp])
    with patcher:
        provider = AsyncOpenRouterProvider(api_key='test', model='deepseek/deepseek-chat')
        result = await provider.analyze('content', 'prompt')

    assert result is not None
