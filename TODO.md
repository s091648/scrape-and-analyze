# TODO

## Discover/Fetch HTTP client injection is inconsistent

**Where**: `src/infrastructure/collection/`

**Problem**: The discover-side API/feed clients and the fetch-side content-extraction
helpers handle their `HttpClient` dependency differently, with no shared protocol
between them.

- **Discover-side clients are DI-friendly** — `RssClient`, `ArxivClient`,
  `SemanticScholarClient`, `OpenAlexClient` (`src/infrastructure/collection/clients/`)
  all take `http_client=None` in `__init__`, fall back to `get_default_client()` only
  when not given one, and store it as `self._http`. This is what lets
  `ConcreteScraperFactory.create_for()` (`src/infrastructure/collection/scrapers/scraper_factory.py:73,86,99`)
  inject a `.with_skip_retry_status(frozenset({429}))` variant per source type
  (arxiv/semantic_scholar/openalex) at scraper-construction time.

- **Fetch-side helpers are hardwired to the global singleton** — `PdfParser.parse()`
  (`src/infrastructure/collection/parsers/pdf_parser.py:33`), `HtmlArticleParser.fetch_and_parse()`
  (`src/infrastructure/collection/parsers/html_parser.py:52`), and `BlogScraper.discover()`/`.fetch()`
  (`src/infrastructure/collection/scrapers/blog_scraper.py:43,66`) all call
  `get_default_client()` directly inline, with no constructor parameter and nothing
  stored as an attribute. There is no way to inject a customized `HttpClient`
  (different retry/skip-status behavior, or a mock for unit tests) into any of them.

**Concrete effect**: for arXiv specifically, discover-time API calls
(`ArxivClient.fetch_entries()`) skip retrying on 429, but fetch-time PDF downloads
(`PdfParser.parse()`) go through the plain default client and *do* retry 429 with
the normal exponential backoff (`src/infrastructure/shared/http/retry.py`). This
asymmetry is currently harmless (no source has asked for customized fetch-time
retry behavior yet), but it's a real gap in the codebase's shape, not a deliberate
two-tier design.

**Why it hasn't mattered yet**: only 3 source types need 429-skip customization, and
that need has only ever shown up at discover time (querying an API's result list),
never at fetch time (downloading one PDF/HTML page) — so no one has added the
injection seam on the fetch side.

**Suggested fix, if/when fetch-side customization is ever needed**: give
`PdfParser`, `HtmlArticleParser`, and `BlogScraper` the same
`def __init__(self, http_client=None): ...` + `get_default_client()` fallback
pattern the discover-side clients already use, so both sides are DI-friendly and
individually mockable in unit tests. Low-cost, purely additive — not urgent while
nothing needs it.

**Related, deliberately NOT changing**: `HttpClient._retry_policy` is built
internally from scalar constructor params (`retry_max_attempts`, `skip_retry_status`)
via `make_retry_policy()` (`src/infrastructure/shared/http/retry.py`), unlike
`DomainRateLimiter`/`UserAgentPool` which are injected as pre-built objects. This is
intentional, not an inconsistency to fix: the rate limiter/UA pool carry persistent
cross-call, cross-thread state that must stay a single shared object for rate
limiting to work at all, whereas the retry policy is pure stateless behavior
(tenacity resets its internal state on every `for attempt in policy:` loop) — there's
no correctness reason to share one `tenacity.Retrying` instance across `HttpClient`
variants, and forcing constructors to accept a raw `tenacity.Retrying` would leak
that third-party library's API into every call site that wants to customize retry,
for no real benefit over the current two scalar knobs. Revisit only if a future
source needs retry customization beyond "skip these status codes" (e.g. a
fundamentally different backoff curve).

## `HttpClient` singleton: thread-safety caveats

**Where**: `src/infrastructure/shared/http/http_client.py`

`HttpClient` (via `get_default_client()`) is shared as one process-wide instance
across every discover/fetch worker thread. In the normal startup path this is
safe — `main.py:51` calls `init_default_client(HttpClient.build_default())` on the
main thread before any `ScrapeExecutor` worker thread is spawned, so the global is
already set before any concurrent access happens. Two smaller things worth noting,
neither currently causing a bug:

- **`get_default_client()`'s lazy-init fallback is not thread-safe**
  (`http_client.py:171-177`):
  ```python
  if _default_client is None:
      _default_client = HttpClient.build_default()
  ```
  No lock guards this check-then-set. If `init_default_client()` were ever skipped
  and multiple threads called `get_default_client()` concurrently as the first
  callers, they could race and each build their own `HttpClient` — each with its
  own independent `DomainRateLimiter`/`UserAgentPool` — silently breaking the
  "one shared rate limiter for the whole process" invariant (no crash, just
  effective rate limits multiplying by however many instances got created).
  Doesn't happen today because `main.py` always calls `init_default_client()`
  first, synchronously, before spawning any threads.

- **`HttpClient._proxy_enabled` is mutated without a lock**
  (`http_client.py:103,111`, flipped to `False` on `ProxyError`/407). Harmless in
  practice: it's a plain bool, only ever flips one-way (`True` → `False`, never
  back), and a race just means another thread might send one extra request through
  the now-disabled proxy before it also observes the flip — not a correctness bug,
  just worth knowing it's an unguarded shared mutable field on an otherwise
  carefully-locked object (contrast with `DomainRateLimiter`/`UserAgentPool`, which
  guard their per-domain dicts with `threading.Lock`).

