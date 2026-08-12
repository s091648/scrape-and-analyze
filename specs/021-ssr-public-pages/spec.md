# Feature Specification: SSR Conversion for Public Pages (LCP Fix)

**Feature Branch**: `020-redis-caching-layer` (reused — this spec does not open a new branch; see Assumptions)

**Created**: 2026-08-07

**Status**: Draft

**Input**: User description: "Redis caching (020) sped up backend query responses but did not improve LCP on `/` (home) and `/articles`, because both pages are client-only with zero server-rendered data fetching — the browser has to download/parse/execute the JS bundle, hydrate, then fire two sequential API requests (topics, then articles) before the first meaningful content appears. Convert these pages to Server Components so first-paint data is fetched server-side and shipped with the initial HTML, actually cashing in on the caching work done in 020."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - First-time visitor sees articles immediately (Priority: P1)

A visitor (logged in or anonymous/guest) opens the articles page directly (e.g. from a shared link or search engine result) on a fresh browser session with no cached JS or local state. Today they see a blank/skeleton page until the JS bundle loads, hydrates, and two sequential API calls resolve. They should instead see the article list rendered in the initial HTML response, before any client-side JavaScript has run.

**Why this priority**: This is the core LCP problem — the slowest, most common real-world path (first visit, cold cache) is exactly the one Redis caching (020) failed to speed up.

**Independent Test**: Load `/articles` with JavaScript disabled (or throttled/blocked in a network trace) and confirm article cards are present in the raw HTML response, not just an empty shell.

**Acceptance Scenarios**:

1. **Given** a visitor with no session and no local storage, **When** they navigate to `/articles`, **Then** the server response HTML already contains the rendered article list for the default topic/filter state.
2. **Given** the same visitor, **When** the page finishes hydrating, **Then** no duplicate fetch of the same default article list fires (the client reuses the server-fetched data instead of re-requesting it).
3. **Given** the same visitor, **When** they view `/` (home), **Then** the equivalent server-rendered first-paint behavior applies there too.

---

### User Story 2 - Returning visitor sees their own topic and language on first paint (Priority: P2)

A visitor who previously selected a topic (e.g. "AI Safety") and a non-default display language returns to `/articles`. Today the server-rendered shell would default to "no topic" / a guessed language and only reflect the visitor's real choice after client-side hydration corrects it, causing a visible content swap. With their preference readable by the server (via cookie), the initial HTML should already reflect their chosen topic and language.

**Why this priority**: Without this, converting to SSR fixes raw load speed but introduces a visible "flash of wrong content" regression for returning visitors, which would be a net UX downgrade for a meaningful segment of traffic.

**Independent Test**: Set the topic-preference cookie to a non-default topic, request `/articles` fresh (no JS), and confirm the server-rendered HTML reflects that topic's articles, not the default topic's.

**Acceptance Scenarios**:

1. **Given** a visitor whose topic-preference cookie is set to topic X, **When** they load `/articles`, **Then** the initial HTML shows articles filtered to topic X.
2. **Given** a visitor with no topic-preference cookie set (first-ever visit), **When** they load `/articles`, **Then** the initial HTML shows a sensible default (no-topic-filter or first active topic — see Assumptions) and the client does not need to re-fetch to correct it.
3. **Given** a visitor changes their topic selection while on the page, **When** the change is applied, **Then** subsequent navigations/reloads reflect the new topic on first paint (the preference cookie is updated).

---

### User Story 3 - Anonymous visitor sees the same paywalled placeholder instantly, with no content leak (Priority: P1)

