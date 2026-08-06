# Research: Public API Endpoint Authentication

## 1. How the guard layer verifies tokens today (baseline)

**Finding**: `backend/auth/guards.py` only ever **decodes/verifies** JWTs (`jose.jwt.decode`) — it has never minted one. Every real login/admin token is signed on the *frontend*, inside NextAuth's server-side JWT callback (Node.js, `jose` npm package), using the shared `NEXTAUTH_SECRET`. A repo-wide search for `jwt.encode` in production code (excluding tests) returns **zero** hits — only test fixtures (`backend/tests/test_guards.py`, `test_error_response_audit.py`) construct tokens today, purely for test setup.

**Implication**: giving the backend the ability to *issue* a token (the guest access/refresh pair) is a new capability, not an extension of an existing one. `python-jose` (already a `backend` dependency, already imported as `from jose import jwt` in `guards.py`) supports `jwt.encode(claims, key, algorithm="HS256")` symmetrically with the `jwt.decode` already in use — no new dependency required.

## 2. Token verification strategy for "any valid token"

**Decision**: Add one new guard function, `require_any_token`, alongside the existing `require_admin`/`require_user` in `backend/auth/guards.py`. It decodes the presented bearer token with the existing `NEXTAUTH_SECRET`/HS256 path and accepts it if either:
- it has a `role` claim (i.e. it's an existing real user/admin token, exactly what `_require_user_impl` already accepts), **or**
- it has `"tier": "guest"` **and** `"token_use"` is absent or `"access"` (a guest access token).

It rejects (→ `UnauthorizedError` → 401, per FR-001/FR-008):
- no token at all,
- a malformed/expired/wrong-signature token,
- a guest token with `"token_use": "refresh"` (FR-003: a refresh token must never work as an access token).

**Rationale**: Reuses the exact decode call, secret, and algorithm already in `guards.py` — no second verification pipeline (Assumptions in spec.md already commit to this). Keeping it as one new function (not modifying `require_user`/`require_admin`) means the existing 401/403 behavior for endpoints that already require a specific role is provably untouched (spec.md User Story 3).

**Alternatives considered**:
- *Shared service-secret header instead of JWT* — rejected earlier in the conversation that produced this spec (the user explicitly chose "any valid JWT" over a proxy-only shared secret).
- *Reuse `require_user` as-is and just relax it* — rejected: `require_user` has no concept of a "guest" tier today and would need the same branching logic anyway; a dedicated function keeps `require_user`'s contract (a *real* logged-in user) unambiguous for the endpoints that still specifically need it.

## 3. Guest identity (`guest_id`) derivation

**Finding**: `chat.py` already computes a per-visitor guest identity today: `sha256(client_ip + user_agent)[:16]`, stored client-side via the `__rag_gid` cookie so repeat requests reuse the same id (`backend/routers/chat.py::_guest_identity`). This is the only existing precedent in the codebase for "identify an anonymous visitor."

**Decision**: Reuse the same derivation (`sha256(ip + user_agent)[:16]`) as the `guest_id` embedded in the new guest access/refresh tokens, computed at issuance time. This id is carried as a claim and persists across refreshes (i.e. refreshing an access token does not change `guest_id`).

**Rationale**: Preserves today's observable behavior (a given visitor's guest chat quota is already effectively scoped by IP+UA) while satisfying the spec's clarification that guest identity must be stable across a visitor's requests. Avoids inventing a new anonymous-identity scheme when a shipped one already exists one router away.

**Alternatives considered**:
- *Random UUID per issuance, no linkage* — rejected: fails the "stable across refresh" clarification and would silently change chat's existing rate-limit granularity.
- *Cookie-only (no claim), like today* — rejected: doesn't survive the stated design (a JWT the guest carries and presents as `Authorization: Bearer`, not a cookie the backend reads directly for identity).

## 4. Token lifetimes

