# Quickstart: Exception Handling Guideline & API Status Code Management

## For a contributor adding a new failure case

1. **Is this an expected, recoverable failure the caller can act on** (bad input, missing resource, conflicting state, unauthorized, upstream dependency down)?
   - Yes → raise a `DomainError` subclass. Pick (or create) a leaf exception that multiply-inherits the matching shared category (`ValidationError`, `NotFoundError`, `ConflictError`, `UnauthorizedError`/`ForbiddenError`, `ExternalDependencyError`) and your bounded context's root (e.g. `CollectionDomainError`). See data-model.md §1.
   - No, it's a violated invariant / "should never happen" bug → let it propagate as whatever exception naturally occurs, or raise `AssertionError`; do **not** invent a `DomainError` subclass for it (FR-011) — it should surface as an unmapped 500 and reach Sentry, not a polished user-facing error.
2. **Where does the raise happen?**
   - Domain/application layer: raise the `DomainError` subclass directly.
   - Infrastructure layer (DB, HTTP client, external API): catch the library-specific exception and re-raise as the matching `DomainError` subclass before it crosses into the application layer (FR-003). Application-layer code should never need to import `sqlalchemy.exc` or `httpx.HTTPError`.
3. **Never hand-pick an HTTP status code in a router.** Just let the `DomainError` propagate out of the endpoint function — the central exception handler (`backend/main.py`) converts it to the right status + body automatically, using the mapping in data-model.md §2.

## Verifying the mapping works end-to-end

```bash
# 1. Run backend + src unit tests (Docker-only per Constitution Principle III)
make test-backend
make test-src

# 2. Manually exercise the mapping against a running stack
docker compose up -d backend postgres
curl -i http://localhost:8000/articles/00000000-0000-0000-0000-000000000000
# Expect: HTTP/1.1 404, body {"error": {"code": "NOT_FOUND", "message": "Article not found", "request_id": "..."}}

curl -i -H "Authorization: Bearer garbage.invalid.token" http://localhost:8000/scraper-settings
# Expect: HTTP/1.1 401, body {"error": {"code": "UNAUTHORIZED", "message": "Invalid token", "request_id": "..."}}
# Note: a request with NO Authorization header at all never reaches our guard function —
# FastAPI's HTTPBearer security scheme rejects it first with its own {"detail": "Not authenticated"}
# body (still 401, but not the ErrorResponse shape). Out of scope for this feature's DomainError
# mechanism since it happens before any application code runs.

curl -i -X POST http://localhost:8000/auth/register -H "Content-Type: application/json" -d '{"email": "<existing-email>", "username": "<u>", "password": "<p>", "name": "<n>"}'
# Expect: HTTP/1.1 409, body {"error": {"code": "CONFLICT", ...}}
```

## Checking the guideline document renders correctly

The guideline lives at `site/guide/architecture/exception-handling.md` (VitePress). Before merging, run the site build locally (not just `npm run dev`) since VitePress's production compiler is stricter about bare `<...>` outside code fences (Constitution Principle VII) — see the site's own build command in its `package.json`.
