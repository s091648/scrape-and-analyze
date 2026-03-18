# Design: User Tracking, Loki Frontend Logging, Geo-IP, Telegram Notifications

**Date:** 2026-03-18
**Status:** Approved

---

## Overview

This change adds three capabilities:

1. **User tracking** — enrich backend request logs with authenticated user identity, real IP, geo-location, and user agent
2. **Frontend Loki logging** — Next.js proxy route pushes structured logs (including request body) directly to Loki
3. **Telegram notifications** — after each scraping job, push a per-source summary table to a Telegram chatroom via an extensible notifier abstraction

No database schema changes are required. All data flows to Loki (observability) or Telegram (notification).

---

## Part 1: Backend — Real IP, Geo-IP, Middleware Enrichment

### 1.1 Proxy Header Trust

**Goal:** `request.client.host` returns the real user IP instead of Railway's internal proxy IP.

**Changes:**
- Add `ProxyHeadersMiddleware` as the outermost middleware in `backend/main.py`
- Add `--proxy-headers --forwarded-allow-ips='*'` to the Uvicorn startup command in `docker-compose.yml` (backend service)

### 1.2 GeoIP Database (MaxMind GeoLite2-City)

**Goal:** Resolve IP addresses to country + city at request time.

**Changes:**
- Add `geoip2` to `backend/requirements.txt`
- Add `MAXMIND_LICENSE_KEY` to `.env.example` (build-time ARG only, not a runtime env var)
- In the backend `Dockerfile`, use the existing builder stage (which has `curl` installed or must add it) to download the DB, then copy it to the runtime stage:

```dockerfile
# In builder stage — install curl if not present, then download DB
ARG MAXMIND_LICENSE_KEY
RUN apt-get install -y curl && \
    mkdir -p /app/data && \
    curl -sSL \
      "https://download.maxmind.com/app/geoip_download?edition_id=GeoLite2-City&license_key=${MAXMIND_LICENSE_KEY}&suffix=tar.gz" \
    | tar -xz --strip-components=1 -C /app/data/

# In runtime stage — copy the DB file from builder
COPY --from=builder /app/data/GeoLite2-City.mmdb /app/data/GeoLite2-City.mmdb
```

`MAXMIND_LICENSE_KEY` is a Docker build-time `ARG` (not a runtime `ENV`). In Railway it must be set as a build variable, not a runtime env var. In `docker-compose.yml` it is passed as `args: [MAXMIND_LICENSE_KEY]` under `build:`.

Railway re-builds on every deploy; the `mmdb` layer will be cached as long as the Dockerfile layer above it is unchanged. If the MaxMind download fails (transient network issue), the build fails — this is the intended behaviour since a missing DB causes silent geo-lookup failures.

- Add `src/observability/geoip.py` — singleton reader initialised at app startup:

```python
def get_geo(ip: str) -> dict:
    # returns {"country": "TW", "city": "Taipei"} or {}
```

Reader is initialised once at module import. Returns empty dict if DB file not found, IP is private/loopback, or lookup raises any exception (graceful degradation — never blocks a request).

### 1.3 RequestLoggingMiddleware Enrichment

**File:** `backend/middleware/logging.py`

**New log fields added per request:**

| Field | Source | Fallback |
|-------|--------|----------|
| `user_id` | JWT `sub` claim | `"anonymous"` |
| `user_email` | JWT payload | omitted |
| `user_role` | JWT `role` claim | omitted |
| `ip` | `request.client.host` (corrected by ProxyHeaders) | raw host |
| `user_agent` | `User-Agent` header | omitted |
| `geo_country` | GeoIP lookup on IP | omitted |
| `geo_city` | GeoIP lookup on IP | omitted |

JWT is decoded using `NEXTAUTH_SECRET` (already available). If token is absent, expired, or invalid, user fields are silently skipped — no error is raised for public/unauthenticated endpoints.

GeoIP reader is accessed via the singleton from `geoip.py`. Lookup failure never propagates to the response.

**Loki label note:** The backend already emits logs under `app: "scraper"`. After this change, API request logs (from `RequestLoggingMiddleware`) will share the same Loki stream. When querying Grafana, use `event="request_completed"` to filter API logs, and `event="execution_started"` etc. for scraper job logs.

---

## Part 2: Frontend — Proxy Route Loki Logging

### 2.1 New file: `frontend/lib/loki-logger.ts`

Lightweight Loki push utility using Node.js built-in `fetch`. No additional npm packages.

```typescript
interface LogEntry {
  level: string
  labels: Record<string, string>
  message: Record<string, unknown>
}

export function pushToLoki(entry: LogEntry): void
// Fire-and-forget: called WITHOUT await. Errors are console.error'd, never thrown.
// The returned Promise is intentionally not awaited so it never blocks the response.
```

Reads `GRAFANA_LOKI_URL`, `GRAFANA_LOKI_USER`, `GRAFANA_API_KEY` from environment (server-side only, not exposed to browser).

If any env var is missing, silently skips (same behaviour as backend `configure_loki()`).

