# Contributing to Scrape & Analyze

Thanks for considering a contribution! This is a solo-maintained side project
(see the [README](../README.md) for what it does), so there's no formal
governance — just the conventions below, mostly so PRs are easy to review and
CI stays green. Response times are best-effort.

## Before you start

- **Small fix / obvious bug?** Open a PR directly.
- **New feature or a change to an existing flow?** Please open an issue first
  (there are [bug report](./ISSUE_TEMPLATE/bug-report.yml) and
  [feature request](./ISSUE_TEMPLATE/feature_request.yml) templates) so we can
  agree on the approach before you put time into it — this is a fairly
  opinionated Clean-Architecture/DDD codebase (see `CLAUDE.md`) and some
  changes have non-obvious ripple effects across `src/`, `backend/`, and
  `models/`.
- **Security issue?** Do not open a public issue — see
  [SECURITY.md](./SECURITY.md).

## Project layout

Three services share one PostgreSQL database:

| Directory | Role |
|---|---|
| `src/` | Scraper/analyzer (DDD: `domain/` → `application/` → infra), scheduled scraping + LLM analysis |
| `backend/` | FastAPI REST API serving the frontend |
| `frontend/` | Next.js 16 + React 19 web UI |
| `models/` | Shared SQLAlchemy ORM models used by both `src/` and `backend/` |
| `shared/` | Cross-service Python package (enums, LLM/metric-provider loaders, GeoIP, search tokenizer) |
| `infra/terraform/github/` + `.railway/` | IaC for GitHub Actions config + Railway deploy config |

**Read [`CLAUDE.md`](../CLAUDE.md) first** — it's the single source of truth
for architecture, conventions, and every `make`/`npm` command in this repo,
and is kept up to date as the project evolves. This file only covers the
contribution workflow itself.

## Local development

Everything runs in Docker — there's no supported bare-metal setup.

```bash
# Start all services (postgres, redis, pgadmin, backend, frontend, fastembed, chatbot_plugin)
docker compose up

# Run database migrations
make migrate
```

## Making changes

1. **Branch off `master`** (the default/only long-lived branch). Name it
   however's clear (`fix/...`, `feat/...`, whatever), it's not enforced.
2. **Write/update tests** for your change. This repo does not use strict TDD,
   but PRs without test coverage for new behavior will likely get asked for it.
3. **Run tests locally, in Docker**, before opening the PR:

   ```bash
   make test-src                # scraper/analyzer unit tests
   make test-backend             # backend API unit tests
   make test-backend-integration # needs local postgres — see docker-compose.yml
   make test-frontend             # Vitest unit tests
   make test-frontend-e2e         # Playwright E2E
   make test-all                  # everything, with a summary
   ```

   Integration tests (`make test-src-integration` / `make test-backend-integration`)
   need a running Postgres and, for LLM-touching tests, real provider API
   keys — if you don't have keys, it's fine to skip those locally and let CI's
   own configured keys run them; just say so in the PR.
4. **Frontend**: run `npm run lint` and `npm run format` (inside the
   `frontend` container/dir) before pushing — CI runs ESLint but not an
   auto-formatter, so a pass through Prettier first avoids review noise.
5. **Database schema changes** go through Alembic
   (`alembic/versions/`, numbered prefix) — add a migration, run `make migrate`
   against your local DB, and make sure `make migrate-down` (or the specific
   `DOWNGRADE_REV`) cleanly reverses it.
6. **Commit messages** in this repo follow `<emoji> [TYPE] <message>`, e.g.:

   ```
   🐛 [FIX] correct off-by-one in pagination
   ✨ [FEAT] add tag-group translation cache
   💤 [TEST] cover the RAG circuit breaker
   📝 [DOCS] update CLAUDE.md pipeline flow section
   ```

   `TYPE` is one of `FEAT`, `FIX`, `DOCS`, `TEST`, `REFACTOR`, `CHORE` (see
   `git log` for more examples of the emoji/type pairing in use). Not
   rigidly enforced, but appreciated for consistency.

## Opening the PR

- Fill out the PR template — it's mostly a checklist, shouldn't take long.
- CI (`.github/workflows/ci.yml`) runs automatically on PRs to `master`:
  migration check → unit tests → integration tests → frontend unit tests →
  Playwright E2E → a Lighthouse performance check against a staging deploy.
  A failed migration step auto-rolls back the staging DB.
- [`coderabbitai`](https://coderabbit.ai) auto-reviews every PR — treat its
  comments like a second pair of eyes, not a blocking gate; use judgment on
  what to act on.
- Once CI is green and the PR is approved, a maintainer merges it. Production
  deploys happen on a `v*` release tag (`.github/workflows/release.yml`), not
  on every merge to `master`.

## Code style

There's no enforced Python formatter/linter in CI today — match the style of
the surrounding code (this repo leans toward explicit, well-commented code
over cleverness; see any existing module's docstrings for the level of detail
expected). Frontend uses ESLint (`npm run lint`) + Prettier
(`npm run format`).

## Questions

Open a [discussion or issue](https://github.com/s091648/scrape-and-analyze/issues) —
whatever's easiest.
