# Contract: Rate-Limit Refusal Response

Applies to every endpoint protected by a Rate Limit Policy (`POST /auth/guest`, `POST /auth/verify`, `POST /auth/register`, `POST /auth/google/authorize`, `POST /auth/refresh`, `POST /auth/guest/refresh`, `POST /chat/completions`, `GET /search`, `GET /search/autocomplete`).

## When a request is within its policy's limit

No change to the endpoint's existing documented behavior/response shape. (`POST /chat/completions` keeps its existing `X-RateLimit-Remaining`/`X-RateLimit-Limit` success headers, which describe the *daily* quota and are unrelated to this contract.)

## When a request exceeds its policy's limit

**Status**: `429`

**Body** (existing shared `ErrorResponse` shape, `backend/schemas/error.py`):

```json
{
  "error": {
    "code": "RATE_LIMIT_EXCEEDED",
    "message": "<human-readable, does not echo attacker-controlled input>",
    "request_id": "<existing request-id convention>",
    "retry_after_seconds": 42
  }
}
```

- `code` is always the literal `RATE_LIMIT_EXCEEDED` — this is what lets a caller (including `frontend/lib/api/client.ts`) distinguish a rate-limit refusal from any other 4xx/5xx without parsing `message` text (FR-005).
- `retry_after_seconds` is always present and is the number of seconds until that caller's window resets (derived from the Redis key's TTL at refusal time).
- The request is refused **before** any endpoint-specific validation or side effect runs (FR-002's "evaluated before the submitted credentials themselves are checked", generalized to every protected endpoint) — a refusal never partially executes the endpoint's normal logic.

## Consistency requirements

- Identical shape regardless of which policy triggered the refusal (guest-token issuance, auth attempts, chat burst, search) — callers only ever need to branch on `code === "RATE_LIMIT_EXCEEDED"`, never per-endpoint.
- Identical shape regardless of which running backend instance handled the request (FR-006) — the policy's Redis-backed counter, not local process state, decides the outcome.
- Sentry/logging treatment matches every other 4xx `DomainError` category (`backend/exceptions/handlers.py`): logged at `warning`, not sent to Sentry, not counted in the 5xx-only `admin.requestErrorRate` metric — a rate-limit refusal is expected/recoverable, not a bug.

## Frontend handling

`apiFetch` (`frontend/lib/api/client.ts`) already retries on any `429` (`isRetryableStatus`) with exponential backoff before surfacing a failure to the caller — this contract does not change that retry behavior. A caller that exhausts `apiFetch`'s retries still receives the raw `Response`; call sites that want to react specifically to a rate-limit refusal (as opposed to any other failure) read `error.code === "RATE_LIMIT_EXCEEDED"` from the parsed body, the same pattern already used for every other `ErrorResponse`-shaped error.