No action needed unless `init_default_client()`'s call-before-any-thread ordering
ever becomes less certain (e.g. a new entrypoint that spawns executor threads
without going through `main.py`'s setup) — at that point, add a lock around the
lazy-init fallback.

## 429 handling has no accounting/circuit-breaker outside discover's arxiv/ss/openalex path

**Where**: `src/infrastructure/collection/executor/scrape_executor.py`,
`src/infrastructure/collection/scrapers/scraper_factory.py`

Only discover-time calls for arxiv/semantic_scholar/openalex get the "fast-fail +
proactively skip the rest of this host + get counted" treatment for 429. Every
other combination silently falls through to a slow, unaccounted failure:

- **Fetch never uses `with_skip_retry_status({429})`, for any source** — not even
  arxiv/semantic_scholar/openalex, whose own *discover*-time client explicitly skips
  429 retries for exactly this reason (`# arXiv 429 = IP-level ban; retrying only
  extends it`, `scraper_factory.py:72`). `PdfParser`/`HtmlArticleParser`/`BlogScraper`
  all reach `get_default_client()` directly (see the injection TODO above), so a 429
  during fetch — for the *same* host that discover just fast-failed on — runs the
  full ~4-attempt/240s exponential-backoff ladder before giving up. Same host, same
  kind of 429, two very different response times depending on which stage hit it.
- **`ScrapeExecutor`'s fetch worker loop has no equivalent of discover's
  `_rate_limit_tracker`/`on_discover_failed`** (`scrape_executor.py:180-249` vs.
  `:293-386`) — it never checks whether a host is already known-exhausted before
  popping its next `FetchTask`, and never marks one exhausted on failure. A host
  that's already tripped (via the shared `DomainRateLimiter`, see the rate-limiter
  discussion) still has every one of its remaining queued FetchTasks individually
  attempted and individually fail one by one, instead of being skipped in bulk —
  and none of that shows up in `exhausted_hosts`.
- **RSS/blog discover 429s get none of the arxiv/ss/openalex treatment either** —
  they're not wrapped in a typed `ProviderRateLimitedError`, so `DiscoverTask.execute()`'s
  generic `except Exception` catches them, logs `discover_failed`, and returns an
  empty job list. No host skip-ahead, no `exhausted_hosts` entry — same "invisible"
  shape as the fetch-side gap above.
