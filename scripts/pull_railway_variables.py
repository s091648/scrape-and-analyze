"""Read-only helper for specs/025-iac-provisioning's shared-variable migration.

Pulls every service's CURRENT live environment variable values (both staging
and production) via the Railway CLI (`railway variables --json`) and writes
them to a single local, gitignored inventory file.

Why this exists: ~150 of this repo's Terraform-declared variables are still
`managed = false` (baseline — Terraform tracks the name, but leaves the live
value alone). Promoting one to `managed = true` requires supplying its EXACT
current value via `TF_VAR_*` on the very first apply after the flip, or that
apply will silently overwrite the live value with whatever's supplied instead
(FR-004a's "no manual dashboard edits" only holds if Terraform's own values
are correct in the first place). This script exists to make "what's the
current live value" a fast lookup instead of ten trips to the Railway
dashboard, before writing that flip's HCL by hand.

Never calls `terraform` and never writes to Railway — pull-only, and not part
of any CI workflow.

⚠️ SECURITY: the output file concentrates every service's variable values
(including every secret) into ONE local file — treat it with the same care as
infra/terraform/.env.local (gitignored below, never share/commit, delete it
once you're done cross-referencing values for a migration batch).

Requires: `railway` CLI on PATH (`npm install -g @railway/cli`) and
infra/terraform/.env.local populated per infra/terraform/README.md's bootstrap
table. Confirmed the hard way: the account-level RAILWAY_TOKEN that works fine
for Terraform's provider (broader — it also creates/updates resources) gets
"Invalid RAILWAY_TOKEN" from `railway variables` specifically — that read
apparently needs a project-scoped, environment-bound token, the same *shape*
as ci.yml/release.yml's per-GitHub-Environment RAILWAY_TOKEN secret (but this
script never touches those — generate your own via Railway dashboard ->
Project Settings -> Tokens, scoped to that one environment, purely for local
use). Add each as its own line in .env.local:
    RAILWAY_TOKEN_STAGING=...
    RAILWAY_TOKEN_PRODUCTION=...
Falls back to the plain RAILWAY_TOKEN (account-level) per environment if its
specific one isn't set, in case that restriction turns out to be narrower
than observed (e.g. only certain services/resources).

Usage:
    python scripts/pull_railway_variables.py [SERVICE_KEY ...]
    (no args = every service found in infra/terraform/environments/production/main.tf)

Output:
    infra/terraform/.live-variables.json (gitignored)
"""
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import hcl2

REPO_ROOT = Path(__file__).resolve().parent.parent
TF_DIR = REPO_ROOT / "infra" / "terraform"
ENV_LOCAL = TF_DIR / ".env.local"
OUTPUT_PATH = TF_DIR / ".live-variables.json"
ENVIRONMENTS = ["production", "staging"]


class PullError(Exception):
    pass


def _load_env_local():
    """Minimal KEY=VALUE parser for the same file Makefile's TF_LOAD_ENV sources —
    avoids adding a python-dotenv dependency for one file."""
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


def _unwrap(value):
    """python-hcl2 keeps a literal string's source-text quotes (e.g. '"foo"') —
    strip them for a plain literal like a project ID."""
    if isinstance(value, str) and value.startswith('"') and value.endswith('"'):
        return value[1:-1]
    return value


def _load_project_id():
    tfvars_path = TF_DIR / "environments" / "production" / "terraform.tfvars"
    with tfvars_path.open(encoding="utf-8") as f:
        return _unwrap(hcl2.load(f)["railway_project_id"])


def _discover_service_keys():
    """Service module names from production/main.tf's railway-service instances —
    reuses the exact same static-parsing approach as generate_terraform_docs.py."""
    main_tf = TF_DIR / "environments" / "production" / "main.tf"
    with main_tf.open(encoding="utf-8") as f:
        parsed = hcl2.load(f)
    keys = []
    for entry in parsed.get("module", []):
        for label, body in entry.items():
            if body.get("source", "").strip('"') == "../../modules/railway-service":
                keys.append(label.strip('"'))
    return keys


def _require_bin(name):
    """shutil.which (unlike a raw subprocess.run([name, ...])) correctly resolves
    PATHEXT on Windows — railway/terraform are installed as .cmd/.exe shims there,
    and Popen/CreateProcess doesn't append extensions the way a shell does."""
    path = shutil.which(name)
    if not path:
        raise PullError(f"`{name}` not found on PATH")
    return path


