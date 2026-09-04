"""External data-source client adapters (OpenAlex, Semantic Scholar, RSS, arXiv).

Intentionally NOT a barrel: import the concrete submodule you need, e.g.
``from src.infrastructure.collection.clients.openalex_client import OpenAlexClient``.

Each submodule imports its own third-party client at module scope, and those
deps do not share a footprint — ``rss_client`` needs ``feedparser`` (``scraper``
uv group), whereas ``openalex_client`` / ``semantic_scholar_client`` need only
``requests`` (``http-clients``). Re-exporting them here would run every
submodule's imports whenever any one of them is imported (Python executes the
package ``__init__`` first), so the lean cron services — ``dedup-reconcile``
(``http-clients``) and ``refresh-metrics`` (``http-clients metrics``), which
construct only the ``requests``-only clients — would still pull ``feedparser``
and crash at startup with ``ModuleNotFoundError``.

Keep this file free of module-scope imports of the submodules. See
``src/tests/unit/infrastructure/collection/clients/test_client_import_isolation.py``.
"""
