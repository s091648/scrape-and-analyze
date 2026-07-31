# Router Audit: Previously-Public Endpoints Gaining `require_any_token` (FR-001)

One row per endpoint in the routers spec.md FR-001 names. "Before" = current auth dependency (none, confirmed by reading each file). "After" = `require_any_token` added, per this feature's design (research.md §2, contracts/guest-token.md).

| Router | Endpoint | Before | After |
|---|---|---|---|
| `articles.py` | `GET /articles` | none | `require_any_token` |
| `articles.py` | `GET /source-categories` | none | `require_any_token` |
| `articles.py` | `GET /articles/filters/sources` | none | `require_any_token` |
| `articles.py` | `GET /articles/filters/original-sources` | none | `require_any_token` |
| `articles.py` | `GET /articles/filters/tags` | none | `require_any_token` |
| `articles.py` | `GET /articles/{article_id}` | none | `require_any_token` (existing `NotFoundError` behavior unchanged) |
| `articles.py` | `POST /articles/{article_id}/view` | none | `require_any_token` |
| `articles.py` | `POST /admin/articles/flush-view-counts` | `require_admin` | **unchanged** — already admin-gated, out of scope |
| `graph.py` | `GET /analyses/graph` | none | `require_any_token` |
| `graph.py` | `GET /analyses/graph/group/{group_name}` | none | `require_any_token` |
| `tags.py` | `GET /tag-groups` | none | `require_any_token` |
| `tags.py` | `GET /tag-groups/{group_id}` | none | `require_any_token` |
| `tags.py` | all other endpoints (create/update/delete/merge/reorder tag-groups, rename/delete/batch-move tags, suggestions) | `require_admin` | **unchanged** — already admin-gated, out of scope |
| `topics.py` | `GET /topics` | none | `require_any_token` |
| `topics.py` | `POST /topics`, `PATCH /topics/{id}`, `DELETE /topics/{id}` | `require_admin` | **unchanged** — already admin-gated, out of scope |
| `weekly_reports.py` | `GET /weekly-reports` | none | `require_any_token` |
| `weekly_reports.py` | `GET /weekly-reports/latest` | none | `require_any_token` |
| `weekly_reports.py` | `GET /weekly-reports/weeks` | none | `require_any_token` |
| `weekly_reports.py` | `GET /weekly-reports/by-week` | none | `require_any_token` |
| `languages.py` | `GET /languages` | none | `require_any_token` |
| `chat.py` | `POST /chat/completions` | none (optional `Authorization` header, guest cookie fallback) | `require_any_token` + `_parse_identity` reads `guest_id` from the token instead of `__rag_gid`/ip-hash (research.md §7) |
| `chat.py` | `GET /chat/quota` | none (same as above) | same migration as `/chat/completions` |
| `monitoring.py` | `GET /failed-tasks` | none | `require_admin` — closed out during the `backend/tests/integration/` coverage pass (`017-exception-handling-guideline`); not part of FR-001's `require_any_token` rollout since this is operational/internal data, not public-facing content |

**Explicitly out of scope** (unchanged by this feature): `graph.py` has no other endpoints. `grafana.py`, `metric_definitions.py`'s public `GET /metric-definitions`, and `llm_providers.py` are not named in spec.md FR-001 and are not touched here — `GET /metric-definitions` in particular remains public per its own documented `017`-era classification and is not part of this feature's scope (not listed in spec.md's Background/FR-001 enumeration).

**Summary**: 11 previously-unauthenticated GET/POST endpoints across 6 routers (`articles.py`, `graph.py`, `tags.py`, `topics.py`, `weekly_reports.py`, `languages.py`) plus `chat.py`'s 2 endpoints (migrated off bespoke guest-cookie logic, not merely gated) gain `require_any_token`. Every already-`require_admin`-gated endpoint in these same router files is confirmed untouched.
