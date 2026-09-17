# Feature Specification: API Rate Limiting & Generated Frontend Types

**Feature Branch**: `026-rate-limit-codegen`

**Created**: 2026-09-16

**Status**: Draft

**Input**: User description: "我會需要開一個新的 spec, 要來實作上面說的 rate limit 以及 codegen。" (Implement rate limiting for the public API and adopt contract-driven generation of the frontend's API types, as previously discussed.)

## User Scenarios & Testing *(mandatory)*

<!--
  This feature bundles two related but independently deliverable capabilities that
  were scoped together in the originating discussion:
  (A) Rate limiting for abuse-prone API endpoints.
  (B) Generating the frontend's API type definitions from the backend's API contract
      instead of hand-maintaining them, to eliminate silent drift.
  Each is its own set of prioritized, independently testable stories below.
-->

### User Story 1 - Anonymous credential issuance is throttled (Priority: P1)

A malicious or misbehaving client repeatedly requests new guest/anonymous access credentials from the same origin in a short period. The system recognizes the pattern and starts refusing the excess requests, instead of minting an unlimited number of credentials.

**Why this priority**: Guest credential issuance requires no prior authentication today, so it is the cheapest entry point for abuse and indirectly gates access to every other endpoint that accepts a guest credential. Protecting it has the highest leverage of any single change in this feature.

**Independent Test**: Can be fully tested by issuing repeated guest-credential requests from a single origin in a short window and confirming that requests beyond the allowed count are refused with a distinguishable "too many requests" outcome, while requests from a different origin are unaffected.

**Acceptance Scenarios**:

1. **Given** a client with no prior requests, **When** it requests guest credentials at a normal pace, **Then** every request succeeds.
2. **Given** a client that has already requested guest credentials up to the allowed count within the current window, **When** it requests again, **Then** the request is refused with a response that clearly identifies it as rate-limited (not a generic failure) and indicates when the client may retry.
3. **Given** two different clients (different origins), **When** one of them is currently rate-limited, **Then** the other client's requests are unaffected.

---

### User Story 2 - Login, registration, and token-refresh attempts are throttled (Priority: P1)

An attacker attempts to guess credentials, enumerate accounts, or replay stale refresh tokens by repeatedly calling the credential-verification and account-registration endpoints. The system limits how many such attempts a single origin can make in a given period.

**Why this priority**: These endpoints directly gate account access; unrestricted attempts enable credential stuffing and account enumeration. Equal priority to Story 1 because both close the two "front doors" that currently have no abuse protection.

**Independent Test**: Can be fully tested by repeatedly submitting login/registration/refresh requests from one origin and confirming the system starts refusing them after the allowed count, independent of whether the submitted credentials are valid.

**Acceptance Scenarios**:

1. **Given** a client submitting login attempts at a normal pace, **When** each attempt is within the allowed count, **Then** the system evaluates each one normally (accepting or rejecting based on credential validity, not on rate).
2. **Given** a client that has exceeded the allowed number of attempts in the current window, **When** it submits another attempt (valid or invalid credentials), **Then** the system refuses it as rate-limited before evaluating the credentials.
3. **Given** a successful login, **When** the same client continues to operate normally afterward, **Then** it is not penalized for its earlier attempts once the window has elapsed.

---

### User Story 3 - Bursts on costly authenticated features are smoothed out (Priority: P2)

A single signed-in user or guest sends a rapid burst of requests to a high-cost feature (the AI chat feature, and search/autocomplete) well within their longer-term usage allowance but fast enough to strain shared resources. The system smooths the burst by limiting how many requests that identity can make in a short window, independent of any longer-term quota already in place.

**Why this priority**: Lower priority than Stories 1-2 because these endpoints already require a valid identity (guest or account), which is a meaningful deterrent on its own, and the chat feature already has a separate longer-term usage allowance. This story closes the remaining gap: nothing today stops a burst within that longer-term allowance.

**Independent Test**: Can be fully tested by having one authenticated/guest identity issue a rapid burst of requests to the chat feature or to search, and confirming excess requests within the short window are refused as rate-limited while the identity's longer-term allowance is left untouched.

**Acceptance Scenarios**:

1. **Given** a signed-in user with remaining longer-term usage allowance, **When** they send requests to the chat feature faster than the short-window limit allows, **Then** the excess requests are refused as rate-limited even though their longer-term allowance is not exhausted.
2. **Given** a guest or signed-in user issuing search/autocomplete queries, **When** the pace exceeds the allowed short-window count, **Then** the excess requests are refused as rate-limited.
3. **Given** a user pacing their requests within the short-window limit, **When** they use the chat or search feature normally, **Then** they never encounter a rate-limit refusal.

---

### User Story 4 - Frontend API types are generated from the backend contract (Priority: P1)

A developer changes a backend API's request or response shape. Instead of separately, manually updating a hand-written type definition on the frontend (and risking forgetting to, or getting it subtly wrong), the frontend's type definitions are produced directly from the backend's current API contract.

**Why this priority**: This is the core value of the codegen effort — it removes the manual, error-prone step that causes today's type drift. Without this, nothing else in the codegen effort matters.

**Independent Test**: Can be fully tested by changing a backend endpoint's response shape, regenerating the frontend's type definitions, and confirming the change is reflected without any hand edits to the generated output; and separately, confirming existing frontend code that consumes the API still compiles/typechecks against the freshly generated types.

**Acceptance Scenarios**:

1. **Given** a backend endpoint with a defined request/response contract, **When** the frontend's type definitions are generated, **Then** the generated types accurately reflect that contract's field names, shapes, and optionality.
2. **Given** a backend response shape changes (field added, removed, renamed, or its optionality changed), **When** the frontend's type definitions are regenerated, **Then** the change appears in the generated output without a developer manually editing it.
3. **Given** the frontend's existing API-calling code, **When** it is switched to use the generated types in place of the current hand-written ones, **Then** it continues to compile and behave the same for every endpoint whose contract is fully defined.

---

### User Story 5 - Drift between backend contract and frontend types is caught automatically (Priority: P2)

A developer changes a backend API's contract but forgets to regenerate the frontend's type definitions before submitting their change for review. The system catches this automatically instead of letting the mismatch reach production.

**Why this priority**: Generation alone (Story 4) only helps if it's actually re-run; this story is what prevents the exact failure mode (silent drift) that motivated this feature in the first place. Slightly lower priority than Story 4 because it depends on generation already existing.

**Independent Test**: Can be fully tested by changing a backend contract, deliberately skipping regeneration, and confirming the normal change-submission process flags the mismatch before it can be merged.

**Acceptance Scenarios**:

1. **Given** a backend contract change with the frontend's generated types left stale, **When** the change is submitted for review, **Then** the mismatch is flagged automatically.
2. **Given** a backend contract change with the frontend's generated types correctly regenerated and committed alongside it, **When** the change is submitted for review, **Then** no mismatch is flagged.

---

### Edge Cases

- What happens when the shared store used to track and enforce rate limits is temporarily unavailable? (Assumption below: the system fails open — requests are allowed through — rather than blocking all traffic, to avoid an infrastructure hiccup taking down the whole product.)
- What happens when many distinct legitimate users share a single origin (e.g., an office or campus network) and collectively approach an origin-based limit meant for one actor? Their requests may be refused even though no single user is abusing the system — this is an accepted trade-off for the anonymous-endpoint stories (1-2), where no better identity signal is available.
- What happens when a rate-limited client retries immediately instead of waiting? The refusal response must make the retry-after guidance clear enough that well-behaved clients back off; the system is not required to prevent a misbehaving client from retrying immediately (it will simply keep being refused).
- What happens when a backend endpoint's request or response is not (yet) fully described by a contract? It is out of scope for automatic type generation until its contract is defined; existing hand-written types remain in place for it until then.
- What happens when regenerating frontend types would change a type in a way that breaks existing frontend code (e.g., a field is removed)? This must surface as a normal type-check failure the developer has to resolve, not a silent runtime break.

## Requirements *(mandatory)*

### Functional Requirements

**Rate limiting**

- **FR-001**: System MUST limit, per originating client, how many new anonymous/guest access credentials can be issued within a rolling time window.
- **FR-002**: System MUST limit, per originating client, how many login, registration, and token-refresh attempts can be made within a rolling time window, evaluated before the submitted credentials themselves are checked.
- **FR-003**: System MUST limit, per authenticated or guest identity, how many chat-feature requests can be made within a short rolling window, independently of that identity's existing longer-term usage allowance.
- **FR-004**: System MUST limit, per authenticated or guest identity, how many search and autocomplete requests can be made within a rolling window.
- **FR-005**: When a request is refused for exceeding a limit, the system MUST return a response that a caller (human or automated) can distinguish from other kinds of failures, and that indicates when the caller may retry.
- **FR-006**: Rate limits MUST be enforced consistently regardless of which running instance of the service handles a given request — a client cannot gain extra allowance by having its requests land on different instances.
- **FR-007**: Rate-limit enforcement MUST NOT alter the outcome of a request that stays within its limit (a compliant client sees no behavior change beyond the existing endpoint behavior).
- **FR-008**: System MUST allow each protected capability (guest-credential issuance, login/registration/refresh, chat, search) to have its own independently tunable limit and time window.

**Frontend type generation**

- **FR-009**: System MUST produce the frontend's API request/response type definitions from the backend's current, authoritative API contract, for every endpoint whose contract is fully defined.
- **FR-010**: Regenerating the frontend's type definitions from an unchanged backend contract MUST produce no differences (regeneration is deterministic/idempotent).
- **FR-011**: The frontend's existing API-calling code MUST be updated to consume the generated type definitions in place of the hand-written ones they replace, for every endpoint covered by generation.
- **FR-012**: The normal process for submitting a change MUST detect and flag the case where a backend contract change is submitted without a corresponding regeneration of the frontend's type definitions.
- **FR-013**: System MUST identify which backend endpoints are not yet covered by generation (because their contract is not fully defined) so they can be tracked as follow-up work rather than silently staying unprotected from drift.

### Key Entities

- **Rate Limit Policy**: A named rule protecting one capability (e.g., guest-credential issuance, login, chat, search); defines what identity dimension it keys on (originating client vs. authenticated/guest identity), the allowed request count, and the time window.
- **Rate Limit Refusal**: The outcome produced when a request is refused for exceeding its policy's allowance; carries enough information for the caller to know it was rate-limited and when to retry.
- **API Contract**: The authoritative, current description of a backend endpoint's request and response shape, maintained on the backend side.
- **Generated Frontend Type Definitions**: The frontend-side artifact derived from the API Contract, consumed by the frontend's existing API-calling code in place of hand-written equivalents.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: An automated test issuing a rapid burst of anonymous credential requests from a single origin has fewer than 100% of that burst succeed, with the excess clearly refused as rate-limited, while a legitimate client using the product at a normal pace never experiences a rate-limit refusal.
- **SC-002**: An automated test issuing a rapid burst of login/registration/refresh attempts from a single origin has the excess refused as rate-limited, without changing the outcome for any attempt within the allowed count.
- **SC-003**: A signed-in or guest user chatting or searching at a normal, human pace never encounters a rate-limit refusal; a scripted rapid-fire burst from the same identity does.
- **SC-004**: 100% of endpoints with a fully defined backend contract have frontend type definitions produced from that contract rather than hand-written.
- **SC-005**: When a backend contract changes, the corresponding frontend type definitions can be brought up to date without any developer manually retyping the changed fields.
- **SC-006**: A backend contract change submitted without regenerating the frontend's type definitions is caught before it reaches production, on every occurrence during normal review, not just when someone happens to notice.

## Assumptions

- "Originating client" for the not-yet-authenticated endpoints (guest-credential issuance, login, registration, refresh) defaults to the caller's network origin, since no stronger identity signal exists before a credential has been issued.
- For already-authenticated or already-guest-identified endpoints (chat, search), the identity used for limiting is the caller's account or guest identity rather than network origin, since that signal is available and more precise.
- Exact request-count and time-window thresholds are tunable operational parameters, not fixed by this specification; reasonable starting values are chosen based on normal usage patterns observed today and refined afterward.
- If the store used to track rate-limit counts becomes unavailable, the system fails open (requests are allowed through) rather than blocking all traffic — availability of the core product takes priority over throttling during an infrastructure outage.
- Administrator-only endpoints are out of scope for this feature; they are restricted to a small, trusted user base and are not currently showing signs of abuse.
- Frontend type generation covers request/response shape only; it does not generate or replace the frontend's existing request-sending logic (retries, authentication headers, error handling), which continues to work as it does today.
- All of the frontend's existing hand-written API type definitions are migrated to generated ones as part of this feature, rather than only applying generation to future endpoints, since leaving old ones hand-written would preserve the exact drift risk this feature exists to remove.
- Endpoints whose backend contract is not yet fully defined are explicitly tracked as follow-up work rather than blocking this feature; this feature does not require fully defining every such contract as a prerequisite.
