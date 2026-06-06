# Contract: Grafana Datasource Proxy API

**Location**: `frontend/app/api/grafana-proxy/[...path]/route.ts`

**Auth**: Requires authenticated session (NextAuth). Requests without session return 401.

**SSRF Protection**: Each sub-route only forwards requests to its configured datasource URL. All other targets return 403.

---

## Endpoint: GET /api/grafana-proxy/metrics

Proxies PromQL `query_range` requests to Grafana Cloud Mimir.

**Query Parameters**:

| Parameter | Required | Description |
|-----------|----------|-------------|
| `query` | Yes | PromQL expression |
| `start` | Yes | Unix timestamp (seconds) |
| `end` | Yes | Unix timestamp (seconds) |
| `step` | No | Resolution step. Default: `60` |

**Success Response**: 200 — Prometheus `query_range` JSON (transparently forwarded)

**Error Responses**:
- 400 — Missing required parameter
- 401 — Unauthenticated
- 403 — `GRAFANA_PROMETHEUS_URL` not configured
- 502 — Upstream fetch failed

---

## Endpoint: GET /api/grafana-proxy/logs

Proxies LogQL `query_range` requests to Grafana Cloud Loki.

**Query Parameters**:

| Parameter | Required | Description |
|-----------|----------|-------------|
| `query` | Yes | LogQL expression (e.g. `{app="scraper"} \|= "error"`) |
| `start` | Yes | Nanosecond timestamp |
| `end` | Yes | Nanosecond timestamp |
| `limit` | No | Max log lines. Default: `100` |
| `direction` | No | `forward` or `backward`. Default: `backward` |

**Success Response**: 200 — Loki `query_range` JSON (transparently forwarded)

**Error Responses**:
- 400 — Missing required parameter
- 401 — Unauthenticated
- 403 — `GRAFANA_LOKI_URL` not configured
- 502 — Upstream fetch failed

---

## Endpoint: GET /api/grafana-proxy/traces

Proxies TraceQL search requests to Grafana Cloud Tempo.

**Query Parameters**:

| Parameter | Required | Description |
|-----------|----------|-------------|
| `q` | No | TraceQL expression. Default: `{ }` (all traces) |
| `start` | No | Unix timestamp (seconds). Default: now-24h |
| `end` | No | Unix timestamp (seconds). Default: now |
| `limit` | No | Max results. Default: `20` |
| `minDuration` | No | Filter by minimum duration (e.g. `100ms`) |

**Success Response**: 200 — Tempo search JSON (transparently forwarded)

**Error Responses**:
- 401 — Unauthenticated
- 403 — `GRAFANA_TEMPO_URL` not configured
- 502 — Upstream fetch failed

---

## Security Requirements

- All endpoints MUST check `getServerSession(authConfig)` before proceeding
- Each endpoint MUST only forward to its own pre-configured datasource URL (no URL parameter accepted from client)
- `GRAFANA_SA_TOKEN` MUST NOT appear in any client-side response
- Query parameters are forwarded as-is to the upstream — no sanitization of PromQL/LogQL/TraceQL (upstream handles validation)