**Labels sent to Loki:** `{ app: "frontend", env: "production" }` — distinct from backend's `app: "scraper"`, allowing independent filtering.

### 2.2 Proxy Route Changes: `frontend/app/api/proxy/[...path]/route.ts`

**Session resolution:** `getServerSession(authOptions)` — user identity without extra round-trips.

**Request body handling:** Body is a readable stream and can only be consumed once. Strategy:
1. Read and store body text for all methods except GET and HEAD
2. Reconstruct the forwarded request using the stored body text
3. Include body (parsed JSON or raw string) in log payload

This covers POST, PUT, PATCH, and DELETE-with-body.

**Sensitive field redaction:** Before logging, recursively scan all JSON keys (case-insensitive) and replace values with `"[REDACTED]"` for keys matching any of: `password`, `hashed_password`, `token`, `access_token`, `refresh_token`, `secret`, `api_key`, `authorization`, `private_key`, `credentials`. This is a known defence against accidental leakage; values stored under unexpected key names are not covered.

**Log fields:**

| Field | Source |
|-------|--------|
| `user_id` | NextAuth session |
| `user_email` | NextAuth session |
| `user_role` | NextAuth session |
| `ip` | `x-forwarded-for` header |
| `user_agent` | `user-agent` header |
| `method` | request method |
| `path` | forwarded API path |
| `status_code` | backend response status |
| `duration_ms` | proxy route timer |
| `request_body` | body for POST/PUT/PATCH/DELETE (redacted) |

**Timing:** `pushToLoki(...)` is called (without `await`) after the backend response is received, before `return response`. Since it is not awaited, it does not block the client response. Failure is logged to `console.error` only.

**Double-logging note:** Each proxied request produces two Loki entries — one from the frontend proxy route (`app: "frontend"`) and one from the backend middleware (`app: "scraper"`). The frontend log has session user info and request body; the backend log has Geo-IP data and the corrected real IP. Use `app` label in Grafana to filter the stream you need.

---

## Part 3: Telegram Notifications

### 3.1 Run Summary Accumulator

**New file:** `src/observability/run_summary.py`

A thread-safe in-process accumulator that runs alongside (not replacing) existing OpenTelemetry counters.

```python
@dataclass
class SourceResult:
    source: str
    new: int = 0
    duplicate: int = 0
    failed: int = 0

class RunSummary:
    def record_new(self, source: str, count: int = 1) -> None
    def record_duplicate(self, source: str, count: int = 1) -> None
    def record_failed(self, source: str, count: int = 1) -> None
    def get_results(self) -> list[SourceResult]
    def total_new(self) -> int
    def total_duplicate(self) -> int
    def total_failed(self) -> int
```

Uses `threading.Lock` for thread safety since `ScraperWorker` threads call into `process_article()` concurrently.

### 3.2 RunSummary Call Chain Threading

`RunSummary` is created in `main()` and must be threaded through the following call chain. **All five functions require signature updates:**

```
main()                         ← creates RunSummary, passes to run_scrape_cycle()
  └─ run_scrape_cycle(summary) ← passes summary into handle_result closure
       └─ handle_result()      ← closure captures summary, passes to process_article_safe()
            └─ process_article_safe(summary)  ← passes to process_article()
                 └─ process_article(summary)
                      ├─ summary.record_new(scraped.source)       [where SCRAPER_ARTICLES_NEW.add() is]
                      ├─ summary.record_duplicate(scraped.source) [where SCRAPER_ARTICLES_DUPLICATE.add() is]
                      └─ on failure → record_failure(session, task_type, url, article_id, error, source=scraped.source)
```

`record_failure()` gains an optional `source: str = ""` parameter. When `source` is available (called from `process_article()`), it is passed through; when called from `process_article_safe()` catch block (where `scraped.source` is available), it is also passed. `summary.record_failed(source)` is called inside `record_failure()` when `source` is non-empty.

### 3.3 Notifier Abstraction

**Directory structure:**
```
src/notifications/
├── __init__.py
├── base.py      — BaseNotifier ABC
├── telegram.py  — TelegramNotifier
└── service.py   — factory + notify_all()
```

**`base.py`:**
```python
from abc import ABC, abstractmethod

class BaseNotifier(ABC):
    @abstractmethod
    def send_scrape_summary(self, summary: RunSummary, duration: float) -> None: ...
```

**`telegram.py`:** Calls `https://api.telegram.org/bot{TOKEN}/sendMessage` via `requests.post(timeout=10)`. Uses `parse_mode="MarkdownV2"` with the table wrapped in a code block for guaranteed monospace alignment. Calls `response.raise_for_status()` so HTTP errors (invalid token, bad chat_id) are surfaced as exceptions and caught by `notify_all()`.

**`service.py`:**
```python
def get_notifiers() -> list[BaseNotifier]:
    """
    Currently reads from env vars.

    Future extension: accept optional user_id and query notification_settings
    table to return per-user configured notifiers. For system-level jobs
    (e.g. scraping cron), use a designated admin notification setting row.
    """
    notifiers = []
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")
    if token and chat_id:
        notifiers.append(TelegramNotifier(token, chat_id))
    return notifiers

def notify_all(summary: RunSummary, duration: float) -> None:
    for notifier in get_notifiers():
        try:
            notifier.send_scrape_summary(summary, duration)
        except Exception as e:
            logger.warning("notifier_failed", notifier=type(notifier).__name__, error=str(e))
```

