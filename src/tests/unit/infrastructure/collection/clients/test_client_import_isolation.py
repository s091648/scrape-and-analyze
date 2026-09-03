"""Guards the lean/heavy uv-dependency-group split for external-source clients.

Two Railway cron services build WITHOUT the ``scraper`` uv group:

    dedup-reconcile   UV_GROUP="http-clients"
    refresh-metrics   UV_GROUP="http-clients metrics"

Both construct only ``OpenAlexClient`` / ``SemanticScholarClient`` (``requests``
-only). If importing either of those transitively drags in a ``scraper``-group
package -- ``feedparser`` via ``rss_client`` is the one that has bitten us -- the
service dies at startup with ``ModuleNotFoundError`` even though every unit test
here (run in the full dev venv) would still pass.

These tests import in a *clean* child interpreter and assert on the resulting
``sys.modules``, so they catch the coupling regardless of what happens to be
installed locally. Regression test for the barrel-``__init__`` removal in the
same change, and the analogous ``pillow`` coupling in weekly-report's
``image_encoding`` (covered by ``test_pillow_is_explicit_llm_group_dependency``).
"""
import json
import pathlib
import subprocess
import sys
import tomllib

import pytest

_REPO_ROOT = pathlib.Path(__file__).resolve().parents[6]

# Packages that live ONLY in the `scraper` uv group (src/pyproject.toml). None of
# these may be reachable from a requests-only client.
_SCRAPER_GROUP_ONLY = frozenset({
    "feedparser", "bs4", "lxml", "fitz", "pymupdf", "fastembed", "dateutil",
})


def _top_level_modules_after_import(module: str) -> set[str]:
    """Import ``module`` in a fresh interpreter; return the set of top-level
    package names present in ``sys.modules`` afterwards."""
    code = (
        "import sys, json; "
        f"sys.path.insert(0, {str(_REPO_ROOT)!r}); "
        f"import {module}; "
        "print(json.dumps(sorted({k.split('.')[0] for k in sys.modules})))"
    )
    proc = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True, text=True, cwd=_REPO_ROOT,
    )
    assert proc.returncode == 0, f"import {module} failed:\n{proc.stderr}"
    return set(json.loads(proc.stdout.strip().splitlines()[-1]))


@pytest.mark.parametrize("module", [
    "src.infrastructure.collection.clients.openalex_client",
    "src.infrastructure.collection.clients.semantic_scholar_client",
])
def test_requests_only_client_does_not_pull_scraper_group(module):
    leaked = _top_level_modules_after_import(module) & _SCRAPER_GROUP_ONLY
    assert not leaked, (
        f"{module} transitively imported scraper-group-only package(s) {sorted(leaked)} "
        "-- this breaks the lean dedup-reconcile / refresh-metrics services, which "
        "build without the `scraper` uv group. Likely cause: an eager re-export was "
        "added back to src/infrastructure/collection/clients/__init__.py."
    )


def test_clients_package_init_is_import_side_effect_free():
    """Importing the package itself must not run any submodule's module-scope
    imports (keep ``__init__`` a docstring only)."""
    loaded = _top_level_modules_after_import("src.infrastructure.collection.clients")
    leaked = loaded & (_SCRAPER_GROUP_ONLY | {"requests"})
    assert not leaked, (
        f"importing the clients package alone pulled {sorted(leaked)} -- its "
        "__init__ re-exports submodules again; keep it minimal."
    )


def test_pillow_is_explicit_llm_group_dependency():
    """weekly-report (UV_GROUP="llm http-clients") needs PIL for
    ``image_encoding.encode_as_webp``. It must be a declared ``llm`` group dep,
    not merely transitively present via ``fastembed`` in the ``scraper`` group
    (which weekly-report does not install)."""
    with open(_REPO_ROOT / "pyproject.toml", "rb") as fh:
        pyproject = tomllib.load(fh)
    llm_deps = pyproject["dependency-groups"]["llm"]
    assert any(d.lower().replace("_", "-").startswith("pillow") for d in llm_deps), (
        f"pillow missing from the `llm` dependency group: {llm_deps}"
    )
