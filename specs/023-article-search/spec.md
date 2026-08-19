# Feature Specification: Article Search & Autocomplete

**Feature Branch**: `023-article-search`

**Created**: 2026-08-15

**Status**: Draft

**Input**: User description: "我想要新增一個新的功能，那就是搜尋功能。具體來說，是要在 frontend/app/articles/page.tsx 中新增一個 search bar，當使用者在這個 search bar 上面輸入文字時，還要能夠觸發 auto-complete。為此，主要需要新增的功能為：1. Redis 與 models/ 裡面需要新增一個 prefix tree（但其實不是只有 prefix，所以可能要包含所有的 occurrence）2. src/entrypoints/cli/main.py 中要新增一個 stage 是去更新那個 tree（re-construct 而不是 append/update 可能會比較簡單）3. backend/ 中要去實作 autocomplete 以及 search 的端點與服務，search 的話因為 alembic/versions/21_add_vectors_schema_and_article_chunks.py 裡面應該是已經有 sparse vector 可以做 keyword-based 的資料查詢，不確定有沒有需要額外引用新的 tech stack 如 opensearch 之類的。而且 autocomplete 對於 response time 非常地要求，所以可能會需要在 Redis 上面指定一個 database index 專門 for 這個 prefix node 的 key-value cache 的形式。4. frontend 的部分需要實作 debounce 以節制 autocomplete API 的輸出，至於 search 後的頁面是否要用一個新的 UI 可以再討論。"

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Keyword search across articles (Priority: P1)

As a visitor browsing the articles list, I want to type a keyword into a search bar and get back a list of matching articles, so that I can find relevant content without manually scrolling or filtering through the full article list.

**Why this priority**: This is the core value of the feature — everything else (autocomplete, debouncing) exists to help the user arrive at a good search query faster. Without working search, there is nothing to accelerate.

**Independent Test**: Can be fully tested by typing a keyword that appears in one or more article titles/content and submitting the search, then confirming the returned results actually contain that keyword and irrelevant articles are excluded.

**Acceptance Scenarios**:

1. **Given** the articles page is loaded, **When** the user types a keyword into the search bar and submits it, **Then** the system returns articles whose title or content match the keyword, ranked by relevance.
2. **Given** a search query that matches no articles, **When** the user submits it, **Then** the system clearly indicates no results were found, without showing an error state.
3. **Given** a user has run a search, **When** they clear the search bar, **Then** the article list returns to its normal (unfiltered) browsing state.

---

### User Story 2 - Autocomplete suggestions while typing (Priority: P2)

As a visitor typing into the search bar, I want to see suggested terms drawn from real article content as I type, so that I can quickly discover the right query without knowing the exact wording used in the articles.

**Why this priority**: Autocomplete is a usability accelerator on top of P1's search — it reduces mistyped or zero-result queries by steering the user toward terms that actually occur in the corpus. It depends on search existing but is not required to deliver the baseline search value.

**Independent Test**: Can be fully tested by typing a partial term into the search bar and confirming that a list of suggested terms actually present in article content appears within the target response time, and that selecting a suggestion runs a search for that term.

**Acceptance Scenarios**:

1. **Given** the user has typed at least the minimum number of characters into the search bar, **When** matching terms exist in the article corpus, **Then** a dropdown of suggested terms appears below the search bar.
2. **Given** suggestions are showing, **When** the user selects one, **Then** the system immediately runs a search using the selected term and closes the suggestion dropdown.
3. **Given** the user keeps typing quickly, **When** they pause, **Then** only the suggestions for the final typed text are requested and shown (no flicker from outdated in-flight requests).
4. **Given** no article content matches the typed characters, **When** suggestions are requested, **Then** the dropdown shows an empty/no-suggestions state rather than stale or incorrect terms.

---

### User Story 3 - Fast, responsive typing experience (Priority: P3)

As a visitor typing quickly into the search bar, I want the interface to stay responsive and not flood the backend with a request per keystroke, so that autocomplete feels instant and doesn't degrade the experience for other users.

**Why this priority**: This is a refinement of P2's usability — the feature is functional without it, but under real typing speed an unthrottled implementation would feel laggy and waste backend/cache capacity.

**Independent Test**: Can be fully tested by typing a multi-character query at normal typing speed and confirming via network inspection that autocomplete requests are throttled (not one per keystroke) while the final suggestion list still reflects the fully typed text.

**Acceptance Scenarios**:

1. **Given** the user is typing continuously, **When** each keystroke occurs, **Then** the system waits for a short pause in typing before requesting new suggestions.
2. **Given** the user types and then immediately deletes characters back to a previous state, **When** suggestions are requested, **Then** the system does not display suggestions for intermediate states the user has already moved past.

---

### Edge Cases

