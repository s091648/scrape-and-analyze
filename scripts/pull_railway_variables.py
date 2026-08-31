"""Read-only helper for the 025-iac-provisioning revision-2 import (task R35).

Pulls every service's CURRENT live environment variable values (both staging and
production) via the Railway CLI (`railway variables --json`) into a local,
git-ignored inventory, and — with --as-tfvars — a paste-ready
secrets/*.tfvars draft.

Runs on the HOST (needs the `railway` CLI + infra/terraform/railway/.env tokens)
— NOT inside a container. Uses only the Python standard library, so plain
`python scripts/pull_railway_variables.py` works; no `uv run`, no python-hcl2.

Never calls `terraform` and never writes to Railway — pull-only, not in CI.

⚠️ SECURITY: the output files concentrate every service's variable values
(secrets included) into one local file each — treat them like
infra/terraform/railway/.env: never share/commit, delete once the import batch
is done.

Prerequisites (task R35 order):
  1. `railway` CLI on PATH (`npm install -g @railway/cli`).
  2. infra/terraform/railway/.env has a Railway token. `railway variables` needs a
     project-scoped, environment-bound token (the account-level one Terraform's
     provider uses gets "Invalid RAILWAY_TOKEN" here) — add per-environment ones:
         RAILWAY_TOKEN_STAGING=...
         RAILWAY_TOKEN_PRODUCTION=...
     (falls back to a plain RAILWAY_TOKEN if a specific one isn't set).
  3. infra/terraform/railway/secrets/shared.tfvars exists with `railway_project_id` and
     every `service_id_<key>` filled in (copy from shared.tfvars.example — these
     are non-secret UUIDs from the Railway dashboard).

Usage:
    python scripts/pull_railway_variables.py [--as-tfvars] [SERVICE_KEY ...]
    (no SERVICE_KEY args = every service under infra/terraform/services/)

Output:
    infra/terraform/railway/.live-variables.json     (always)
    infra/terraform/railway/.live-variables.tfvars   (with --as-tfvars — a draft to split)
"""
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
TF_DIR = REPO_ROOT / "infra" / "terraform" / "railway"
# Bootstrap-credential file for the terraform providers. `.env` is the current
# name; `.env.local` is the pre-existing one, still honoured as a fallback.
ENV_LOCAL = TF_DIR / ".env"
if not ENV_LOCAL.exists() and (TF_DIR / ".env.local").exists():
    ENV_LOCAL = TF_DIR / ".env.local"
SHARED_TFVARS = TF_DIR / "secrets" / "shared.tfvars"
MANIFEST = TF_DIR / "railway-services.json"
OUTPUT_PATH = TF_DIR / ".live-variables.json"
TFVARS_OUTPUT_PATH = TF_DIR / ".live-variables.tfvars"

ENVIRONMENTS = ["production", "staging"]

_RAILWAY_INJECTED_RE = re.compile(r"^RAILWAY_")
_MODULE_LABEL_RE = re.compile(r'^\s*module\s+"(\w+)"\s*\{', re.MULTILINE)


class PullError(Exception):
    pass


def _to_tfvar_key(env_var_name):
    return env_var_name.lower()


def _escape_hcl(value):
    """Escape `${` -> `$${` (and `%{` -> `%%{`) so a Railway reference string like
    `${{ Redis.REDIS_URL }}` survives HCL parsing as a literal Railway resolves
    server-side."""
    if not isinstance(value, str):
        return value
    return value.replace("${", "$${").replace("%{", "%%{")


def _load_env_local():
    if not ENV_LOCAL.is_file():
        raise PullError(f"missing {ENV_LOCAL} — see infra/terraform/README.md's bootstrap table")
    values = {}
    for line in ENV_LOCAL.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def _load_tfvars(path):
    """Minimal `key = "value"` reader (ignores comments/blank lines)."""
    if not path.is_file():
        raise PullError(
            f"missing {path} -- copy it from {path}.example and fill in railway_project_id "
            f"+ every service_id_<key> (non-secret UUIDs from the Railway dashboard) first"
        )
    out = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        m = re.match(r'\s*([A-Za-z_][A-Za-z0-9_]*)\s*=\s*"([^"]*)"', line)
        if m:
            out[m.group(1)] = m.group(2)
    return out


def _discover_service_keys():
    """Service keys from railway-services.json (the manifest push_railway_variables.py uses)."""
    if not MANIFEST.is_file():
        raise PullError(f"missing {MANIFEST}")
    return list(json.loads(MANIFEST.read_text(encoding="utf-8"))["services"])


def _require_bin(name):
    """shutil.which resolves PATHEXT on Windows (railway/terraform are .cmd/.exe
    shims there); a raw subprocess call would not."""
    path = shutil.which(name)
    if not path:
        raise PullError(
            f"`{name}` not found on PATH -- this script runs on the HOST, not in a "
            f"container. `npm install -g @railway/cli` if it's the railway CLI."
        )
    return path


def _token_for(env_local, environment_name):
    specific = env_local.get(f"RAILWAY_TOKEN_{environment_name.upper()}")
    return specific or env_local.get("RAILWAY_TOKEN")