- **A fetch failure of any kind — 429 or otherwise — is never recorded into
  `PipelineStats`/`ArticleOutcome`** at all (confirmed: `ArticleOutcome.FAILED` is
  only ever set in `ProcessScrapedArticleUseCase`, the downstream text stage). A
  `FetchTask` that returns `None` just vanishes from `results` with a log line and
  an ERROR-status span — `PipelineCompletedEvent`'s `failed` count and
  `rate_limited_hosts` never reflect it.

**Why it hasn't mattered yet**: same story as the injection TODO above — the 429
fast-fail/skip-ahead/accounting bundle was built specifically for discover's
arxiv/semantic_scholar/openalex API calls (where a 429 mid-run is common and cheap
to detect early), and nothing has needed the same treatment anywhere else yet.

**Suggested fix, if/when this needs to be consistent**: (a) generalize
`ScrapeExecutor`'s host-exhausted check + skip + `on_*_failed` accounting so the
fetch worker loop uses the same pattern discover's does; (b) decide deliberately
whether fetch-time downloads should also skip-retry on 429 per source (arxiv PDF
downloads share the same host/TOS as the arxiv API, so probably yes there at
least); (c) give fetch failures a `PipelineStats`/`ArticleOutcome`-equivalent
recording so they're visible in run-completion stats, not just logs. Not urgent —
no incident has surfaced from this gap yet.

## Article's commit is incidental — piggybacks on the metrics-upsert's commit, not an explicit decision by `ProcessScrapedArticleUseCase`

**Where**: `src/modules/collection/application/use_cases/process_scraped_article.py`,
`src/infrastructure/persistence/collection/article_metrics_async_repo_impl.py`,
`src/infrastructure/persistence/shared/article_async_repo_impl.py`

**This entry replaces two earlier, factually wrong versions of itself** — both
claimed `Article`/`Analysis` stay uncommitted until `NormalizeTagsUseCase`'s
final commit, and that a tag-normalization failure would roll back the
already-successful article + analysis too. That's **incorrect** — verified by
reading `analysis_async_repo_impl.py` and `article_metrics_async_repo_impl.py`
in full (the earlier versions had only skimmed `article_repo.save()` in
isolation and missed the very next call each use case actually makes):

- `AsyncSqlAlchemyAnalysisRepository.save()` (called by `AnalyzeArticleUseCase`)
  flushes the `Analysis` row, adds its English `AnalysesTranslation` row, **then
  commits** (`analysis_async_repo_impl.py:51-55`) — Analysis is durably
  committed the moment `AnalyzeArticleUseCase.execute()` returns success.
- `AsyncSqlAlchemyArticleMetricsRepository.upsert()` (called by
  `ProcessScrapedArticleUseCase.execute()` right after `article_repo.save()`'s
  flush-only insert, for every non-duplicate article — `article_metrics_repo`
  is always wired in production) executes its upsert statements **then commits**
  (`article_metrics_async_repo_impl.py:45`) — this commit lands on the *same*
  session, so it durably commits the just-flushed `Article` row too.

So in the normal path, both `Article` and `Analysis` are **already committed in
their own separate transactions** (SQLAlchemy autobegins a fresh transaction on
the same `AsyncSession` after each `commit()`) well before `NormalizeTagsUseCase`
ever runs. Its `rollback()` on failure only ever discards its own accumulated
tag/link/suggestion writes from that third transaction — exactly the scoped,
low-blast-radius behavior that was previously (wrongly) reported as missing.

**The one real, much narrower gap that remains**: `Article`'s durability is a
side effect of the metrics-upsert call succeeding, not something
`ProcessScrapedArticleUseCase` decides for itself. Two edge cases where this
matters: (a) if `article_metrics_repo` were ever not wired (it's `Optional` in
the constructor, just never `None` in current production wiring), `article_repo.save()`'s
`flush()` would never get an explicit commit at all in that code path; (b) the
`upsert()` call is wrapped in `try/except Exception: logger.warning(...)` in
`ProcessScrapedArticleUseCase.execute()` — if it throws *before* reaching its
own `commit()`, the exception is swallowed, `execute()` still returns
`(ArticleOutcome.NEW, saved)` as if nothing happened, and the `Article` row is
left merely flushed (not durably committed) with no error surfaced anywhere.

