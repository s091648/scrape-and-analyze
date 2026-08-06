
# Feature Specification: Public API Endpoint Authentication

**Feature Branch**: `018-public-api-auth`

**Created**: 2026-07-23

**Status**: Draft

**Input**: User description: "為目前完全公開(無任何 auth 檢查)的 backend API endpoint 加上「任何有效 token 即可」的存取控制,防止外部 consumer 繞過前端直接打 API 拿到未受保護的資料。不做 RBAC,只做「有沒有合法 token」的檢查。讓 backend 也對訪客發一組輕量的 guest JWT,前端的 Guest Mode 與訪客瀏覽都改成先跟 backend 換一組 guest token,之後打其他公開端點時帶上這組 token。真實登入使用者(含 admin)用原本的 JWT,角色仍從 User.role 判斷,不受影響。"

## Background

Today, every endpoint listed as "Public" in the backend routers table (article listing/detail, the analysis graph, tag-group reads, topic listing, weekly reports, language resolution, and the chat endpoints) performs **no server-side check at all**. Anything that looks like protection for anonymous visitors — the blurred/placeholder article view for users who haven't chosen Guest Mode — is applied entirely on the frontend. Anyone who calls the backend directly (bypassing the Next.js proxy and its UI-level blur) receives the same complete, unblurred data as a logged-in user, for free, with no rate limiting beyond what `chat.py` already does for chat specifically.

Separately, `specs/009-guest-mode` already defined a "Guest Mode" experience: a visitor who clicks "continue as guest" on the login page gets to see real first-page article data without registering. That mode is currently tracked purely on the frontend (no token of any kind reaches the backend for it), and `chat.py`'s guest chat tier is tracked via a plain (unsigned-for-auth-purposes) cookie, not a verifiable credential.

This feature closes the server-side gap: every one of these endpoints must see *some* valid, verifiable token before responding, while preserving today's user-visible behavior — anonymous/guest visitors keep seeing what they see today, logged-in users (including admins) are unaffected. This is **not** a permissions/RBAC change: endpoints that already require `admin` or a specific logged-in user keep exactly the checks they have today, driven by the same `role` column on the existing `User` record. This feature only adds a floor requirement — "does the caller present a valid token at all" — under the endpoints that currently require nothing.

## Clarifications

### Session 2026-07-23

- Q: Should the guest token be fully stateless (self-signed JWT, no DB row, cannot be individually revoked before expiry) or server-tracked (a DB-backed guest session row, individually revocable, needs cleanup)? → A: Stateless — a self-signed JWT verified the same way existing login tokens are, no new table, no revocation-before-expiry capability.
- Q: How long should a guest token stay valid? → A: A short-lived (1 hour) guest access token, plus a longer-lived guest refresh token the frontend can silently exchange for a new access token without repeating full guest-token issuance — mirroring the access/refresh split common to token-based auth, kept stateless per the prior answer (the refresh token is itself a self-signed JWT with its own longer expiry and a distinct claim marking it as refresh-only, not a DB-tracked session).
- Q: Should the guest token carry a stable per-visitor identifier across requests/refreshes? → A: Yes — a stable guest identifier persists across a guest access token's refreshes (and is carried into each replacement access token), analogous to `chat.py`'s existing ip-hash-derived `guest_id`, so a single visitor's activity can be correlated without identifying a real person.
- Q: `chat.py`'s existing guest identification (the `__rag_gid` cookie plus an ip-hash-derived `guest_id`) — replace it with the new guest token, or keep both mechanisms side by side? → A: Replace it. `chat.py` is brought into this feature's single guest-token mechanism: it now also requires a valid token (guest or logged-in) like every other in-scope endpoint, and its rate limiting keys off the guest identifier carried inside the guest access token instead of computing its own ip-hash or relying on the `__rag_gid` cookie.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - External API consumer without a token can no longer read data (Priority: P1)

Someone who calls the backend's article/topic/graph/weekly-report/chat endpoints directly — without going through the site's frontend and without any token — is refused instead of receiving real data.

**Why this priority**: This is the actual security gap being closed. Every other story exists to make sure closing it doesn't break the legitimate visitors who currently get in "for free" via the frontend.

**Independent Test**: Call any in-scope endpoint (e.g. article listing, topic listing, weekly report listing) with no `Authorization` header and confirm a 401 response using the standard error shape, instead of the actual data.

**Acceptance Scenarios**:

1. **Given** no token is presented, **When** a request is made to any endpoint that is today fully public, **Then** the response is `401 Unauthorized` with the standard error-response shape (`error.code = "UNAUTHORIZED"`) and no application data is included.
2. **Given** a malformed or expired token is presented, **When** a request is made to any such endpoint, **Then** the response is the same `401 Unauthorized` shape as scenario 1.
3. **Given** a valid token of any kind (guest, regular user, or admin) is presented, **When** a request is made to any such endpoint, **Then** the request succeeds exactly as it does today.

