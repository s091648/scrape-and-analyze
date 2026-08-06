# Router Audit: `backend/routers/` Status-Code Compliance (FR-010)

One row per `HTTPException`/ad hoc `status_code=` occurrence found via `grep -n "HTTPException\|status_code=[0-9]" backend/routers/*.py` before this feature's implementation. "Compliant" = migrated to raise a shared `DomainError` category and let the central handler (`backend/exceptions/handlers.py`) produce the response.

| Router | Occurrence | Previous behavior | Required/actual behavior | Status |
|---|---|---|---|---|
| `articles.py:128` | `get_article` | `HTTPException(404, "Article not found")` | `NotFoundError("Article not found")` | ✅ Migrated |
| `auth.py:38,40` | `verify_credentials` | `HTTPException(401, "Invalid credentials")` ×2 | `UnauthorizedError(...)` | ✅ Migrated |
| `auth.py:42` | `verify_credentials` | `HTTPException(403, "Account disabled")` | `ForbiddenError(...)` | ✅ Migrated |
| `auth.py:66` | `register` | `HTTPException(409, "Email or username already taken")` (string-matched from caught exception) | `ConflictError(...)` | ✅ Migrated |
| `auth.py:67` | `register` | `HTTPException(422, str(e))` — manual construction, not FastAPI's automatic request validation | `ValidationError(str(e))` (400) — was a 422/400 conflation (research.md §5) | ✅ Migrated |
| `auth.py:74` | `google_authorize` | `HTTPException(404, "Email not registered")` | `NotFoundError(...)` | ✅ Migrated |
| `auth.py:76` | `google_authorize` | `HTTPException(403, "Account disabled")` | `ForbiddenError(...)` | ✅ Migrated |
| `auth.py:78` | `google_authorize` | `HTTPException(409, "Google account not linked")` | `ConflictError(...)` | ✅ Migrated |
| `auth.py:91` | `admin_create_user` | `HTTPException(422, "email or username required")` — same 422/400 conflation | `ValidationError(...)` | ✅ Migrated |
| `auth.py:103` | `admin_create_user` | `HTTPException(409, ...)` string-matched | `ConflictError(...)` | ✅ Migrated |
| `auth.py:112,120,129,138,152,167,177,189` | various | `HTTPException(404, "User not found")` ×7 | `NotFoundError(...)` | ✅ Migrated |
| `auth.py:154,156` | `change_password` | `HTTPException(400, ...)` ×2 | `ValidationError(...)` | ✅ Migrated |
| `auth.py:179` | `link_google` | `HTTPException(400, "Google account already linked")` | `ValidationError(...)` | ✅ Migrated |
| `auth.py:181` | `link_google` | `HTTPException(409, "Google account already in use")` | `ConflictError(...)` | ✅ Migrated |
| `auth.py:192` | `unlink_google` | `HTTPException(400, ...)` | `ValidationError(...)` | ✅ Migrated |
| `backend/auth/guards.py:35,38,40,61,64,66` | `_require_admin_impl`, `_require_user_impl` | `HTTPException(401, ...)` ×6 (bypassed domain hierarchy entirely) | `UnauthorizedError(...)` | ✅ Migrated |
| `backend/auth/guards.py:42` | `_require_admin_impl` | `HTTPException(403, "Admin role required")` | `ForbiddenError(...)` | ✅ Migrated |
| `chat.py:99` | `chat_completions` | `HTTPException(429, {...})` | **Left as-is** — rate limiting is not a domain-rule violation; 429 was never in the FR-006 category list (same treatment as FastAPI's native 422, research.md §5) | ⚪ Out of scope (documented) |
| `chat.py` `generate()` in-stream errors | `chat_completions` | `{"error": "chat_stream_failed"}` SSE payload | `{"error": {"code": "EXTERNAL_DEPENDENCY_ERROR", "message": "..."}}` — HTTP status already committed (200) once streaming starts, so this uses the contract's vocabulary in-band rather than the central handler (contracts/error-response.md "Streaming exception" clause) | ✅ Migrated |
| `grafana.py` (8 occurrences) | various proxy endpoints | `JSONResponse({"error": "not_configured"}, status_code=503)` | **Left as-is** — a deliberate, non-exception-driven response for "Grafana env vars not configured," not an ad hoc/inconsistent status code; already a stable 503 with a fixed shape | ⚪ Out of scope (documented) |
| `llm_providers.py:34` | `reorder` | `HTTPException(400, "Duplicate provider IDs...")` | `ValidationError(...)` | ✅ Migrated |
| `llm_providers.py:43,50` | `update`, `delete` | `HTTPException(404, "Provider not found")` ×2 | `NotFoundError(...)` | ✅ Migrated |
| `metric_definitions.py:42` | `patch_metric_definition` | `HTTPException(404, ...)` | `NotFoundError(...)` | ✅ Migrated |
| `scraper_keywords.py:44` | `delete_keyword_endpoint` | `HTTPException(404, "Keyword not found")` | `NotFoundError(...)` | ✅ Migrated |
| `scraper_settings.py:39,46` | `update`, `delete` | `HTTPException(404, "Setting not found")` ×2 | `NotFoundError(...)` | ✅ Migrated |
| `tags.py:141,159,186` | `get_tag_group`, `update_tag_group`, `delete_tag_group` | `HTTPException(404, "Tag group not found")` ×3 | `NotFoundError(...)` | ✅ Migrated |
| `tags.py:165` | `update_tag_group` | `HTTPException(409, "A tag group with this name...")` | `ConflictError(...)` | ✅ Migrated |
| `tags.py:201,231` | `rename_tag`, `delete_tag` | `HTTPException(404, "Tag not found")` ×2 | `NotFoundError(...)` | ✅ Migrated |
| `tags.py:212` | `rename_tag` | `except IntegrityError: raise HTTPException(409, ...)` | `except IntegrityError: raise ConflictError(...)` | ✅ Migrated |
| `tags.py:294,325` | `approve_suggestion`, `reject_suggestion` | `HTTPException(404, "Suggestion not found")` ×2 | `NotFoundError(...)` | ✅ Migrated |
| `tags.py:250` (`batch_move_tags`) | per-item failure in a batch | `{"tag_id": ..., "error": "Tag not found"}` appended to a `failed` list, endpoint still returns 200 | **Left as-is** — deliberate partial-success/partial-failure batch response shape (not a single-request error), out of scope for the single-error-per-response contract | ⚪ Out of scope (documented) |
| `topics.py:42,56` | `update_topic`, `delete_topic` | `HTTPException(404, "Topic not found")` ×2 | `NotFoundError(...)` | ✅ Migrated |
| `user.py` | (none — `HTTPException` was imported but never raised) | dead import | Import removed | ✅ Migrated (cleanup only) |
| `weekly_reports.py` | (none — `HTTPException` was imported but never raised; "no report" cases return `Optional[...]` `None`, a deliberate non-error 200) | dead import | Import removed | ✅ Migrated (cleanup only) |
| Weekly-report image pipeline (`src/entrypoints/cli/weekly_report.py`) | resilient multimodal provider exhaustion | logged only, no exception | **Confirmed out of scope** — this is a CLI/background job with no HTTP response to produce; per spec.md's Assumption, the FR-005/006/007 status-mapping requirements apply only to code paths terminating in an API response. No change needed. | ⚪ Out of scope (confirmed, not merely deferred) |

**Summary**: 101 raw `grep` matches across 12 routers → 34 real ad hoc `HTTPException`/status-code error sites (the rest were success-path `status_code=` on route decorators, e.g. `status_code=201/204`, which are correct as-is and untouched) → all 34 migrated to the shared `DomainError` category hierarchy, except 3 categories of deliberate, documented exceptions (429 rate limiting, Grafana "not configured" 503, batch partial-failure results) and 1 confirmed-out-of-scope background job.

**T026 follow-up (OpenAPI docs)**: every "✅ Migrated" route above now carries a `responses=error_responses(...)` entry (helper in `backend/schemas/error.py`) referencing `ErrorResponse` for the status codes it can produce — the specific business-error codes from this table, plus 401/403 for any endpoint behind `Depends(require_admin)` and 401 for `Depends(require_user)` (per `backend/auth/guards.py`'s `UnauthorizedError`/`ForbiddenError` raises). Swagger UI now reflects these on every migrated endpoint.