**Suggested fix, if ever revisited**: give `ProcessScrapedArticleUseCase` an
explicit commit of its own (e.g. via a repository `commit()` method, mirroring
`AsyncSqlAlchemyTagRepository`'s), independent of whether the metrics upsert
happens to run or succeed — makes `Article`'s durability an intentional
decision instead of a side effect of an unrelated call, and closes edge case
(b) above. Low priority: the happy path already behaves correctly today.

## `NormalizeTagsUseCase._process_tag()`'s `find_similar()` call fetches 5 candidates but only ever uses the best one

**Where**: `src/modules/intelligence/application/use_cases/normalize_tags.py`,
`src/infrastructure/persistence/intelligence/tag_repo_queries.py`

`find_similar_tags_stmt()` does `ORDER BY t.embedding <=> CAST(:vec AS vector) LIMIT 5`,
but `_process_tag()` only ever reads `similar[0]` (the best match) — the other
up to 4 rows returned are never used anywhere. Harmless (a handful of extra
rows from a query already scoped to one topic+group, not a real cost at
expected data volumes), but worth asking whether `LIMIT 5` was meant to support
a multi-candidate suggestion flow that never got built, or should just be
`LIMIT 1` to match what's actually consumed.

**Also worth noting while in this query**: `tags.embedding` has an HNSW index
(`idx_tags_embedding`, migration `17_add_vector_failed_task_and_auto_tag.py`)
built for approximate nearest-neighbor search, but it's a *global* index — it
has no awareness of the `topic_id`/`group_name` filter this query also applies.
At the tag counts one topic+group is expected to hold (dozens to low hundreds,
not millions), an exact scan of the filtered subset is almost certainly both
correct and fast enough, so this likely doesn't matter in practice — but it
means the HNSW index's approximate-search benefit may not actually be
exercised the way its presence might suggest. Not urgent, purely informational.

**Why it hasn't mattered yet**: neither point is a functional bug — found
during an architecture walkthrough of the tag-similarity query.

## `PipelineStats` lives under `use_cases/` despite not being a use case (or a DTO)

**Where**: `src/modules/collection/application/use_cases/pipeline_stats.py`,
`src/modules/collection/application/use_cases/article_outcome.py`,
`src/modules/intelligence/application/use_cases/analysis_result.py`

`ArticleOutcome` (a plain `Enum`) and `AnalysisResult` (a frozen dataclass) sit in
`use_cases/` alongside the use cases that own them — `AnalysisResult`'s docstring
says outright "Return value of AnalyzeArticleUseCase", and `ArticleOutcome` is
half of `ProcessScrapedArticleUseCase.execute()`'s return tuple. That placement
is defensible: CLAUDE.md's own Application-layer description groups "Use cases
..., event handlers, DTOs" as one layer, and each of these two types is a
tightly-coupled, single-use-case-owned return contract with exactly one
consumer — colocating a use case and its own result type avoids splitting a 1:1
pair across an extra `dto/`-style folder for no real benefit.

`PipelineStats` is the odd one out in the same directory: it's not a DTO at all
(it has behavior — `record()`, `record_partial_failure()`, its own
`threading.Lock`, `get_results()` — only its nested `SourceStats` is a pure
data holder), and it isn't owned by any single use case either — it's a
run-scoped, stateful collector shared across many different
handlers/use-cases for the whole pipeline run (`ArticleScrapedHandler`,
`ArticleProcessedHandler`'s downstream chain, `FailedTaskPersistenceHandler`,
etc. all write into the same instance). Structurally it reads more like a
small cross-cutting application *service* than "a use case" or "a use case's
own result type."

**Why it hasn't mattered yet**: purely an organizational/naming concern, not a
functional issue — found during an architecture walkthrough discussing where
DTOs belong, not from any bug.

**Suggested fix, if ever revisited**: move `PipelineStats`/`SourceStats` to a
more accurately-named location (e.g. an `application/services/` sibling
folder, if/when this layer grows enough call for one) — leave `ArticleOutcome`
and `AnalysisResult` where they are, they're correctly colocated with their
owning use case. Not urgent: `PipelineStats` is imported via
`use_cases/__init__.py` re-exports from enough call sites that moving it is a
mechanical but non-trivial import-path change, not worth doing on its own.

## Failure logging now lives entirely in the handler, not the use case — superseded an earlier, opposite convention

**Where**: `src/modules/collection/application/event_handlers/article_scraped_handler.py`,
`src/modules/intelligence/application/event_handlers/article_processed_handler.py`,
`src/modules/intelligence/application/event_handlers/tag_normalization_handler.py`,
`src/modules/collection/application/use_cases/process_scraped_article.py`,
`src/modules/intelligence/application/use_cases/analyze_article.py`,
`src/modules/intelligence/application/use_cases/normalize_tags.py`

**This entry replaces an earlier, now-superseded version of itself** — that
version held up `NormalizeTagsUseCase`/`TagNormalizationHandler` as the clean
model and stated the rule as "the use case logs failure detail (it has the raw
exception), the handler logs the success/completion milestone." The
error-handling unification described elsewhere in this codebase's history
(use cases raise instead of returning a failure-shaped Result; each handler
wraps its `use_case.execute()` call in one `try/except` that is the single
place converting *any* exception — anticipated or not — into a `*FailedEvent`)
flipped failure-logging ownership to the opposite layer:

