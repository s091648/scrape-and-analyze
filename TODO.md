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

## `ProcessScrapedArticleUseCase` save-failure has no `FailedTask` record, unlike every other failure path in the per-article chain

**Where**: `src/modules/collection/application/use_cases/process_scraped_article.py`,
`src/modules/collection/application/event_handlers/article_scraped_handler.py`

When `await self._article_repo.save(article)` raises, `ProcessScrapedArticleUseCase.execute()`
logs `article_save_failed` and returns `(ArticleOutcome.FAILED, None)`
(`process_scraped_article.py:57-61`); `ArticleScrapedHandler.handle()` records this
into `PipelineStats` and sets an ERROR-status span (`article_scraped_handler.py:53-56`)
— but **no `FailedTask` row is ever written** for this failure. Every later failure
point in the same per-article chain *does* get one: discover's rate-limit abort
(`bootstrap.py`'s `_on_discover_failed`), `AnalysisFailedEvent` →
`FailedTaskPersistenceHandler`, `TagNormalizationFailedEvent`/`TranslationFailedEvent`
→ the same handler, and the RAG circuit-breaker's bulk write
(`_record_rag_skipped`). This one save-failure path is the odd one out.

**Why a naive fix isn't free**: the failure happens inside the article's own
per-article `AsyncSession`, mid-`flush()` — after a failed flush, that session's
transaction is typically left in a state where it must be rolled back before any
further query (including an INSERT into `failed_tasks`) can run on it. So "just
call `failed_task_repo.save()` right after catching the exception, on the same
session" would likely raise again for the subset of failures caused by a genuine
DB-connectivity problem — worth being honest that this session is exactly the
scenario the discover-side `_on_discover_failed` avoids by using a completely
separate sync session/repo instead of the one that just failed.

**Why it's still worth recording, not left as intentional**: most of this failure's
realistic causes are *not* a dead DB — e.g. a `url_hash` unique-constraint race (two
concurrently-discovered candidates for the same underlying article slipping past the
earlier hash-based dedup checks) — where the connection is fine and only this one
`INSERT` failed; a rollback + retry on the same session would succeed there. And
unlike a fetch-stage failure (the URL usually reappears in the source feed/API next
run), an article that reaches this point has already survived discover+fetch+dedup —
if this insert fails, its content is gone with only a log line as a trace; there's
currently no durable record that this article was ever seen.

**Suggested fix**: mirror the discover-side pattern — roll back the per-article
session (or use a separate session/connection, to also cover the genuine
DB-outage case) and write a `FailedTask` row for this outcome too, so a save
failure leaves the same kind of durable trace every other failure branch in this
chain already leaves. Not urgent — no incident has surfaced from this gap yet,
this was found by inspection during an architecture walkthrough.

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

**Where**: `src/modules/collection/application/event_handlers/article_scraped_handler.py`,
`src/modules/intelligence/application/event_handlers/article_processed_handler.py`,
`src/modules/intelligence/application/use_cases/analyze_article.py`

No convention for "which layer logs an outcome" is written down anywhere (CLAUDE.md
or otherwise), but it can be reverse-engineered from the cleanest of the three
pairs: `NormalizeTagsUseCase`/`TagNormalizationHandler`. The use case's own
`except` branch logs the failure detail once (`normalize_tags_failed` — it has
the raw exception, richer context than any summarized result object a handler
receives), and the handler logs the success/completion milestone once
(`tag_normalization_completed`, right where it's about to publish the
corresponding `Completed` event) — each layer owns exactly one branch, zero
overlap.

The other two pairs each duplicate exactly one branch instead of splitting cleanly:

- ~~`ArticleScrapedHandler` duplicated the `FAILED` branch~~ **(fixed)** —
  `ProcessScrapedArticleUseCase.execute()` already logs `article_save_failed` on
  save failure; `ArticleScrapedHandler.handle()`'s `FAILED` branch used to *also*
  call `logger.error("article_scrape_failed", ...)` with mostly overlapping
  fields. Removed the handler-level log, kept `span.set_status(ERROR, ...)` and
  `pipeline_stats.record(...)` (genuinely handler-level concerns).
- ~~`ArticleProcessedHandler` duplicated the **success** branch instead~~
  **(fixed)** — `AnalyzeArticleUseCase.execute()`'s success path already logs
  `"analysis_completed"` (article_id, source, model, input/output tokens);
  `ArticleProcessedHandler.handle()`'s success branch used to log the **same
  event name** again with nearly identical fields, right before publishing
  `AnalysisCompletedEvent`. Removed the handler-level log, kept the span
  attribute sets and the `AnalysisCompletedEvent` construction.

**Why it hadn't mattered before fixing**: harmless duplication in both cases,
not a correctness bug — just noise in the logs (two entries where the clean
pair produces one).

Both instances found in this chain are now fixed; the rule going forward
(demonstrated by `NormalizeTagsUseCase`/`TagNormalizationHandler`, now matched
by the other two pairs) is: the use case logs failure detail (it has the raw
exception), the handler logs the success/completion milestone — each outcome
logged exactly once, by whichever layer has the most relevant context for it.

## The three translation use cases repeat the same boilerplate skeleton — worth extracting, not worth merging

**Where**: `src/modules/intelligence/application/use_cases/translate_article.py`,
`src/modules/intelligence/application/use_cases/translate_article_body.py`,
`src/modules/intelligence/application/use_cases/translate_tags.py`

`TranslateArticleUseCase`, `TranslateArticleBodyUseCase`, and
`TranslateTagsUseCase` (each with a near-identical async sibling in the same
file — 6 classes total) all repeat the same five-step skeleton nearly verbatim:
check whether a translation already exists (return it if so) → render an
injected prompt template → call `llm_service.translate("", rendered.content)`
→ parse the raw LLM text response → persist via the repository, the whole
thing wrapped in `try/except Exception: logger.error(...); return a
failure-shaped Result`.

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

**What is worth doing**: extract the repeated boilerplate (the exists-check
early-return, and the "call LLM inside try/except, log and return a failure
Result on any exception" wrapper) into a shared helper function or mixin that
all three (and their async siblings) call into, while keeping each class's own
`execute()`/`translate_tags()`/`translate_groups()`, its own repository
dependency, its own prompt template(s), and its own response-parsing logic
exactly as they are today. Reduces literal duplicated lines without collapsing
three genuinely different responsibilities into one. Not urgent — found during
an architecture walkthrough, no bug involved.

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
3. **Analysis / tag-normalization / translation / RAG-ingestion failures** — go
   through `FailedTaskPersistenceHandler.handle()`, subscribed to each stage's
   own `XxxFailedEvent` on that stage's own event bus (see the "polymorphic
   failure sink" pattern discussed in this session).

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
