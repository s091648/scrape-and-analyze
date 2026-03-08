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


def test_openrouter_provider_analyze_returns_result():
    from src.analyzers.openrouter import OpenRouterProvider
    payload = json.dumps({
        'tag_groups': [{'group': 'test', 'tags': ['a']}],
        'pain_points': 'p', 'insights': 'i', 'innovations': 'n'
    })
    with patch('src.analyzers.openrouter.requests.post',
               return_value=_mock_response(payload)):
        provider = OpenRouterProvider(api_key='test', model='deepseek/deepseek-chat')
        result = provider.analyze('content', 'prompt')

    assert result is not None
    assert result.pain_points == 'p'
    assert result.input_tokens == 100


def test_openrouter_provider_returns_none_on_http_error():
    from src.analyzers.openrouter import OpenRouterProvider
    mock_resp = MagicMock()
    mock_resp.status_code = 429
    mock_resp.raise_for_status.side_effect = Exception("rate limited")

    with patch('src.analyzers.openrouter.requests.post', return_value=mock_resp):
        provider = OpenRouterProvider(api_key='test', model='deepseek/deepseek-chat')
        result = provider.analyze('content', 'prompt')

    assert result is None


def test_openrouter_provider_returns_none_on_invalid_json():
    from src.analyzers.openrouter import OpenRouterProvider
    with patch('src.analyzers.openrouter.requests.post',
               return_value=_mock_response('not valid json')):
        provider = OpenRouterProvider(api_key='test', model='deepseek/deepseek-chat')
        result = provider.analyze('content', 'prompt')

    assert result is None