def _run_railway_variables(token, project_id, service_id, environment_name):
    env = {**os.environ, "RAILWAY_TOKEN": token, "RAILWAY_PROJECT_ID": project_id}
    proc = subprocess.run(
        [_require_bin("railway"), "variables", "--service", service_id,
         "--environment", environment_name, "--json"],
        capture_output=True, text=True, env=env,
    )
    if proc.returncode != 0:
        raise PullError(
            f"`railway variables` failed for service {service_id} ({environment_name}): {proc.stderr.strip()}"
        )
    try:
        return json.loads(proc.stdout)
    except json.JSONDecodeError as e:
        raise PullError(f"unexpected output for service {service_id} ({environment_name}): {e}\n{proc.stdout}") from e


def _emit_tfvars(result):
    """Write a paste-ready .tfvars draft grouped by scope (shared / per-env /
    env-only). Naive: one line per key (representative value); '# DIFFERS' flags
    keys whose value varies across services — split those into suffixed vars."""
    seen = {}
    for svc, entry in result.items():
        for env_name in ENVIRONMENTS:
            for k, v in (entry.get(env_name) or {}).items():
                if _RAILWAY_INJECTED_RE.match(k):
                    continue
                seen.setdefault(k, {}).setdefault(env_name, {}).setdefault(v, []).append(svc)

    lines = [
        "# GENERATED by pull_railway_variables.py --as-tfvars — a DRAFT, not a final file.",
        "# Split these lines into secrets/{shared,staging,production}.tfvars (see the",
        "# .example templates). Reconcile every '# DIFFERS' line by suffixing the var name",
        "# per service (e.g. uv_group_weekly_report). Delete this file when done.",
        "",
    ]
    for k in sorted(seen):
        tfkey = _to_tfvar_key(k)
        prod = seen[k].get("production")
        stg = seen[k].get("staging")
        prod_vals = set(prod) if prod else set()
        stg_vals = set(stg) if stg else set()

        if prod and stg and prod_vals == stg_vals and len(prod_vals) == 1:
            scope = "both envs, same value -> shared.tfvars"
        elif prod and stg:
            scope = "both envs, DIFFERS per env -> staging.tfvars / production.tfvars"
        elif prod:
            scope = "production only -> production.tfvars"
        else:
            scope = "staging only -> staging.tfvars"

        note = f"  # {scope}"
        if len(prod_vals | stg_vals) > 1:
            note += "  ## DIFFERS across services — suffix per service"

        rep_value = next(iter((prod or stg)))
        lines.append(f'{tfkey} = "{_escape_hcl(rep_value)}"{note}')

    TFVARS_OUTPUT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Wrote {TFVARS_OUTPUT_PATH} (draft — split into secrets/*.tfvars, then delete)")


def main():
    args = sys.argv[1:]
    as_tfvars = "--as-tfvars" in args
    requested = set(a for a in args if not a.startswith("-")) or None

    env_local = _load_env_local()
    if not any(env_local.get(k) for k in ("RAILWAY_TOKEN", "RAILWAY_TOKEN_STAGING", "RAILWAY_TOKEN_PRODUCTION")):
        raise SystemExit(
            f"No Railway token in {ENV_LOCAL} — set RAILWAY_TOKEN_STAGING / "
            "RAILWAY_TOKEN_PRODUCTION (preferred) or RAILWAY_TOKEN."
        )

    tfvars = _load_tfvars(SHARED_TFVARS)
    project_id = tfvars.get("railway_project_id")
    if not project_id:
        raise PullError(f"railway_project_id is empty in {SHARED_TFVARS}")

    service_keys = _discover_service_keys()
    if requested:
        unknown = requested - set(service_keys)
        if unknown:
            raise SystemExit(f"Unknown service key(s): {', '.join(sorted(unknown))}. Known: {', '.join(service_keys)}")
        service_keys = [k for k in service_keys if k in requested]

    result = {}
    for key in service_keys:
        service_id = tfvars.get(f"service_id_{key}")
        if not service_id:
            print(f"::warning:: service_id_{key} not set in {SHARED_TFVARS.name} -- skipping {key}", file=sys.stderr)
            continue

        entry = {"service_id": service_id}
        for env_name in ENVIRONMENTS:
            token = _token_for(env_local, env_name)
            if not token:
                raise SystemExit(f"No token for {env_name} — set RAILWAY_TOKEN_{env_name.upper()} (or RAILWAY_TOKEN)")
            entry[env_name] = _run_railway_variables(token, project_id, service_id, env_name)
            print(f"  pulled {key} ({env_name}): {len(entry[env_name])} variables")
        result[key] = entry

    OUTPUT_PATH.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nWrote {OUTPUT_PATH}")
    if as_tfvars:
        _emit_tfvars(result)
    print("⚠️  These file(s) hold real variable values (secrets included) in plaintext —")
    print("    treat like infra/terraform/railway/.env; never share/commit, delete when done.")


if __name__ == "__main__":
    try:
        main()
    except PullError as e:
        raise SystemExit(str(e))