- `AnalyzeArticleUseCase.execute()` no longer logs on failure at all (no more
  `llm_analysis_failed`/`analysis_save_failed`) — it just raises.
  `ArticleProcessedHandler`'s `except` branch now owns the single
  `logger.exception("article_analysis_failed", ..., error_type=...)` call.
- `ProcessScrapedArticleUseCase.execute()` no longer logs `article_save_failed`
  on a save failure — it raises. `ArticleScrapedHandler`'s `except` branch owns
  `logger.exception("article_save_failed", ...)` instead (same event name,
  moved up one layer).
- `NormalizeTagsUseCase.execute()` no longer logs `normalize_tags_failed` on
  the primary failure — it still has its own `try/except`, but only to roll
  back the shared per-article session before re-raising (and logs only if that
  *rollback itself* fails, via `normalize_tags_rollback_failed` — a genuinely
  use-case-owned side effect, not outcome logging).
  `TagNormalizationHandler`'s `except` branch owns
  `logger.exception("tag_normalization_failed", ...)`.

Success-path logging is unchanged by this: each use case still logs its own
completion milestone once (`article_saved`, `analysis_completed`,
`tag_normalization_completed` stays handler-side since the use case itself
returns `None` on success), and no handler duplicates it — so the "log each
outcome exactly once" property this entry originally called out still holds,
just with failure ownership now consistently on the handler side across all
three pairs instead of split.

**Why the convention flipped**: centralizing every failure's `logger.exception(...)`
call at the one `try/except` per handler also guarantees that call site is the
one place building the corresponding `*FailedEvent` — the two responsibilities
(log the failure, record it as a `FailedTask`) can't drift out of sync or be
forgotten independently anymore, which a `NormalizeTagsUseCase`-style "use case
logs, handler builds the event" split made easier to get wrong (as evidenced by
`ProcessScrapedArticleUseCase`'s save failure never having built a `FailedEvent`
at all — the pattern this fix closed).

## The three translation use cases repeat the same boilerplate skeleton — worth extracting, not worth merging

**Where**: `src/modules/intelligence/application/use_cases/translate_article.py`,
`src/modules/intelligence/application/use_cases/translate_article_body.py`,
`src/modules/intelligence/application/use_cases/translate_tags.py`

`TranslateArticleUseCase`, `TranslateArticleBodyUseCase`, and
`TranslateTagsUseCase` (each with a near-identical async sibling in the same
file — 6 classes total) all repeat the same five-step skeleton nearly verbatim:
check whether a translation already exists (return it if so) → render an
injected prompt template → call `llm_service.translate("", rendered.content)`
→ parse the raw LLM text response → persist via the repository.