def _token_for(env_local, environment_name):
    """Prefer a per-environment project token (RAILWAY_TOKEN_STAGING /
    RAILWAY_TOKEN_PRODUCTION) — see this module's docstring for why. Falls back
    to the plain account-level RAILWAY_TOKEN if the specific one isn't set."""
    specific = env_local.get(f"RAILWAY_TOKEN_{environment_name.upper()}")
    return specific or env_local.get("RAILWAY_TOKEN")


def _run_railway_variables(token, project_id, service_id, environment_name):
    # subprocess.run's env= REPLACES the process environment wholesale rather than
    # extending it — merge onto os.environ or the resolved binary's own runtime
    # deps (e.g. node, for the npm-installed railway CLI) won't be found either.
    env = {
        **os.environ,
        "RAILWAY_TOKEN": token,
        "RAILWAY_PROJECT_ID": project_id,
    }
    proc = subprocess.run(
        [_require_bin("railway"), "variables", "--service", service_id, "--environment", environment_name, "--json"],
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


def main():
    requested = set(sys.argv[1:]) or None

    env_local = _load_env_local()
    if not any(env_local.get(k) for k in ("RAILWAY_TOKEN", "RAILWAY_TOKEN_STAGING", "RAILWAY_TOKEN_PRODUCTION")):
        raise SystemExit(
            "No Railway token found in infra/terraform/.env.local — set RAILWAY_TOKEN_STAGING / "
            "RAILWAY_TOKEN_PRODUCTION (preferred) or RAILWAY_TOKEN. See this script's docstring."
        )

    project_id = _load_project_id()
    service_keys = _discover_service_keys()
    if requested:
        unknown = requested - set(service_keys)
        if unknown:
            raise SystemExit(f"Unknown service key(s): {', '.join(sorted(unknown))}. Known: {', '.join(service_keys)}")
        service_keys = [k for k in service_keys if k in requested]

    # Service IDs aren't literals anywhere in the .tf files (they were
    # `terraform import`-ed) — resolve them the same way staging's own config
    # does: read production's Terraform state output. `terraform output` only
    # reads already-fetched state (HCP Terraform), it never touches Railway's
    # API, so this adds zero Railway rate-limit cost.
    tf_env = {**os.environ, **env_local}
    tf_env["TF_TOKEN_app_terraform_io"] = env_local.get("TF_API_TOKEN", "")
    proc = subprocess.run(
        [_require_bin("terraform"), f"-chdir={TF_DIR / 'environments' / 'production'}", "output", "-json", "service_ids"],
        capture_output=True, text=True, env=tf_env,
    )
    if proc.returncode != 0:
        raise SystemExit(f"`terraform output service_ids` failed — run `make terraform-plan ENV=production` once first if this is a fresh checkout:\n{proc.stderr}")
    service_ids_by_name = json.loads(proc.stdout)  # e.g. {"dashboard-backend": "<id>", ...}

    result = {}
    for key in service_keys:
        # main.tf's output "service_ids" block maps hyphenated names -> module keys;
        # reconstruct that same name here rather than re-parsing the output block.
        hyphenated = key.replace("_", "-")
        service_id = service_ids_by_name.get(hyphenated)
        if not service_id:
            print(f"::warning:: no service_ids entry for '{hyphenated}' (module {key}) — skipping", file=sys.stderr)
            continue

        entry = {"service_id": service_id}
        for env_name in ENVIRONMENTS:
            token = _token_for(env_local, env_name)
            if not token:
                raise SystemExit(f"No token available for {env_name} — set RAILWAY_TOKEN_{env_name.upper()} (or RAILWAY_TOKEN) in infra/terraform/.env.local")
            entry[env_name] = _run_railway_variables(token, project_id, service_id, env_name)
            print(f"  pulled {key} ({env_name}): {len(entry[env_name])} variables")
        result[key] = entry

    OUTPUT_PATH.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nWrote {OUTPUT_PATH}")
    print("⚠️  This file holds every pulled service's real variable values (including secrets) in plaintext.")
    print("    Treat it like infra/terraform/.env.local — never share/commit it, delete it once this migration batch is done.")


if __name__ == "__main__":
    try:
        main()
    except PullError as e:
        raise SystemExit(str(e))