An anonymous visitor — no session, and (whether or not they've previously clicked "Continue as Guest" elsewhere in the app) with no server-visible signal of that choice — loads `/articles` or `/`. **Revised during implementation** (2026-08-08): the original framing of this story assumed the server should fetch and server-render the same real content a logged-in visitor sees. Implementation discovered that today's client-side code deliberately withholds real content from exactly this visitor type until they explicitly opt into "Continue as Guest" — a choice recorded only in `sessionStorage`, which never reaches the server. Server-rendering real content for this visitor would silently bypass that existing paywall gate. The corrected behavior: the server never attempts to fetch real data for a visitor with no session — it passes no initial data at all, so this visitor's experience is **completely unchanged from today**: the paywall/placeholder decision itself is computed client-side from `useSession()`'s status (`unauthenticated` vs `loading` vs `authenticated`), which cannot resolve before hydration regardless of SSR, so a pre-hydration/JS-disabled view of the page still shows the same loading state it always has. This feature deliberately does not attempt to speed up that case; it only ensures it isn't made worse (no content leak, no wasted backend call). Once hydrated, the page's existing client-side logic (checking real auth session and the `sessionStorage` guest-mode flag) behaves completely unchanged — including transparently fetching real content client-side the moment a visitor who has already opted into guest mode hydrates.

**Why this priority**: Anonymous, non-authenticated traffic is the majority of first-time visits, and this story is what prevents the SSR conversion from becoming a content-exposure regression for that traffic — without it, "just fetch real data whenever there's no session" (the simplest possible implementation) would silently remove an existing, deliberate business rule.

**Independent Test**: Load `/articles` in a browser session with no prior cookies/local storage/session storage (simulating a true first-time anonymous visitor) and confirm the server-rendered HTML already contains the placeholder/paywall state (not a blank shell, and not real article content).

**Acceptance Scenarios**:

1. **Given** a browser with no auth state at all, **When** it requests `/articles`, **Then** the server does not attempt any real backend fetch on that visitor's behalf — the response HTML contains the same pre-hydration loading state shown today (the placeholder/paywall CTA itself only appears once client-side `useSession()` resolves, which requires hydration either way, unaffected by SSR).
2. **Given** that same visitor has, in a prior interaction, set their browser's `sessionStorage` guest-mode flag (clicked "Continue as Guest"), **When** the page hydrates, **Then** the existing client-side fetch for real content fires exactly as it does today — the SSR layer neither blocks nor duplicates it.
3. **Given** the page has hydrated for any anonymous visitor, **When** they interact with the page (change page, filter, or click "Continue as Guest"), **Then** those interactions use the existing client-side guest token flow, completely independent of and unaffected by SSR.

---

### User Story 4 - Graph and tags views also render server-side (Priority: P3)

A visitor opens the analysis graph (`/graph`) or the tags view (`/tags`) directly. Today, like `/` and `/articles`, both are client-only pages with the same hydrate-then-fetch delay pattern. They should get the same server-rendered first-paint treatment.

**Why this priority**: Lower priority than `/` and `/articles` (User Stories 1–3) since those two carry the bulk of first-time/entry traffic, but included in this spec rather than deferred, since the underlying mechanism (server-side data fetch, guest credential, topic/language cookie resolution) is identical and reusing it here is low incremental cost once built for the primary pages.

**Independent Test**: Load `/graph` and `/tags` with JavaScript disabled and confirm each renders real content (graph data / tag groups) in the raw HTML response, not an empty shell.

**Acceptance Scenarios**:

1. **Given** a visitor (guest or logged-in) with no prior interaction, **When** they load `/graph`, **Then** the initial HTML already contains the rendered graph data for the default topic.
2. **Given** the same conditions, **When** they load `/tags`, **Then** the initial HTML already contains the rendered tag groups for the default topic.
3. **Given** either page has hydrated, **When** hydration completes, **Then** no duplicate fetch of the same default-state data fires.

---

### Edge Cases

- What happens when the backend is unreachable or errors out during the server-side data fetch? (The page must not crash/500 — needs a defined fallback, e.g. render an empty/error state that the client can still recover from post-hydration.)
- What happens when the server-obtained guest credential (for a first-time SSR render) itself fails to be issued (e.g. `POST /auth/guest` errors)? Same fallback question as above.
- What happens when a visitor's topic-preference cookie references a topic that has since been deleted or deactivated by an admin? *(Resolved during implementation, post-launch performance follow-up — see research.md's root-cause-1 optimization: the server now trusts a present cookie directly instead of validating it against `GET /topics` first, to avoid that round trip for every returning visitor. A stale cookie causes that one render's data fetch to come back empty rather than falling back to a default topic; the client's own `topic-provider.tsx` validation corrects both the in-memory state and the cookie on its next run, so this self-heals within one visit.)*
- What happens when the article list page is requested with query-string filters/pagination that differ from the cached default (e.g. `?page=3` or a search term) — does the server-rendered fetch still apply, and does it interact correctly with the 020 cache-aside layer (which only eager-warms default-parameter reads; non-default combinations fall back to lazy cache population, same as today)?
- What happens on repeated/rapid navigation between `/` and `/articles` for the same visitor — should the server-obtained guest credential from one render be reused for the next, or is a fresh one always fetched? *(Resolved during implementation, post-launch performance follow-up: guest tokens are anonymous, not tied to any specific visitor, so the server now caches and reuses one guest token across **all** anonymous visitors' renders — not just repeated navigation by the same visitor — for as long as it remains valid, rather than issuing a fresh one per render. See research.md's root-cause-1 optimization.)*

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The home page (`/`) and articles page (`/articles`) MUST render their primary content (article cards / equivalent first-paint content) as part of the initial server-rendered HTML response for an authenticated visitor, not solely via client-side data fetching after hydration.
- **FR-002** *(revised during implementation — see User Story 3)*: For a visitor with no authentication session, the server MUST NOT fetch or server-render real first-paint content on that visitor's behalf. It MUST instead render the same placeholder/paywall state the existing client-side code already shows for that visitor, so the paywall gate (today enforced by a `sessionStorage`-only "Continue as Guest" flag the server cannot see) is preserved exactly as-is.
- **FR-003**: After the page hydrates in the browser, the client MUST NOT re-fetch the exact same first-paint data the server already rendered for an authenticated visitor (no duplicate default-state request on mount). This does not apply to anonymous visitors, whose client-side fetch (gated on the existing guest-mode check) is unaffected by SSR per FR-002.
- **FR-004**: The client MUST continue to use its existing browser-based guest/auth token flow for all post-hydration interactions (pagination, filtering, topic switching, "Continue as Guest," etc.), completely unaffected by SSR.
- **FR-005**: A visitor's previously selected topic MUST be readable by the server at render time (i.e., available via cookie, not only `localStorage`) so the first-rendered HTML reflects their actual topic selection rather than a default that gets corrected after hydration.
- **FR-006**: Changing the selected topic MUST update the server-readable preference (cookie) so subsequent page loads reflect the new choice on first paint.
- **FR-007**: If the server-side data fetch for first-paint content fails (backend error, credential-issuance failure, timeout, etc.), the page MUST still render without crashing, and MUST remain recoverable by the client after hydration (e.g. falling back to the existing client-side fetch behavior).
- **FR-008**: The system MUST resolve the visitor's display language server-side at render time — including on a visitor's true first-ever page load, with no prior stored preference — by performing IP-based geolocation resolution during server rendering (mirroring the resolution logic `/api/languages` already performs client-side), rather than deferring to a client-written cookie/localStorage value for that first render.
- **FR-009**: `/graph` and `/tags` MUST also be converted to server-rendered first paint, using the same server-side data-fetching approach and the same anonymous-visitor paywall preservation as `/` and `/articles` (FR-001–FR-004). Each currently stays a single-file `page.tsx` per this codebase's convention for pages that don't need the `page.tsx`/`xxx-page-content.tsx` split; converting to SSR requires that split (an async server `page.tsx` plus a sibling client content component), consistent with the pattern used for `/` and `/articles`.
- **FR-010**: The graph view's data fetch (`/analyses/graph`) and the tags view's data fetch (`/tag-groups`) MUST follow the same first-paint-on-server, no-duplicate-client-refetch, anonymous-visitor-paywall-preserving rules as FR-001–FR-004.

