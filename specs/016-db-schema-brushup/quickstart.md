# Quickstart: Database Schema Brush-Up & Auto-Generated Schema Diagram

Manual verification steps for this feature once implemented. Assumes `docker compose up` is already running (postgres, backend, frontend) per the project's normal local dev flow.

## 1. Verify the schema migration (User Story 1)

```bash
make migrate
```

Then connect to the local postgres (`docker compose exec postgres psql -U <user> -d <db>`, or via pgAdmin at `localhost:80`) and run:

```sql
SELECT table_schema, table_name
FROM information_schema.tables
WHERE table_schema IN ('core', 'collection', 'intelligence', 'ai_infra', 'user_prefs')
ORDER BY table_schema, table_name;
```

- **Expect**: 24 rows total, distributed 3/5/10/3/3 across `core`/`collection`/`intelligence`/`ai_infra`/`user_prefs` (see data-model.md §2 for the exact per-table mapping).
- Then confirm nothing unexpected remains in `public`:

```sql
SELECT table_name FROM information_schema.tables WHERE table_schema = 'public';
```

- **Expect**: only `data_migrations` and Alembic's own `alembic_version` (plus Postgres extension bookkeeping tables like `pg_stat_statements`, unrelated to this app) — no `articles`, `tags`, etc.

Run the existing test suites unmodified and confirm they still pass (proves SC-002 — zero behavior change):

```bash
make test
make test-integration
```

Verify reversibility:

```bash
make migrate-down
# re-run the information_schema.tables query above — all 24 tables should be back in public,
# and the 5 new schemas should no longer exist.
make migrate   # re-apply before continuing
```

## 2. Verify `models/arxiv_keyword.py` is gone

```bash
git status models/arxiv_keyword.py   # should report "deleted"
grep -rn "arxiv_keyword" models/__init__.py   # should have no matches (exclusion comment removed too)
```

## 3. Verify the diagram generator (User Story 2)

```bash
make uml-db-schema   # matches the existing `make uml-backend` convention (see Makefile)
```

- **Expect**: exits 0, writes `site/public/guide/architecture/db-schema.dot`.
- The script has zero external dependencies (stdlib `ast` only), so `python scripts/generate_db_schema.py` also works directly on the host without `uv sync` — `make uml-db-schema` just runs it inside `job_service` with the `site/` volume mounted, for parity with `make uml-backend`.
- Deliberately break a model (e.g. temporarily add a `ForeignKey("nonexistent_table.id")` with a malformed schema-qualified string) and re-run — **expect** the script to fail loudly (non-zero exit), not silently omit the table (FR-010).

Then build the docs site and check the page renders:

```bash
cd site
npm run generate
cp -r ../specs site/specs   # matches the CI workflow's "Sync spec content into site/" step
npm run build
npm run preview   # or: npx vitepress dev
```

Navigate to **Architecture → DB Schema** in the nav — the diagram renders client-side via `@viz-js/viz` (same pattern as the existing Pipeline/UML page's `viewer.html`), fetching `./db-schema.dot`.

- Navigate to the new "DB Schema" page (wherever it's wired into nav — see `site/.vitepress/config.js`) and confirm: all 24 + `auth.users` + `vectors.*` tables appear, grouped/labeled by schema, with cross-schema FK edges visually distinguished from same-schema ones.
- Confirm `npm run build` (the **production** build, stricter than `dev`) succeeds — this is the check that would catch a "VitePress-compatible Markdown" violation (constitution VII) from an unescaped `<...>` in any column-type text like `Vector(768)` rendered onto the page.

## 4. Verify the CI workflow wiring

Trigger `speckit-github-pages.yml` (`workflow_dispatch` from the Actions tab, or push a `v*` tag on a throwaway branch if testing pre-merge) and confirm the new diagram-generation step runs after "Generate backend UML (pyreverse)" and before "Sync spec content into site/", with the produced page present in the uploaded Pages artifact.

## 5. Verify `backend/config.py` (User Story 3)

```bash
grep -rn "os\.environ\|os\.getenv" backend/ --include="*.py" | grep -v backend/tests | grep -v backend/config.py
```

- **Expect**: no output — every remaining production read goes through `backend/config.py`.

```bash
docker compose run --rm test_service pytest backend/tests/
```

- **Expect**: full pass, no behavior change (test files that set `os.environ[...]` directly as fixtures are untouched and still work, since `config.py` reads live `os.environ` at import time same as the code it replaces).

Confirm no env var regressions: diff the set of vars `backend/config.py` reads against `.env.example` (data-model.md §4) — every var must already be documented there.
