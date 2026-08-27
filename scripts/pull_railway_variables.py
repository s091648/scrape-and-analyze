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
infra/terraform/.env.local populated per infra/terraform/README.md's
bootstrap table (this script reads RAILWAY_TOKEN — the ACCOUNT-level one,
same as Terraform's provider — not the narrower per-environment CI secrets;
an account-level token can read every environment in one run).

Usage:
    python scripts/pull_railway_variables.py [SERVICE_KEY ...]
    (no args = every service found in infra/terraform/environments/production/main.tf)

Output:
    infra/terraform/.live-variables.json (gitignored)
"""
import json
import os
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


def _run_railway_variables(token, project_id, service_id, environment_name):
    # subprocess.run's env= REPLACES the process environment wholesale rather than
    # extending it — merge onto os.environ or the `railway` binary itself won't
    # even be found (PATH would be missing).
    env = {
        **os.environ,
        "RAILWAY_TOKEN": token,
        "RAILWAY_PROJECT_ID": project_id,
    }
    proc = subprocess.run(
        ["railway", "variables", "--service", service_id, "--environment", environment_name, "--json"],
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
    token = env_local.get("RAILWAY_TOKEN")
    if not token:
        raise SystemExit("RAILWAY_TOKEN not found in infra/terraform/.env.local")

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
        ["terraform", f"-chdir={TF_DIR / 'environments' / 'production'}", "output", "-json", "service_ids"],
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