### Key Entities

- **Topic preference**: the visitor's selected topic/category filter, currently held in `localStorage`, to be made server-readable (cookie) per FR-005/FR-006. Not a new backend entity — a client-side preference relocation.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Largest Contentful Paint (LCP) for a first-time, cold-cache visit to `/` and `/articles` improves to within the "Good" Core Web Vitals threshold (under 2.5s), measured against a production-parity build (not a dev server).
- **SC-002** *(revised — see User Story 3)*: The primary content of `/articles` and `/` is present in the raw server response HTML (verifiable with JavaScript disabled) for authenticated visitors. For anonymous visitors, the raw server response HTML never contains real article/report data (no content leak) — it contains the same pre-hydration loading state shown today, unchanged.
- **SC-003**: Returning **authenticated** visitors with a previously selected topic and language see that same topic/language reflected in the very first rendered frame — no visible content swap after hydration — in at least 95% of repeat visits under normal conditions. (Anonymous visitors, including ones who have opted into guest mode, are unaffected by SSR per FR-002/User Story 3 — their experience is unchanged from today.)
- **SC-004**: No increase in duplicate network requests on page load compared to today's baseline — the total number of first-paint-content API calls per page load does not exceed one (server-side), even though the client previously made its own equivalent request.

## Assumptions

- This spec is developed on the existing `020-redis-caching-layer` git branch, continuing directly from the completed Redis caching work, per explicit user instruction — no new branch is created for this feature; only a new spec directory (this one) is used to keep the two features' documentation separate.
- Per FR-002/User Story 3, this feature does **not** call `POST /auth/guest` (or any other credential-issuing endpoint) on an anonymous visitor's behalf — SSR only fetches real data when a NextAuth session already exists. This is narrower than this spec's original intent (see User Story 3's revision note) but was corrected after discovering the existing client-side paywall/guest-mode gate has no server-visible signal to respect otherwise.
- A longer-term redesign of guest identity (e.g., giving guests a real row/role in the user table so guest mode shares the standard auth framework instead of being special-cased) remains out of scope for this spec and is tracked separately as a future consideration — it is *also* the kind of change that could eventually give the server a legitimate, real signal for "this visitor has opted into guest mode," which today's `sessionStorage`-only flag cannot provide.
- The server-side first-paint fetch is expected to typically be served from the cache-aside layer built in 020 (`CacheWarmupHandler` eager-warms exactly the default-parameter reads this SSR conversion will request), since default topic/language/pagination combinations are the ones proactively kept warm after every scrape; non-default combinations (specific search filters, deep pagination, etc.) fall back to the existing lazy cache-aside behavior, same as any other request today.
- A visitor with no topic-preference cookie yet (true first visit) is treated as having no topic filter or the first active topic selected by default — final choice depends on resolving FR-005's cookie-write timing, but either way the server-rendered default must not require a hydration-time correction for a *first-time* visitor (only *returning* visitors with an actual stored preference need the cookie to be authoritative).
- Server-side language resolution (FR-008) reuses the existing IP-based geolocation approach (already used by `/api/languages` and by `require_any_token`'s GeoIP2 resolution elsewhere in the backend) rather than introducing a new resolution mechanism; the server-side render performs this resolution directly from the incoming request rather than round-tripping through the `/api/languages` endpoint.
- `/graph` and `/tags` (FR-009, FR-010) are included in this spec's scope rather than deferred to a follow-up, since they share the exact same conversion mechanism as `/` and `/articles`.
