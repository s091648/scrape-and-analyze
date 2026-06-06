"""Integration tests for shared.llm_provider.load_active_providers."""
import pytest
from models.llm_provider import LlmProvider

pytestmark = pytest.mark.integration


def _make_provider(db_session, **kwargs) -> LlmProvider:
    defaults = dict(
        name='gemini',
        model='gemini-test-model',
        api_key_env='GEMINI_API_KEY',
        priority=1,
        is_active=True,
        rpm=5,
        tpm=250000,
        rpd=20,
    )
    defaults.update(kwargs)
    p = LlmProvider(**defaults)
    db_session.add(p)
    db_session.flush()
    return p


def test_returns_only_active_providers(db_session):
    from shared.llm_provider import load_active_providers
    _make_provider(db_session, model='model-active', is_active=True, priority=1)
    _make_provider(db_session, model='model-inactive', is_active=False, priority=2)

    result = load_active_providers(db_session)

    models = [r['model'] for r in result]
    assert 'model-active' in models
    assert 'model-inactive' not in models


def test_returns_sorted_by_priority(db_session):
    from shared.llm_provider import load_active_providers
    _make_provider(db_session, model='model-p3', priority=3)
    _make_provider(db_session, model='model-p1', priority=1)
    _make_provider(db_session, model='model-p2', priority=2)

    result = load_active_providers(db_session)

    active = [r for r in result if r['model'] in ('model-p1', 'model-p2', 'model-p3')]
    priorities = [r['priority'] for r in active]
    assert priorities == sorted(priorities)


def test_sliding_window_strategy_when_all_rate_limits_set(db_session):
    from shared.llm_provider import load_active_providers
    _make_provider(db_session, model='model-sw', rpm=5, tpm=100000, rpd=50)

    result = load_active_providers(db_session)

    match = next(r for r in result if r['model'] == 'model-sw')
    assert match['strategy']['type'] == 'sliding_window'
    assert match['strategy']['rpm'] == 5
    assert match['strategy']['tpm'] == 100000
    assert match['strategy']['rpd'] == 50


def test_noop_strategy_when_any_rate_limit_is_null(db_session):
    from shared.llm_provider import load_active_providers
    _make_provider(db_session, model='model-noop', rpm=5, tpm=None, rpd=50)

    result = load_active_providers(db_session)

    match = next(r for r in result if r['model'] == 'model-noop')
    assert match['strategy']['type'] == 'noop'


def test_dict_contains_required_keys(db_session):
    from shared.llm_provider import load_active_providers
    _make_provider(db_session, model='model-keys')

    result = load_active_providers(db_session)

    match = next(r for r in result if r['model'] == 'model-keys')
    for key in ('name', 'model', 'api_key_env', 'priority', 'strategy'):
        assert key in match
