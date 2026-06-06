import pytest
from unittest.mock import patch, MagicMock
import json


def _mock_response(content: str, input_tokens=100, output_tokens=50):
    mock = MagicMock()
    mock.status_code = 200
    mock.json.return_value = {
        'choices': [{'message': {'content': content}}],
        'usage': {'prompt_tokens': input_tokens, 'completion_tokens': output_tokens}
    }
    return mock


def test_openrouter_provider_analyze_returns_tuple():
    from src.infrastructure.intelligence.llm.providers.openrouter_provider import OpenRouterProvider
    payload = json.dumps({
        'tag_groups': [],
        'pain_points': 'p', 'insights': 'i', 'innovations': 'n', 'summary': 's'
    })
    with patch('src.infrastructure.intelligence.llm.providers.openrouter_provider.requests.post',
               return_value=_mock_response(payload)):
        provider = OpenRouterProvider(api_key='test', model='deepseek/deepseek-chat')
        result = provider.analyze('content', 'prompt')

    assert result is not None
    content, metadata = result
    assert content.pain_points == 'p'
    assert metadata.input_tokens == 100


def test_openrouter_provider_returns_none_on_http_error():
    from src.infrastructure.intelligence.llm.providers.openrouter_provider import OpenRouterProvider
    mock_resp = MagicMock()
    mock_resp.status_code = 429
    mock_resp.raise_for_status.side_effect = Exception("rate limited")

    with patch('src.infrastructure.intelligence.llm.providers.openrouter_provider.requests.post',
               return_value=mock_resp):
        provider = OpenRouterProvider(api_key='test', model='deepseek/deepseek-chat')
        result = provider.analyze('content', 'prompt')

    assert result is None


def test_openrouter_provider_returns_none_on_invalid_json():
    from src.infrastructure.intelligence.llm.providers.openrouter_provider import OpenRouterProvider
    with patch('src.infrastructure.intelligence.llm.providers.openrouter_provider.requests.post',
               return_value=_mock_response('not valid json')):
        provider = OpenRouterProvider(api_key='test', model='deepseek/deepseek-chat')
        result = provider.analyze('content', 'prompt')

    assert result is None


# ── T016: Retry on transient HTTP error ───────────────────────────────────────

def test_openrouter_provider_retries_on_transient_http_error():
    import requests as req_lib
    from src.infrastructure.intelligence.llm.providers.openrouter_provider import OpenRouterProvider

    payload = json.dumps({
        'tag_groups': [], 'pain_points': 'p', 'insights': 'i',
        'innovations': 'n', 'summary': 's'
    })
    error_resp = MagicMock()
    error_resp.status_code = 500
    error_resp.raise_for_status.side_effect = req_lib.HTTPError("Server error 500")

    with patch('src.infrastructure.intelligence.llm.providers.openrouter_provider.requests.post',
               side_effect=[error_resp, _mock_response(payload)]):
        provider = OpenRouterProvider(api_key='test', model='deepseek/deepseek-chat')
        result = provider.analyze('content', 'prompt')

    assert result is not None