- What happens when the search query contains only whitespace, punctuation, or is empty? System should not run a search or show suggestions.
- What happens when the underlying suggestion/search data is being rebuilt (see FR-008) and is briefly unavailable? System should degrade gracefully (e.g. fall back to search-only, no autocomplete) rather than error out.
- How does the system handle very short queries (1 character) that would match a huge number of terms? Suggestion results should be capped/ranked rather than returning everything.
- How does the system handle special characters, non-Latin scripts (e.g. Traditional Chinese), or mixed-language queries, given articles are scraped from varied sources and may already exist in multiple languages via the translation pipeline?
- What happens if a user submits a search while a previous search for a different query is still in flight? The most recently submitted query's results should be the ones displayed.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The articles page MUST provide a visible search bar that accepts free-text keyword input.
- **FR-002**: The system MUST return a list of articles matching a submitted search query, ranked by relevance to the query.
- **FR-003**: The system MUST show a clear "no results" state when a search query matches no articles.
- **FR-004**: The system MUST show autocomplete suggestions as the user types, drawn from terms that actually occur in article content (not merely a static/predefined term list), so suggestions reflect the real corpus.
- **FR-005**: The system MUST throttle (debounce) autocomplete requests so that not every keystroke triggers a new request.
- **FR-006**: The system MUST discard/ignore stale autocomplete or search responses that no longer correspond to the user's current input, so results never regress to an outdated query.
- **FR-007**: Selecting an autocomplete suggestion MUST run a search using that suggestion's term.
- **FR-008**: The set of searchable/suggestible terms MUST be refreshed as part of the existing scheduled scraper pipeline's next run — newly scraped articles become searchable/suggestible on the next scheduled scrape-and-refresh cycle, with no separate real-time update mechanism required.
- **FR-009**: Search results MUST be scoped to the visitor's currently selected topic, consistent with how the rest of the articles list (filters, pagination) is already topic-scoped.
- **FR-010**: The system MUST clear the applied search when the user empties the search bar, returning to the normal unfiltered/filtered-by-other-controls article list.
- **FR-011**: Autocomplete suggestions MUST respond within 300ms under normal load, with a target of under 100ms where achievable, so the interaction feels instantaneous while typing.
- **FR-012**: Both guest and logged-in visitors MUST be able to use search and autocomplete, consistent with the existing `require_any_token` access level applied to the rest of the articles list.

### Key Entities

- **Search Query**: The free-text term(s) a visitor submits; scoped to a topic; produces a ranked list of matching articles.
- **Autocomplete Suggestion**: A term derived from real article content (title/body) that a visitor can select to run a search; associated with how frequently/where it occurs across articles, not just which articles it prefix-matches.
- **Article** (existing entity): The content being searched and matched against queries/suggestions.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Visitors can locate a specific known article via search in under 10 seconds, compared to manually scrolling/filtering.
- **SC-002**: Autocomplete suggestions appear within 300ms of the user pausing input (target under 100ms), without visibly interrupting or lagging the typing experience.
- **SC-003**: At least 90% of submitted searches for terms that exist in the article corpus return at least one relevant result.
- **SC-004**: The number of autocomplete requests sent while typing a typical query is substantially lower than one request per keystroke (debouncing is observably effective).
- **SC-005**: Newly scraped articles become findable via search and suggestible via autocomplete within one scheduled refresh cycle of being added.

## Assumptions

- The search bar is added to the existing articles page (`frontend/app/articles/page.tsx` / `articles-page-content.tsx`) rather than a dedicated new page; whether search results reuse the existing article list UI or introduce new result UI is a presentation-layer decision left to the planning phase, not a scope change here.
- "Search" in this feature combines keyword-shaped and semantic/similarity matching (hybrid sparse+dense retrieval, merged via Reciprocal Rank Fusion — decided during planning; see `research.md`'s "Decision: Hybrid sparse + dense search via RRF"); reuse of existing vector infrastructure (already-populated sparse/dense embeddings on `vectors.article_chunks`) is preferred over introducing new search infrastructure like ElasticSearch/OpenSearch.
- Autocomplete suggestions are single terms or short phrases pulled from actual article occurrences, not a fixed/curated dictionary — this is why the underlying term index must be rebuilt as new articles arrive rather than staying static.
- Rebuilding the term index is an acceptable strategy (versus incremental updates) given the existing scraper pipeline already runs on a recurring schedule; this trades some data freshness for simplicity — confirmed acceptable per FR-008 (next scheduled cycle, no separate real-time path).
- Both guest and authenticated visitors are in scope, matching the existing access level of the articles list itself.
- The 300ms (target 100ms) autocomplete latency target in FR-011 applies to the suggestion lookup itself under normal load; it does not cover network conditions outside the system's control (e.g. a visitor on a very slow connection).
- Multi-language content (English + Traditional Chinese via the existing translation pipeline) is in scope for search/autocomplete matching, but exact cross-language matching behavior (e.g. whether an English query surfaces a Chinese-translated article) is left to planning.