**Note (post error-handling unification)**: this skeleton used to end with "the
whole thing wrapped in `try/except Exception: logger.error(...); return a
failure-shaped Result`" for all three — that's no longer accurate for
`TranslateArticleUseCase`/`TranslateArticleBodyUseCase`, which now raise
directly on any failure (LLM exhausted, unparseable response, or persistence
failing) with no internal `try/except` and no `success`/`exception_type`
fields left on their Result dataclasses at all — the caller
(`AnalysisCompletedHandler`) owns catching and logging now, same as every
other use case/handler pair in this codebase. `TranslateTagsUseCase` was never
quite this shape to begin with (no top-level `try/except` — only its
per-item `save()` calls are individually caught so one bad item doesn't sink
the whole batch — and it returns a `{total, success, failed}` count dict, not
a Result object), so it's unaffected. The four remaining shared steps above
are still duplicated across all three/six classes as described.

**Why they're still three separate classes, not one merged with different
injected content** — verified by reading all three in full, the actual
differences go deeper than "different data injected":
- Different target table/parent key: `AnalysesTranslation` (`analysis_id`, 4
  fields) vs `ArticleTranslation` (`article_id`, 2 fields) vs
  `TagTranslation`/`TagGroupTranslation` (two separate tables, `tag_id`/`group_id`).
- Different execution model: the first two are "given one specific id,
  translate it"; `TranslateTagsUseCase` is a **batch backlog worker** — it
  queries `find_tags_without_translation(language, limit)` itself rather than
  being handed a target, and exposes two methods (`translate_tags`/
  `translate_groups`), not one `execute()`.
- Different response-parsing logic per format (regex header-splitting for
  article sections, a dedicated `parse_response()` for title+content, positional
  line-matching plus a `"name | description"` sub-parse for tags/groups) and a
  different count of injected prompt templates (1, 1, and 2 respectively).

Merging them into one parameterized class would mean injecting not just content
but also *which* repository shape, *which* prompt template(s), and *which*
parsing strategy — effectively reinventing a Strategy-pattern generic
translator, which is more complex than three small single-purpose classes, not
less. Not a merge candidate.

**What is worth doing**: extract the repeated exists-check early-return into a
shared helper function or mixin that all three (and their async siblings) call
into, while keeping each class's own `execute()`/`translate_tags()`/
`translate_groups()`, its own repository dependency, its own prompt
template(s), and its own response-parsing logic exactly as they are today.
Reduces literal duplicated lines without collapsing three genuinely different
responsibilities into one. (The other half of the original suggestion — extract
the error-handling wrapper — is now moot for `TranslateArticleUseCase`/
`TranslateArticleBodyUseCase` per the note above; there's no per-use-case error
wrapper left to extract, since that responsibility now lives once in the
handler.) Not urgent — found during an architecture walkthrough, no bug involved.

## Recording a `FailedTask` has three different, inconsistent call paths across the codebase

**Where**: `src/bootstrap.py` (`_on_discover_failed`), `src/infrastructure/collection/collection_pipeline.py`
(`_record_rag_skipped` + the run-end `save_many` call), `src/modules/intelligence/application/event_handlers/failed_task_persistence_handler.py`

There is no single, consistent way "a failure gets recorded as a `FailedTask`
row" in this codebase — three different paths exist, each wired differently:

1. **Discover's rate-limit abort** (`bootstrap.py::_on_discover_failed`) — calls
   `failed_task_repo_sync.save(failed)` **directly**, from a plain function, no
   handler, no use case, no event involved at all (this runs inside
   `ScrapeExecutor`'s thread pool, outside the async/event-driven world
   entirely, so bypassing events here is arguably justified).
2. **RAG's circuit-breaker bulk skip** (`collection_pipeline.py::_record_rag_skipped`
   + the run-end `repo.save_many(self._rag_skipped_tasks)` call) — also calls
   the repository **directly**, no handler, no event, no use case — a batch
   write done once at run-end.
