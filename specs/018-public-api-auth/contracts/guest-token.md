# Contract: Guest Token Issuance & Refresh

Two new endpoints on the existing `/auth`-prefixed router (`backend/routers/auth.py`). Neither requires any existing credential or the new `require_any_token` guard — they are the bootstrap mechanism *for* obtaining a token, so by definition they must be reachable with nothing at all.

## `POST /auth/guest`

Issues a fresh guest access/refresh token pair. No request body, no credentials.

**Request**: no body required.

**Response** `200 OK`:
```json
{
  "access_token": "<jwt, tier=guest, token_use=access, 1h expiry>",
  "refresh_token": "<jwt, tier=guest, token_use=refresh, 30d expiry>",
  "expires_in": 3600
}
```

**Guarantees**:
- `access_token` and `refresh_token` share the same `guest_id` claim (data-model.md §1–2).
- Always succeeds (`200`) — there is no failure mode that isn't a 500 (unexpected server error, handled by the existing central handler per `017-exception-handling-guideline`).
- MUST NOT require or read any `Authorization` header — a caller with an existing valid token (real user, admin, or even another guest token) is still free to call this and gets back a brand-new, independent guest identity; this endpoint does not "upgrade" or reuse whatever the caller already presented.

## `POST /auth/guest/refresh`

Exchanges a still-valid guest refresh token for a new guest access token.

**Request**:
```json
{ "refresh_token": "<jwt>" }
```

**Response** `200 OK` (refresh token is valid and not expired):
```json
{
  "access_token": "<jwt, tier=guest, token_use=access, 1h expiry, same guest_id as the refresh token>",
  "expires_in": 3600
}
```
(No new refresh token is returned — the same refresh token remains valid until its own `exp`, per data-model.md §2's lifecycle note.)

**Response** `401 Unauthorized` (missing/malformed/expired refresh token, or a token with `token_use != "refresh"` — including an access token presented here by mistake), using the standard `ErrorResponse` shape from `specs/017-exception-handling-guideline/contracts/error-response.md`:
```json
{ "error": { "code": "UNAUTHORIZED", "message": "...", "request_id": "..." } }
```
This is the caller's (frontend's) signal to fall back to `POST /auth/guest` for a brand-new pair (spec.md User Story 2, Scenario 4) — not a signal to retry the same call.

## Every other in-scope endpoint (the `401` gate itself)

Applies to every endpoint enumerated in spec.md FR-001 (article listing/detail + filters, the analysis graph, tag-group reads, topic listing, all weekly-report endpoints, language resolution, `/chat/completions`, `/chat/quota`).

**Request header**: `Authorization: Bearer <token>`, where `<token>` is any of: a real user JWT, a real admin JWT, or a guest **access** token (never a guest refresh token — see data-model.md §2).

**On missing/invalid/expired/wrong-type token** — `401 Unauthorized`, standard `ErrorResponse` shape (identical contract to `017-exception-handling-guideline`'s `UnauthorizedError` mapping — this feature introduces no new error category, per spec.md FR-008):
```json
{ "error": { "code": "UNAUTHORIZED", "message": "...", "request_id": "..." } }
```

**On a valid token of any accepted kind** — endpoint behaves exactly as it does today; this contract adds no new success-path fields or behavior (spec.md User Story 3).

**Endpoints that already require `admin` or a specific logged-in user** (e.g. `require_admin`-gated routes) are **not** in scope for this contract — they keep their existing, stricter checks unchanged (spec.md FR-003).
