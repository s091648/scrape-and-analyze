# Data Model: Public API Endpoint Authentication

This feature introduces no database tables and no Alembic migration — both credential types are stateless (research.md §1–2, spec.md Clarifications). The "data model" here is the shape of the two new JWT claim sets, plus the (unchanged) existing token/user shapes they must coexist with.

## 1. Guest Access Token (JWT claims)

| Claim | Type | Notes |
|---|---|---|
| `tier` | `"guest"` (literal) | Distinguishes this from a real user/admin token, which has no `tier` claim and instead carries `role`. |
| `guest_id` | string, 16 lowercase hex chars | `sha256(client_ip + user_agent)[:16]`, computed once at issuance (research.md §3). Stable across refreshes of the same guest session. |
| `token_use` | `"access"` (literal) | Present so `require_any_token` can reject a refresh token presented as an access token (FR-003). |
| `exp` | Unix timestamp | Issuance time + 1 hour (FR-005). |

**Validation rules** (enforced by `require_any_token`, research.md §2):
- Signature MUST verify against `NEXTAUTH_SECRET` (the same secret/algorithm — HS256 — already used to verify real user/admin tokens).
- `exp` MUST NOT be in the past.
- `token_use` MUST be `"access"` (or absent — but issuance always sets it explicitly).

**Lifecycle**: issued by `POST /auth/guest` and by `POST /auth/guest/refresh`. Never persisted server-side. Cannot be individually revoked; only expires naturally (spec.md Assumptions).

## 2. Guest Refresh Token (JWT claims)

| Claim | Type | Notes |
|---|---|---|
| `tier` | `"guest"` (literal) | Same family as the access token it was issued alongside. |
| `guest_id` | string, 16 lowercase hex chars | Identical value to the paired access token's `guest_id` — carried forward into every subsequently-issued access token from this refresh token (FR-005). |
| `token_use` | `"refresh"` (literal) | Distinguishes it from an access token. `require_any_token` MUST reject any token with this value (FR-003). |
| `exp` | Unix timestamp | Issuance time + 30 days (research.md §4). |

**Validation rules** (enforced by `POST /auth/guest/refresh` only — this token is never sent to any other endpoint):
- Signature MUST verify against `NEXTAUTH_SECRET`.
- `exp` MUST NOT be in the past (an expired refresh token → 401, frontend falls back to full re-issuance per spec.md User Story 2 Scenario 4).
- `token_use` MUST be `"refresh"`.

**Lifecycle**: issued only by `POST /auth/guest`, alongside its paired access token. Consumed by `POST /auth/guest/refresh`, which returns a new access token carrying the same `guest_id` (the refresh token itself is not rotated/re-issued — the client keeps using the same refresh token until *it* expires, at which point the client re-issues a whole new pair).

## 3. Existing real user/admin token (unchanged)

| Claim | Type | Notes |
|---|---|---|
| `sub` | string (UUID) | Existing user id — unchanged. |
| `role` | `"user"` \| `"admin"` | Sourced from `models.auth.User.role`, unchanged (FR-004). |
| `exp` | Unix timestamp | Existing NextAuth-controlled session lifetime — unchanged. |

`require_any_token` accepts any token with a `role` claim present, regardless of its value, exactly as `require_user` already does today — no new logic on this path (research.md §2).

## 4. Entity relationship summary

```
User (existing, unchanged)
  └─ role ──────────────► embedded verbatim into the existing login JWT's `role` claim (unchanged flow)

Guest Access Token ◄──── issued alongside ────┐
  guest_id ────────────► carried forward ─────┤ Guest Refresh Token
  (no DB row, no FK to anything)               guest_id (same value)
```

No relationship to `User` exists or is needed — a guest is explicitly not a `User` row (spec.md: "without identifying a real person").
