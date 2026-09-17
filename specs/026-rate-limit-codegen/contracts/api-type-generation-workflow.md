# Contract: Backend Contract → Generated Frontend Types Workflow

## Artifacts and their producer/consumer relationship

```
backend routers' Pydantic response_model / request bodies
        │  (source of truth — nothing here is hand-maintained for this purpose)
        ▼
scripts/export_openapi_schema.py            (Decision 6)
        │  imports the FastAPI `app` object directly, writes app.openapi()
        ▼
backend/openapi.json                         (checked in)
        │
        ├──► coverage-gap report               (Decision 9 — informational)
        │
        ▼
types-only OpenAPI→TS generator               (Decision 7)
        │
        ▼
frontend/lib/api/generated-types.ts           (checked in, never hand-edited)
        │
        ▼
frontend/lib/api/*.ts (topics.ts, articles.ts, ...)
        import types from generated-types.ts instead of declaring their own `interface`;
        fetch functions / apiFetch usage unchanged
```

## Regeneration command (developer-facing)

A single Makefile target (e.g. `make generate-api-types`) runs both steps (export → generate) in order, following this project's "Makefile as interface" convention (constitution IV). Running it twice in a row with no backend contract changes MUST produce no working-tree diff (FR-010).

## CI enforcement (Decision 8)

The `frontend-unit` job (`.github/workflows/ci.yml`) re-runs the same regeneration command on every `pull_request` and reconciles any diff automatically instead of just failing:

- **Trigger**: same PR pipeline that already runs `frontend-unit` (per CLAUDE.md's CI/CD section) — regeneration runs as part of that stage, since it doesn't need a running backend (Decision 6) and therefore doesn't need the `unit-test`/`integration-test` services to be up.
- **No diff**: job continues normally.
- **Diff, same-repo PR**: the job commits `backend/openapi.json` + `frontend/lib/api/generated-types.ts` (message suffixed `[skip ci]`) and pushes straight back onto the PR's own branch — the PR author never has to run the regeneration command themselves or even notice it happened, beyond a new commit appearing on their branch.
- **Diff, fork PR or a direct `push` to `master`**: `GITHUB_TOKEN` can't push to a fork's branch, and a `push` event has no PR branch to commit onto — these fall back to failing the job with a message pointing at `make generate-api-types` (this should only ever fire for a `push` if someone bypassed the PR gate, since the PR that introduced the drift would already have been auto-fixed).

This deliberately does **not** mirror this project's other generated/derived docs (UML/DB-schema diagrams, `site/.vitepress/config.js`) — see research.md Decision 8's "Correction" — those have no CI gate at all, just a `make` target regenerated fresh at each docs deploy. `generated-types.ts` gets stricter handling because it's `import`ed into the frontend's own build, not pure documentation.

## Backward-compatibility expectation

Because `frontend/lib/api/*.ts` call sites are migrated to import from `generated-types.ts` (FR-011), a backend change that removes/renames a field the frontend actually uses surfaces as a normal TypeScript compile error at the *call site*, not a silent runtime mismatch — this is the mechanism behind SC-005/edge case "regenerating frontend types would change a type in a way that breaks existing frontend code."

## Out of scope for this contract

- Any endpoint whose request/response is not backed by a Pydantic schema (raw `dict` body, missing `response_model`) is excluded from generation and appears only in the coverage-gap report (Decision 9) — its `frontend/lib/api/*.ts` counterpart keeps its current hand-written type until a follow-up defines that endpoint's schema.
- Request-sending behavior (retries, auth headers, timeout, error toasting) in `frontend/lib/api/client.ts` — untouched by this workflow.