---

### User Story 2 - Anonymous site visitors keep browsing without registering (Priority: P1)

A visitor who has never logged in — including someone who picks "continue as guest" per `specs/009-guest-mode`, and someone who opens the chat widget without an account — keeps getting the same real, working experience they get today. Behind the scenes, the frontend obtains a short-lived guest token from the backend and attaches it to these calls; the visitor never sees a login prompt or registration step they don't see today.

**Why this priority**: Without this, User Story 1 would break two already-shipped, user-facing features (Guest Mode, guest chat) the moment the server-side check goes live. This has to land together with Story 1, not after it.

**Independent Test**: With no prior login, request a guest token from the backend, then call an in-scope endpoint (e.g. article listing) using only that token, and confirm it succeeds with real (non-placeholder) data — matching what `specs/009-guest-mode` already promises for Guest Mode.

**Acceptance Scenarios**:

1. **Given** a visitor with no account and no prior session, **When** they trigger a flow that today requires no token (default homepage load, Guest Mode entry, opening chat), **Then** the frontend transparently obtains a guest token and the visitor's experience is unchanged from today's.
2. **Given** a visitor is using a guest token, **When** they attempt an action that already requires a real logged-in user or admin (e.g. saving a favorite, admin settings), **Then** they are refused exactly as an anonymous visitor is refused today — a guest token grants no more access than "no token" does for anything outside this feature's scope.
3. **Given** a guest access token has expired but the guest refresh token has not, **When** the visitor makes another request, **Then** the frontend silently exchanges the refresh token for a new access token, without the visitor needing to take any action.
4. **Given** both the guest access token and the guest refresh token have expired, **When** the visitor makes another request, **Then** the frontend transparently starts over and obtains a brand-new guest token pair, without the visitor needing to take any action.

---

### User Story 3 - Existing logged-in users and admins are unaffected (Priority: P2)

Someone who is already logged in (regular user or admin) continues to use every endpoint in scope exactly as before, with the same token they already have. Their role continues to come from the same place it does today.

**Why this priority**: Lower priority than Stories 1–2 only because it's a "keep working" guarantee rather than new behavior — but it must be verified, since it's easy for a blanket "require a token" change to accidentally also require re-authentication or a role re-check that doesn't exist today.

**Independent Test**: Log in as a regular user (or admin), call an in-scope endpoint with the existing session token, and confirm it succeeds with no change in behavior, latency, or required steps compared to before this feature.

**Acceptance Scenarios**:

1. **Given** an already-logged-in regular user, **When** they call any endpoint in this feature's scope, **Then** the request succeeds exactly as before, with no re-login and no new prompt.
2. **Given** an already-logged-in admin, **When** they call any endpoint in this feature's scope (including the ones that already required `admin`), **Then** the request succeeds exactly as before — this feature does not add any new check on top of the existing admin check.

---

### Edge Cases