**Decision** (per user's explicit answer, spec.md Clarifications):
- Guest **access** token: `exp` = issuance + 1 hour.
- Guest **refresh** token: `exp` = issuance + 30 days.

**Rationale for the refresh-token number specifically** (not explicitly given by the user, chosen as a reasonable default consistent with a stateless, low-privilege, read-mostly credential): long enough that a returning visitor within the same browser session/day doesn't re-trigger full issuance on every visit, short enough that a stale/abandoned refresh token doesn't linger indefinitely. Because both tokens are stateless (research.md §2, spec.md Clarifications), this number is a pure constant with no migration cost to change later — flagged here for the user to override if 30 days doesn't match their intent.

**Alternatives considered**: matching the refresh token's lifetime to typical "remember me" durations (e.g. 90 days) — rejected as unnecessarily long for a credential that identifies "some guest," not a person, and that the frontend can re-acquire transparently at zero UX cost if it does expire (spec.md User Story 2, Scenario 4).

## 5. Token claim shapes

**Decision**:
```
Guest access token claims:  {"tier": "guest", "guest_id": "<16-hex>", "token_use": "access",  "exp": <issued_at + 1h>}
Guest refresh token claims: {"tier": "guest", "guest_id": "<16-hex>", "token_use": "refresh", "exp": <issued_at + 30d>}
```
Existing real user/admin tokens are untouched — they keep their current `{"sub", "role", "exp"}` shape (`backend/routers/auth.py`, frontend NextAuth callback). `require_any_token` (research.md §2) distinguishes the two families by presence of `role` vs. `tier == "guest"`.

## 6. Where the new endpoints live

**Decision**: Add two endpoints to the existing `backend/routers/auth.py` (already the `/auth`-prefixed router for all authentication concerns):
- `POST /auth/guest` — issues a fresh access+refresh pair. Takes no credentials; reads client IP/User-Agent from the request the same way `chat.py::_guest_identity` does today.
- `POST /auth/guest/refresh` — takes `{"refresh_token": "<jwt>"}`, validates it's a non-expired guest token with `token_use == "refresh"`, and returns a new access token (same `guest_id`, fresh `exp`).

Business logic (claim construction, signing) lives in `backend/services/auth_service.py` alongside the other user/auth logic, per Constitution Principle IX ("routers = route handlers only, services = business logic").

**Rationale**: `/auth` is already the single home for every authentication concern in this codebase; a separate `backend/routers/guest.py` would split one concern (issuing credentials) across two routers for no benefit at this scale (2 endpoints).

**Alternatives considered**: a dedicated `backend/routers/guest.py` — rejected as unnecessary proliferation; auto-issuing a guest token via response headers on any 401 instead of a dedicated endpoint — rejected as too implicit/surprising for an HTTP API contract and harder to test in isolation.

## 7. `chat.py` migration

**Finding**: `chat.py::_parse_identity` already extracts `ChatIdentity(tier="admin"|"user", user_id=...)` from a real JWT's `role`/`sub` claims when present, and only falls back to `_guest_identity()` (the ip-hash/cookie logic) when no such token is presented at all. `/chat/completions` and `/chat/quota` currently accept the request either way (token optional).

**Decision**: `chat.py` gains the same `require_any_token` dependency as every other in-scope endpoint (FR-001), so a request with no token or an invalid one now 401s before reaching `_parse_identity` at all. `_parse_identity`/`ChatIdentity` construction is extended to also recognize `"tier": "guest"` tokens, reading `guest_id` directly from the token's claim instead of calling `_guest_identity()`. The `__rag_gid` cookie and `_guest_identity()` function are removed (FR-007) — the guest token *is* the identity now, nothing to derive from a cookie anymore.

**Rationale**: `RateLimitService`'s tier/key logic is untouched (spec.md Edge Cases: "same limits and tiers, only the identity source changes") — this is a pure identity-source swap, not a rate-limiting redesign.

## 8. Frontend integration point

**Finding**: The frontend has no central "attach auth header" layer — `apiFetch()` (`frontend/lib/api/client.ts`) does not touch `Authorization` at all; every `lib/api/*.ts` call site that needs auth takes an explicit `token?: string` parameter and builds the header itself via a local `authHeader(token)`/`authHeaders(token)` helper (e.g. `lib/api/scraper-settings.ts`, `lib/api/auth.ts`), with the token itself coming from `useSession()` (NextAuth) in the calling component. Fully-public call sites today (`lib/api/articles.ts` et al.) simply omit the parameter. A `GuestModeProvider` (`frontend/lib/providers/guest-mode-provider.tsx`) already exists, tracking an `isGuestMode` boolean in `sessionStorage`, keyed off `useSession()`'s status.

**Decision**: Extend the existing guest-mode provider (or a sibling provider colocated with it) to also own the guest access/refresh token pair: acquire one via `POST /auth/guest` whenever `useSession()` resolves to "no authenticated user," store it (sessionStorage, consistent with the provider's existing storage choice — a guest token carries no real-identity data, so the XSS exposure profile is materially lower than a real session token), and expose it so every currently-public `lib/api/*.ts` function can adopt the exact same `token?: string` + `authHeader(token)` pattern already used by the protected ones. Silent refresh (spec.md User Story 2, Scenarios 3–4) is a timer/on-401-retry concern inside this same provider.

**Rationale**: Zero new conventions — this is the same `Authorization: Bearer` pattern the codebase already uses everywhere else, just applied to endpoints that skip it today. Centralizing acquisition/refresh in one provider (rather than duplicating fetch-and-cache logic per page/component) matches how `GuestModeProvider` already centralizes guest-mode state.

**Alternatives considered**: attaching the token inside the Next.js proxy route (`app/api/proxy/[...path]/route.ts`) instead of client-side — rejected: the proxy runs server-side per-request with no client session-storage access, and would need its own guest-token acquisition/caching layer duplicating what NextAuth's session already does for real users; keeping token attachment client-side (mirroring the existing pattern) is simpler and consistent.

## 9. Sequencing implication (not a design decision, a note for `/speckit-tasks`)

Because gating an endpoint (backend) and attaching a token to every call site that hits it (frontend) must land together — a backend-only rollout would 401 the *current* production frontend, and a frontend-only change has nothing to call — task breakdown should treat "issue endpoints + `require_any_token` + `chat.py` migration" (backend) and "guest-token provider + call-site updates" (frontend) as one atomically-deployed unit per spec.md's User Story 1+2 pairing, not two independently-shippable phases.
