import importlib
import os
from unittest.mock import patch


def _reload():
    import backend.config as m
    importlib.reload(m)
    return m


def test_database_url_reads_env():
    with patch.dict(os.environ, {"DATABASE_URL": "postgresql://test:test@localhost/db"}):
        m = _reload()
        assert m.DATABASE_URL == "postgresql://test:test@localhost/db"


def test_frontend_origin_has_default():
    with patch.dict(os.environ, {}, clear=False):
        os.environ.pop("FRONTEND_ORIGIN", None)
        m = _reload()
        assert m.FRONTEND_ORIGIN == "http://localhost:3000"


def test_view_count_flush_interval_is_int():
    with patch.dict(os.environ, {"VIEW_COUNT_FLUSH_INTERVAL": "300"}):
        m = _reload()
        assert m.VIEW_COUNT_FLUSH_INTERVAL == 300
        assert isinstance(m.VIEW_COUNT_FLUSH_INTERVAL, int)


def test_redis_url_default_matches_docker_compose_service_name():
    with patch.dict(os.environ, {}, clear=False):
        os.environ.pop("REDIS_URL", None)
        m = _reload()
        assert m.REDIS_URL == "redis://redis:6379/0"


def test_nextauth_secret_reads_env():
    with patch.dict(os.environ, {"NEXTAUTH_SECRET": "test-secret"}):
        m = _reload()
        assert m.NEXTAUTH_SECRET == "test-secret"


def test_chat_service_url_strips_trailing_slash():
    with patch.dict(os.environ, {"CHAT_SERVICE_URL": "https://chat.example.com/"}):
        m = _reload()
        assert m.CHAT_SERVICE_URL == "https://chat.example.com"


def test_grafana_vars_read_from_env():
    env = {
        "GRAFANA_PROMETHEUS_URL": "https://prom.example.com/",
        "GRAFANA_PROMETHEUS_USER": "prom-user",
        "GRAFANA_API_KEY": "api-key",
        "GRAFANA_LOKI_URL": "https://loki.example.com/",
        "GRAFANA_LOKI_USER": "loki-user",
        "GRAFANA_TEMPO_URL": "https://tempo.example.com/",
        "GRAFANA_TEMPO_USER": "tempo-user",
    }
    with patch.dict(os.environ, env):
        m = _reload()
        assert m.GRAFANA_PROMETHEUS_URL == "https://prom.example.com"
        assert m.GRAFANA_PROMETHEUS_USER == "prom-user"
        assert m.GRAFANA_API_KEY == "api-key"
        assert m.GRAFANA_LOKI_URL == "https://loki.example.com"
        assert m.GRAFANA_LOKI_USER == "loki-user"
        assert m.GRAFANA_TEMPO_URL == "https://tempo.example.com"
        assert m.GRAFANA_TEMPO_USER == "tempo-user"


def test_gemini_api_key_reads_env():
    with patch.dict(os.environ, {"GEMINI_API_KEY": "gemini-key"}):
        m = _reload()
        assert m.GEMINI_API_KEY == "gemini-key"


def test_swagger_try_it_out_enabled_defaults_to_false():
    with patch.dict(os.environ, {}, clear=False):
        os.environ.pop("SWAGGER_TRY_IT_OUT_ENABLED", None)
        m = _reload()
        assert m.SWAGGER_TRY_IT_OUT_ENABLED is False


def test_swagger_try_it_out_enabled_true_variants():
    for value in ("true", "True", "TRUE"):
        with patch.dict(os.environ, {"SWAGGER_TRY_IT_OUT_ENABLED": value}):
            m = _reload()
            assert m.SWAGGER_TRY_IT_OUT_ENABLED is True


def test_swagger_try_it_out_enabled_false_for_other_values():
    with patch.dict(os.environ, {"SWAGGER_TRY_IT_OUT_ENABLED": "no"}):
        m = _reload()
        assert m.SWAGGER_TRY_IT_OUT_ENABLED is False
