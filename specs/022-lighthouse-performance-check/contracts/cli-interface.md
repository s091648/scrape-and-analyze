# Contract: `make lighthouse-check` CLI Interface

This feature's "external interface" is a CLI (a `make` target wrapping a Node script), not an HTTP API — documented per the project-type guidance in the plan template.

## Invocation

```bash
make lighthouse-check
make lighthouse-check LIGHTHOUSE_URL=http://frontend_prod:3000
make lighthouse-check LIGHTHOUSE_ROUTES="/,/articles"
make lighthouse-check LIGHTHOUSE_URL=https://staging.example.com LIGHTHOUSE_ROUTES="/,/articles,/graph,/tags"
```

Internally (Makefile target body):

```bash
docker compose run --rm -v "$(CURDIR)/lighthouse-reports:/app/lighthouse-reports" frontend \
	node scripts/lighthouse-check.mjs --url "$(LIGHTHOUSE_URL)" --routes "$(LIGHTHOUSE_ROUTES)"
```

(`LIGHTHOUSE_URL`/`LIGHTHOUSE_ROUTES` rather than bare `URL`/`ROUTES` — this Makefile has no existing generic `URL`/`ROUTES` variable, but a prefixed name avoids ever colliding with one added later, consistent with this Makefile's existing `REMOTE_URL`/`DUMP_FILE` naming.)

## Parameters

| Makefile var | Script flag | Default | Notes |
|---|---|---|---|
| `LIGHTHOUSE_URL` | `--url` | `http://frontend_prod:3000` | Must be reachable from inside the `frontend` container's Docker network (i.e. a service name like `frontend_prod`/`frontend`, or any externally-resolvable host — not `localhost`, which inside a container refers to the container itself) |
| `LIGHTHOUSE_ROUTES` | `--routes` | `/,/articles,/graph,/tags` | Comma-separated list of paths; each is appended to `URL` as-is (must start with `/`) |

## Preconditions

- `backend` and `postgres` (and `redis`, for cache-aside reads) MUST already be running and healthy.
- The target frontend service (`frontend_prod` by default) MUST already be running and able to reach `backend` — this script does not start/stop any compose services itself.

## Exit codes

| Code | Meaning |
|---|---|
| `0` | Run completed; report written. Note: per-route failures do **not** by themselves cause a non-zero exit — see spec.md Edge Cases ("one route fails, others still report") and Assumptions ("informational for v1, no hard thresholds"). |
| `1` | Run could not start at all — `URL` unreachable, or the pre-flight `POST /auth/guest` call failed (see spec.md Edge Cases). No report is written in this case. |

## Output (stdout)

- One line per route as it completes: `✅ /articles` or `❌ /graph (逾時)`.
- Final line: the absolute path to the generated report, e.g. `報告已產出：lighthouse-reports/20260809-143000/report.md`.

## Output (filesystem)

See `contracts/report-format.md` and `data-model.md` for the full shape of `lighthouse-reports/<runId>/`.