`main.py` calls only `notify_all(summary, duration)` — no knowledge of which notifiers are active.

### 3.4 Telegram Message Format

The table is wrapped in a MarkdownV2 code block (`` ``` ``) to guarantee monospace rendering in all Telegram clients. The `⚠` marker uses only the base character (U+26A0) without the variation selector (U+FE0F) to avoid column-width shift in monospace.

```
🤖 Scraping 任務完成

📅 2026-03-18 00:05 UTC
⏱ 耗時：59.4 秒
📦 來源數：8

```
來源            新增  重複  失敗
────────────────────────────
techcrunch        0    12    0
venturebeat       0     8    0
arxiv             0     0    1 ⚠
iotworldtoday     0     1    0
nvidia            0     0    0
siemens           0     0    0
aws_iot           0     0    0
azure_iot         0     0    1 ⚠
────────────────────────────
合計              0    21    2
```

⚠ 有 2 個錯誤，請檢查 log
```

- `⚠` (U+26A0, no variation selector) appended per row when `failed > 0`
- Footer: `⚠ 有 N 個錯誤，請檢查 log` when total_failed > 0; `✅ 全部完成` otherwise

### 3.5 main.py Integration

`RunSummary` is created before the scrape cycle. `notify_all()` is placed inside the `finally` block, **before** `push_metrics()`, so notifications go out even if the scrape raises an exception. Both calls are wrapped in their own silent error handling so neither can prevent the other from running.

```python
summary = RunSummary()
try:
    ...
    run_scrape_cycle(sources_due, analyzer, prompt, correlation_id, summary)
except Exception as e:
    logger.error("execution_failed", error=str(e))
    raise
finally:
    duration = time.time() - start_time
    logger.info("execution_completed", ...)
    SCRAPER_DURATION.record(duration)
    notify_all(summary, duration)   # inside finally, before push_metrics
    push_metrics()
```

**No-sources-due path:** If `sources_due` is empty, `main()` returns early before the `finally` block, so no notification is sent. This is intentional — a "nothing to do" run is noise.

---

## Environment Variables

| Variable | Used by | Type | Notes |
|----------|---------|------|-------|
| `MAXMIND_LICENSE_KEY` | Backend Dockerfile | Build ARG | Set as Railway build variable, not runtime env var |
| `TELEGRAM_BOT_TOKEN` | `TelegramNotifier` | Runtime ENV | Already in `.env.example` |
| `TELEGRAM_CHAT_ID` | `TelegramNotifier` | Runtime ENV | Already in `.env.example` |
| `GRAFANA_LOKI_URL` | Frontend `loki-logger.ts` | Runtime ENV | Already exists |
| `GRAFANA_LOKI_USER` | Frontend `loki-logger.ts` | Runtime ENV | Already exists |
| `GRAFANA_API_KEY` | Frontend `loki-logger.ts` | Runtime ENV | Already exists |

---

## Future Notes

### Notification Settings DB Extension

When `notification_settings` table is added:

1. `service.py`'s `get_notifiers()` should accept an optional `user_id` parameter
2. For the scraping cron job (no user context), a designated system-level row in `notification_settings` controls which notifiers are active
3. `BaseNotifier` interface requires no changes — new notifiers (Slack, Email, etc.) just implement `send_scrape_summary()`
4. `main.py` requires no changes — it only calls `notify_all()`

---

## Files Changed / Created

### New files
- `src/observability/geoip.py`
- `src/observability/run_summary.py`
- `src/notifications/__init__.py`
- `src/notifications/base.py`
- `src/notifications/telegram.py`
- `src/notifications/service.py`
- `frontend/lib/loki-logger.ts`

### Modified files
- `backend/main.py` — add `ProxyHeadersMiddleware`
- `backend/middleware/logging.py` — enrich with user/IP/geo fields
- `backend/requirements.txt` — add `geoip2`
- `backend/Dockerfile` — download GeoLite2-City.mmdb at build time, copy to runtime stage
- `docker-compose.yml` — add `--proxy-headers` to Uvicorn command, add `MAXMIND_LICENSE_KEY` build arg
- `frontend/app/api/proxy/[...path]/route.ts` — session parsing + body handling + Loki push
- `src/main.py` — integrate `RunSummary` + `notify_all()`, update call chain signatures
- `.env.example` — add `MAXMIND_LICENSE_KEY`

### Functions with signature changes in `src/main.py`
- `run_scrape_cycle()` — add `summary: RunSummary` param
- `handle_result()` closure — captures `summary` from outer scope
- `process_article_safe()` — add `summary: RunSummary` param
- `process_article()` — add `summary: RunSummary` param
- `record_failure()` — add optional `source: str = ""` param

### No changes
- Database schema (no Alembic revision needed)
- OpenTelemetry metrics (RunSummary runs alongside, does not replace)
