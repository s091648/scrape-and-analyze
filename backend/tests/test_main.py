import importlib

import pytest


@pytest.fixture
def app_with_swagger_toggle(monkeypatch):
    """Reload backend.config then backend.main after setting SWAGGER_TRY_IT_OUT_ENABLED, same
    reload-order rationale as test_cors.py's app_with_frontend_origin fixture."""
    def _set(value: str | None):
        if value is None:
            monkeypatch.delenv("SWAGGER_TRY_IT_OUT_ENABLED", raising=False)
        else:
            monkeypatch.setenv("SWAGGER_TRY_IT_OUT_ENABLED", value)
        import backend.config as config
        importlib.reload(config)
        import backend.main as main
        importlib.reload(main)
        return main.app

    yield _set

    monkeypatch.undo()
    import backend.config as config
    importlib.reload(config)
    import backend.main as main
    importlib.reload(main)


def test_swagger_try_it_out_disabled_by_default(app_with_swagger_toggle):
    app = app_with_swagger_toggle(None)
    assert app.swagger_ui_parameters == {"supportedSubmitMethods": []}


def test_swagger_try_it_out_enabled_restores_full_interactivity(app_with_swagger_toggle):
    app = app_with_swagger_toggle("true")
    assert app.swagger_ui_parameters is None