- A caller presents a token signed for something unrelated (garbage/random string) → same `401` as no token at all.
- A guest access token is replayed after its expiry → `401`, and the frontend must be able to recover by silently exchanging the refresh token for a new access token, or — if that has also expired — obtaining a brand-new guest token pair (see Story 2, Scenarios 3–4).
- A guest refresh token is presented directly to an in-scope endpoint instead of an access token → `401`, identical to presenting no token at all (FR-003).
- A guest token is presented to an endpoint that requires `admin` or a specific logged-in user → refused with the same status those endpoints already return for an anonymous caller today (no new information is leaked about why).
- Chat's existing per-tier rate limiting (guest vs. user, in `chat.py`'s `RateLimitService`) continues to apply with the same limits and tiers; only the identity it keys off changes — the guest identifier now comes from the guest access token instead of `chat.py`'s own ip-hash/`__rag_gid` cookie logic (which this feature retires). This feature does not change the limits themselves.
- A very high rate of guest-token issuance (e.g. a scraper repeatedly requesting fresh guest tokens to defeat the whole point of this feature) is a known residual risk — out of scope for this feature, which only closes the "zero authentication" gap, not abuse-resistance of guest-token issuance itself.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST reject, with `401 Unauthorized`, any request to an endpoint currently listed as fully public (article listing/detail and its filter endpoints, the analysis graph, tag-group read endpoints, topic listing, all weekly-report endpoints, language resolution, and the chat endpoints) when no valid token is presented — reusing the existing `UnauthorizedError` → 401 mapping and standard error-response shape already established for the rest of the API.
- **FR-002**: System MUST provide a way for a caller with no account to obtain a valid guest access token (and its paired guest refresh token) without providing any credentials (no email/password/registration step).
- **FR-003**: A guest access token MUST be accepted as "a valid token" by every endpoint in this feature's scope, and MUST NOT grant any access beyond that — it MUST continue to be refused by every endpoint that already requires a specific logged-in user or `admin` role, with no change to those existing checks. A guest refresh token MUST NOT itself be accepted as a valid access token anywhere — it is only usable to obtain a new guest access token.
- **FR-004**: Existing logged-in user and admin tokens (issued through the current login flow) MUST continue to work, unchanged, both for the endpoints they already access and for the newly-gated previously-public endpoints. Role MUST continue to be determined the same way it is today — from the `role` column on the existing user record — with no new role logic introduced by this feature.
- **FR-005**: A guest access token MUST expire 1 hour after issuance. System MUST provide a way to exchange a still-valid guest refresh token for a new guest access token without repeating full guest-token issuance, and the frontend MUST perform this exchange transparently (no visible interruption) whenever an access token expires. When the refresh token has also expired, the frontend MUST fall back to obtaining a brand-new guest token pair, again transparently.
- **FR-006**: This feature MUST NOT introduce any new permission tier or role — for the endpoints in scope, the only distinction is "has a valid token" vs. "does not"; a guest token, a regular user's token, and an admin's token are all equally sufficient to pass this check.
- **FR-007**: Every frontend flow that today reaches an in-scope endpoint without a token (default anonymous homepage load, `specs/009-guest-mode` Guest Mode, guest chat) MUST be updated to transparently acquire and attach a guest token, so that end-user-visible behavior for these flows is unchanged from what those existing specs describe. `chat.py`'s existing `__rag_gid` cookie and ip-hash-derived guest identification MUST be retired in favor of the guest identifier carried in the guest access token — chat keeps exactly one guest-identification mechanism, not two.
- **FR-008**: All `401` responses produced by this feature MUST use the same `ErrorResponse` contract and central exception-handling mechanism defined in `specs/017-exception-handling-guideline` — no bespoke error shape for this feature.

### Key Entities

- **Guest Access Token**: A backend-issued, self-contained (stateless) credential, valid for 1 hour, that proves "this caller is a legitimate anonymous visitor" without identifying a real person or requiring a password. It is not backed by a database row — the backend does not track issued guest tokens and cannot revoke one individually before it naturally expires. Carries no role beyond "guest" and is never accepted where a specific logged-in user or `admin` is required. Carries a stable guest identifier (analogous to `chat.py`'s existing ip-hash-derived `guest_id`) that persists across refreshes, so one visitor's activity across requests can be correlated without identifying a real person.
- **Guest Refresh Token**: A longer-lived, backend-issued, self-contained (stateless) credential issued together with a Guest Access Token, carrying the same stable guest identifier. Its only purpose is to be exchanged for a new Guest Access Token (carrying that same identifier forward) when the current one expires; it is never itself accepted as a valid access token by any in-scope endpoint.
- **User** *(existing, unchanged)*: The existing account record; its `role` continues to be the sole source of truth for admin-vs-regular-user distinctions, exactly as today.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 100% of requests to previously fully-public endpoints with no token, or an invalid/expired token, receive `401` instead of real data.
- **SC-002**: Anonymous visitors, Guest Mode users, and guest chat users see no change in what they can do or see compared to before this feature — zero new login/registration prompts introduced for flows that don't have one today.
- **SC-003**: Logged-in users and admins experience zero change in behavior — no re-authentication, no new prompts, no latency-visible extra step — when using any endpoint in scope.

## Assumptions

- This feature builds on the `DomainError` → HTTP status mechanism and `ErrorResponse` contract delivered by `specs/017-exception-handling-guideline`; it reuses `UnauthorizedError` → 401 rather than introducing a new error category.
- Guest tokens are verified through the same signing/verification path the existing login tokens already use (`backend/auth/guards.py`), so no second, parallel verification mechanism is introduced — a guest token is simply a token whose claims mark it as a guest rather than a specific user.
- Guest tokens are stateless (self-signed, no database-backed session record). This means the system cannot revoke an individual guest token before it expires — the only mitigation for a compromised or abused guest token is waiting out its short lifetime. This tradeoff was chosen deliberately to avoid introducing a new table and cleanup job for what is, by design, a low-stakes, read-mostly credential.
- RBAC / fine-grained permissions are explicitly out of scope. This feature only adds a "some valid token is present" floor to endpoints that currently have none; it does not change what any given role is allowed to do.
- Rate limiting is out of scope beyond what `chat.py` already implements today; this feature changes how a caller proves who/what they are, not how their usage is throttled.
- Abuse-resistance of guest-token issuance itself (e.g. a bot minting unlimited guest tokens) is out of scope for this feature.