3. **Scrape-save / analysis / tag-normalization / translation / RAG-ingestion
   failures** — go through `FailedTaskPersistenceHandler.handle()`, subscribed
   to each stage's own `XxxFailedEvent` on that stage's own event bus (see the
   "polymorphic failure sink" pattern; `ArticleSaveFailedEvent` was the most
   recent addition to this list — `ProcessScrapedArticleUseCase`'s save
   failure used to fall through this classification entirely with no
   `FailedTask` record at all, now fixed by routing it through this same path).

Only path 3 is event-driven and reusable across stages; paths 1 and 2 each
re-implement their own inline "build a `FailedTask`, call save()" logic instead
of going through any shared abstraction — so there are effectively three
independent, uncoordinated implementations of "record a failure," not one.

**Why it hasn't mattered yet**: each path works correctly on its own — this is
a consistency/duplication concern, not an observed correctness bug. Paths 1-2
sit outside the async event-bus world for structural reasons (sync thread pool,
run-end batch flush respectively), so collapsing all three into literally one
code path isn't free — but the *logic* of "build this FailedTask shape, log it,
save it, handle save failure" is duplicated across all three today with no
shared helper at all.

**Suggested fix, if ever revisited**: extract the "construct + persist a
`FailedTask` (with its own try/except/log-on-save-failure)" logic that's
currently inline in both `_on_discover_failed` and `_record_rag_skipped`/the
run-end bulk save into a small shared helper (sync and async variants, mirroring
this codebase's existing sync/async-sibling convention) that both call — and
that `FailedTaskPersistenceHandler.handle()` also delegates to internally,
rather than duplicating its own repo-call logic separately. Not a call for
routing paths 1-2 through the event bus (they have real structural reasons to
stay direct) — just for sharing the "how do we build and save a `FailedTask`"
logic itself. Not urgent, no incident has surfaced.

## `TranslateArticleUseCase` actually translates the *analysis*, not the article — misleading name, historical cause identified

**Where**: `src/modules/intelligence/application/use_cases/translate_article.py`,
`src/modules/intelligence/application/use_cases/translate_article_body.py`

`AsyncTranslateArticleUseCase` (`translate_article.py`) translates the LLM's
*analysis* output — `summary`/`pain_points`/`insights`/`innovations`, keyed by
`analysis_id`, persisted to `AnalysesTranslation`. It does **not** touch the
article's own title/content at all — that's a completely separate class,
`AsyncTranslateArticleBodyUseCase` (`translate_article_body.py`), keyed by
`article_id`, persisted to `ArticleTranslation`. The naming is backwards from
what a reader would expect: the class named generically "Article" translates
the analysis, while the class that actually translates the article's own body
needed the more specific "ArticleBody" suffix to distinguish itself.

**Why it happened**: CLAUDE.md's own ORM Models section documents the
timeline — "English content was normalized into translations by migration
`15_add_translations` (article-body translations came later, in
`20_add_article_translation`)". `TranslateArticleUseCase` predates the very
concept of article-body translation — when it was named, "translating
something related to the article" only ever meant translating its analysis,
so the name wasn't ambiguous at the time. When article-body translation was
added later (migration 20), the new capability got its own, more precisely-named
sibling class rather than the original being renamed — consistent with this
codebase's general pattern of adding new sibling classes instead of touching
existing ones with active callers (here, `TranslateArticleUseCase` is also
used by the out-of-scope standalone `build_translation_pipeline()` / `make
translate` CLI job, so renaming it ripples beyond just this one file).

**Related, smaller naming quirk while in this area**: `AnalysesTranslation` /
`AnalysesTranslationRepository` / `AnalysesContent` use the plural "Analyses",
inconsistent with the singular `Analysis` / `AnalysisResult` /
`AnalyzeArticleUseCase` used everywhere else for the same concept (one
analysis).

**Suggested fix**: rename `TranslateArticleUseCase`/`AsyncTranslateArticleUseCase`
to something unambiguous (e.g. `TranslateAnalysisUseCase`) — and consider
normalizing `AnalysesTranslation`/`AnalysesTranslationRepository`/`AnalysesContent`
to the singular `Analysis...` form used elsewhere. Both are pure renames with
no behavior change, but ripple beyond `analysis_completed_handler.py` into
`build_translation_pipeline()`'s standalone CLI job and any other callers/tests
of these classes — a mechanical but non-trivial, repo-wide rename, not a
one-file patch. Not urgent (no functional impact), but flagged because
imprecise naming here is actively disliked, not just a minor nit to defer
indefinitely.

## No database-side observability — only the backend app's own CPU is profiled

**Where**: `backend/observability.py` (`setup_profiling`), `backend/routers/grafana.py`,
`.railway/railway.ts`, `docker-compose.yml`

The Grafana Cloud Profiles integration just added (`setup_profiling()`, `GET
/grafana/profile`, the flame graph in `RunWaterfallDialog`) measures **only the
backend pod's own CPU** — `pyroscope.configure()` runs inside `backend/main.py`'s
process, and Postgres is a completely separate process Railway manages, which this
profiler never touches. A "Postgres SELECT" span barely registers in the flame graph
even when its trace duration is nonzero, because CPU profiling only samples time the
CPU is actually busy — the wall-clock time spent blocked waiting on the DB's response
(almost all of a fast query's duration) is invisible to it by design. So there is
currently **no way to see the database server's own resource usage** (its own CPU,
memory, disk I/O, connection counts, cache hit ratio, per-query cost) from anywhere
in this stack.

**Why `node_exporter` (the obvious first answer) doesn't work here**: it needs to run
on the same host as what it's measuring, reading `/proc`/`/sys` directly. Railway's
managed Postgres gives no host/SSH access at all, so there's no machine to install it
on — ruled out during this same conversation.

**What does work**: `postgres_exporter` (prometheuscommunity/postgres-exporter)
doesn't need host access — it just needs a normal SQL connection string
(`DATA_SOURCE_NAME`) and scrapes `pg_stat_activity`/`pg_stat_database`/
`pg_stat_user_tables`/etc. via ordinary queries, exposing them as `/metrics` for
Prometheus-style scraping. This is the piece to add.

**Two decisions still open (asked, not yet answered) before implementing**:

1. **Scope**: local dev only (`docker-compose.yml`, pointed at the local `postgres`
   service — safe, no cost, but doesn't show anything about the actual
   production/Railway-managed DB) vs. also production (a **new, persistent Railway
   service** — real ongoing cost, not just a code change, needs `.railway/railway.ts` +
   `.railway/constants.ts` wiring following the existing per-service pattern).
2. **How the metrics actually reach Grafana Cloud**: `postgres_exporter` only exposes
   `/metrics` for something else to *scrape* — Grafana Cloud does not reach out and
   pull from arbitrary user endpoints (no Private Datasource Connect set up here), so
   a scrape-and-remote-write agent (Grafana Alloy / grafana-agent) is also needed in
   front of it. Grafana Cloud's own Connections page has a guided "PostgreSQL
   integration" flow that generates the correct Alloy config + remote-write
   credentials directly — that needs the account owner to click through it (same as
   the Profiles endpoint/user setup earlier in this project), not something codeable
   from here blind. The alternative is hand-writing an Alloy scrape config once the
   remote-write endpoint/credentials are known.

**Suggested fix, when resuming**: get answers to the two questions above, then (if
production is in scope) add `postgres_exporter` + the chosen shipping mechanism as new
Railway service(s) via `.railway/railway.ts`, following the same
`service("name", {...})` pattern the 10 existing services already use — and/or add a
`postgres_exporter` service to `docker-compose.yml` for local dev visibility. Not
urgent — flagged mid-conversation, no incident driving it, just a real observability
gap now that the CPU-only nature of the profiler is understood.
