"""Explode the Railway env-var VALUES from the tfvars into `KEY=value` lines for
`$GITHUB_ENV`, so `.railway/railway.ts` can read them via `process.env.X` at
`railway config plan|apply` time (025-iac-provisioning "Revision 6", task T6-08c).

This is the v2 replacement for `push_railway_variables.py` doing the value push:
`railway.ts` becomes the single place that says *which* service gets *which*
variable; this script only supplies the non-committable values (secrets +
`${{...}}` reference strings), pulled from the same
`secrets/{railway,github}-{shared,<env>}.tfvars` files everything else already
uses. Name mapping (`RAILWAY_NAME -> tfvars key`) is read from
`infra/terraform/railway/railway-services.json` — the union of every
`shared_groups` entry and every service's `own`.

NOT emitted (kept `preserve()` in railway.ts, so nothing here needs to):
  - UV_GROUP           — per-service (a single env var can't hold all four values);
                         a plain literal per service in railway.ts instead
  - anything `unmanaged` in railway-services.json (OPENROUTER_API_KEY,
    RESEND_API_KEY, RESEND_FROM_EMAIL) — deliberately hand-managed on Railway
  - empty tfvars values (FIXIE_URL, RAG_DENSE_ENDPOINT_URL, RAG_SPARSE_*_limits
    on staging) — Railway does not store empty vars
  - values already expressed as SDK refs in railway.ts (DATABASE_URL, REDIS_URL,
    VECTOR_DB_* -> Postgres.env.* / Redis.env.*) and de-preserve()d literals
    (RAG tuning, Grafana endpoints, APP_ENV, ...) — listed in NON_ENV below

Usage:
    python scripts/tfvars_to_env.py --env staging   >> "$GITHUB_ENV"
    python scripts/tfvars_to_env.py --env production --check   # list, don't format

Stdlib only. Runs anywhere the tfvars files exist (CI materializes them from the
base64 TF_TFVARS_RAILWAY_* / TF_TFVARS_GITHUB_* secrets, same as terraform.yml).
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
TF_DIR = REPO_ROOT / "infra" / "terraform" / "railway"
MANIFEST = TF_DIR / "railway-services.json"

# RAILWAY_NAMEs that railway.ts already manages WITHOUT process.env — as an SDK
# ref, a de-preserve()d literal, a per-service literal, or a still-preserve().
# Anything in this set that the manifest maps is skipped here so the two halves
# can't fight. Keep in sync with railway.ts / .railway/constants.ts.
NON_ENV = {
    # T6-08b — SDK refs
    "DATABASE_URL", "REDIS_URL",
    "VECTOR_DB_HOST", "VECTOR_DB_NAME", "VECTOR_DB_PASSWORD",
    "VECTOR_DB_PORT", "VECTOR_DB_USER",
    # T6-08a — de-preserve()d literals (.railway/constants.ts)
    "APP_ENV", "CONTACT_EMAIL", "VECTOR_DB_SCHEMA",
    "GRAFANA_LOKI_URL", "GRAFANA_LOKI_USER",
    "GRAFANA_OTLP_ENDPOINT", "GRAFANA_OTLP_USER",
    "GRAFANA_PROMETHEUS_URL", "GRAFANA_PROMETHEUS_USER",
    "GRAFANA_TEMPO_URL", "GRAFANA_TEMPO_USER",
    "GRAFANA_URL",
    "RAG_DENSE_API_KEY_ENV", "RAG_DENSE_DIMENSION", "RAG_DENSE_MODEL",
    "RAG_DENSE_PROVIDER", "RAG_DENSE_RPD", "RAG_DENSE_RPM", "RAG_DENSE_TPM",
    "RAG_SPARSE_DIMENSION", "RAG_SPARSE_MODEL", "RAG_SPARSE_PROVIDER",
    "RAG_CHUNK_OVERLAP", "RAG_CHUNK_SIZE", "RAG_EMBED_BATCH_SIZE",
    "SWAGGER_TRY_IT_OUT_ENABLED", "CHATBOT_MAX_TOKENS",
    "SEARCH_AUTOCOMPLETE_MAX_QUERY_LEN", "SEARCH_MIN_DOC_FREQ",
    # T6-08c — Redis logical-DB URLs: literal ${{Redis.REDIS_URL}}/N in
    # constants.ts (the tfvars form has non-round-tripping inner spaces)
    "CACHE_REDIS_URL", "SEARCH_INDEX_REDIS_URL",
    # T6-08c PROD-DRIFT HOLD — production's live value != the tfvars; left
    # preserve() in railway.ts until reconciled, so don't emit them here either.
    "NEXTAUTH_SECRET", "GITHUB_PACKAGE_TOKEN", "FRONTEND_ORIGIN", "NEXTAUTH_URL",
    # per-service literal in railway.ts, not a single process.env value
    "UV_GROUP",
    # kept preserve() in railway.ts (empty on some/all envs, or hand-managed)
    "FIXIE_URL", "RAG_DENSE_ENDPOINT_URL",
    "RAG_SPARSE_RPD", "RAG_SPARSE_RPM", "RAG_SPARSE_TPM",
    "OPENROUTER_API_KEY", "RESEND_API_KEY", "RESEND_FROM_EMAIL",
}


def _load_kv(path: Path) -> dict[str, str]:
    """Parse `key = "value"` / bare `key = value` tfvars lines."""
    out: dict[str, str] = {}
    if not path.exists():
        return out
    for line in path.read_text(encoding="utf-8").splitlines():
        m = re.match(r'\s*([A-Za-z_][A-Za-z0-9_]*)\s*=\s*"([^"]*)"\s*(#.*)?$', line)
        if m:
            out[m.group(1)] = m.group(2)
            continue
        m = re.match(r'\s*([A-Za-z_][A-Za-z0-9_]*)\s*=\s*([^"#\s][^#\n]*?)\s*(#.*)?$', line)
        if m:
            out[m.group(1)] = m.group(2)
    return out


def _unescape_ref(v: str) -> str:
    """tfvars keep Railway refs HCL-escaped as `$${{ ... }}`; Railway wants `${{ ... }}`."""
    return v.replace("$${", "${")


def _name_map() -> dict[str, str]:
    """{RAILWAY_NAME: tfvars_key} — union of shared_groups + every service's own.

    Raises on a RAILWAY_NAME that two definitions map to different tfvars keys
    (UV_GROUP is the known one; it is in NON_ENV so it never reaches here)."""
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    pairs: dict[str, str] = {}
    sources: list[tuple[str, dict]] = [
        (f"shared_groups/{g}", body) for g, body in manifest["shared_groups"].items()
    ]
    for svc, body in manifest["services"].items():
        sources.append((f"services/{svc}/own", body.get("own", {})))
    for where, body in sources:
        for railway_name, tfvar_key in body.items():
            if railway_name in NON_ENV:
                continue
            prev = pairs.get(railway_name)
            if prev is not None and prev != tfvar_key:
                raise SystemExit(
                    f"tfvars_to_env: {railway_name} maps to both {prev!r} and "
                    f"{tfvar_key!r} ({where}) — add it to NON_ENV and handle it "
                    f"explicitly in railway.ts"
                )
            pairs[railway_name] = tfvar_key
    return pairs


def resolve(env: str) -> dict[str, str]:
    tfvars: dict[str, str] = {}
    for name in (
        "railway-shared.tfvars", f"railway-{env}.tfvars",
        "github-shared.tfvars", f"github-{env}.tfvars",
    ):
        tfvars.update(_load_kv(TF_DIR / "secrets" / name))  # per-env file wins

    out: dict[str, str] = {}
    for railway_name, tfvar_key in sorted(_name_map().items()):
        val = tfvars.get(tfvar_key, "")
        if val == "":
            continue  # missing or intentionally empty -> Railway stores nothing
        val = _unescape_ref(val)
        if "\n" in val:
            raise SystemExit(f"tfvars_to_env: {railway_name} value has a newline")
        out[railway_name] = val
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--env", required=True, choices=["staging", "production"])
    ap.add_argument(
        "--check", action="store_true",
        help="print `NAME (tfvars_key)` one per line instead of `NAME=value`",
    )
    args = ap.parse_args()

    # `$GITHUB_ENV` (and our local plan harness) must get LF only — a stray CR
    # from a Windows text-mode stdout ends up appended to every value.
    try:
        sys.stdout.reconfigure(newline="\n")
    except (AttributeError, ValueError):
        pass

    resolved = resolve(args.env)
    if args.check:
        nmap = _name_map()
        for name in sorted(resolved):
            print(f"{name} ({nmap[name]})")
        print(f"\n{len(resolved)} vars for {args.env}", file=sys.stderr)
        return 0

    for name, val in resolved.items():
        print(f"{name}={val}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
