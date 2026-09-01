"""Push (or --check) every Railway service's environment variables from the
tfvars files, using the Railway CLI — the reliable replacement for the
terraform-community-providers/railway variable resources (025-iac-provisioning
Option A, 2026-08-31).

Structure (which service gets which vars) lives in
  infra/terraform/railway/railway-services.json
Values live in
  infra/terraform/railway/secrets/railway-{shared,<env>}.tfvars   (per-env wins)
  + secrets/github-{shared,<env>}.tfvars  for service_id_* / gh_env_railway_token

Per service: one `railway variables --set ... --skip-deploys` call (atomic, no
per-variable redeploy), then a single `railway redeploy`. Empty/missing values
are skipped (Railway does not store empty vars). "$${{ ... }}" reference strings
in the tfvars are un-escaped to "${{ ... }}" before sending.

Runs on the HOST (needs the `railway` CLI). The Railway token is
`gh_env_railway_token` from secrets/<env>.tfvars — the environment-scoped project
token (the same one CI's deploy jobs / the `scraper / <env>` GitHub Environment
use; `railway variables` rejects the account-level token). Override with the
RAILWAY_TOKEN env var. Stdlib only.

    python scripts/push_railway_variables.py --env staging [SERVICE ...]
    python scripts/push_railway_variables.py --env staging --check    # exit 2 on drift
    python scripts/push_railway_variables.py --env staging --prune    # also delete Railway vars not in manifest/tfvars
    python scripts/push_railway_variables.py --env production --no-redeploy

railway-services.json may carry an "unmanaged_all": [KEY, ...] list and per-service
"unmanaged": [KEY, ...] — RAILWAY var names deliberately left to manual/other
management: never resolved, never flagged as drift, never pruned.
"""
import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
TF_DIR = REPO_ROOT / "infra" / "terraform" / "railway"
MANIFEST = TF_DIR / "railway-services.json"

RAILWAY_INJECTED = re.compile(r"^RAILWAY_")


class PushError(RuntimeError):
    pass


def _require_bin(name):
    path = shutil.which(name)
    if not path:
        raise PushError(
            f"`{name}` not found on PATH — this runs on the HOST, not a container. "
            f"`npm install -g @railway/cli` for the railway CLI."
        )
    return path


def _load_kv(path):
    """Parse `key = "value"` lines (the tfvars / .env subset we use)."""
    out = {}
    if not path.exists():
        return out
    for line in path.read_text(encoding="utf-8").splitlines():
        m = re.match(r'\s*([A-Za-z_][A-Za-z0-9_]*)\s*=\s*"([^"]*)"\s*(#.*)?$', line)
        if m:
            out[m.group(1)] = m.group(2)
            continue
        m = re.match(r'\s*([A-Za-z_][A-Za-z0-9_]*)\s*=\s*([^"#\s][^#\n]*?)\s*(#.*)?$', line)
        if m:  # bare (unquoted) value — .env style
            out[m.group(1)] = m.group(2)
    return out


def _unescape_ref(v):
    """tfvars keep Railway refs HCL-escaped as `$${{ ... }}`; Railway wants `${{ ... }}`."""
    return v.replace("$${", "${")


def _railway_token(tfvars):
    # gh_env_railway_token (secrets/<env>.tfvars) is the environment-scoped
    # project token `railway variables` needs — present locally and materialized
    # in CI. Preferred over an ambient RAILWAY_TOKEN (which, via the root
    # Makefile's `include .env`, may be an account-level token the CLI rejects).
    return tfvars.get("gh_env_railway_token") or os.environ.get("RAILWAY_TOKEN")


def _unmanaged(manifest, svc_key):
    return (set(manifest.get("unmanaged_all", []))
            | set(manifest["services"][svc_key].get("unmanaged", [])))


def _resolve(manifest, tfvars, svc_key):
    """{RAILWAY_NAME: value} for one service — groups merged first, then own keys.
    Drops entries whose tfvars value is missing or empty, and any name listed as
    unmanaged."""
    svc = manifest["services"][svc_key]
    unmanaged = _unmanaged(manifest, svc_key)
    pairs = {}
    for group in svc["groups"]:
        pairs.update(manifest["shared_groups"][group])
    pairs.update(svc["own"])

    resolved = {}
    missing = []
    for railway_name, tfvar_key in pairs.items():
        if railway_name in unmanaged:
            continue
        if tfvar_key not in tfvars:
            missing.append(tfvar_key)
            continue
        val = tfvars[tfvar_key]
        if val == "":
            continue
        resolved[railway_name] = _unescape_ref(val)
    return resolved, missing


def _railway_env(token, project_id):
    return {**os.environ, "RAILWAY_TOKEN": token, "RAILWAY_PROJECT_ID": project_id}


def _live_vars(token, project_id, service_id, env_name):
    proc = subprocess.run(
        [_require_bin("railway"), "variables", "--service", service_id,
         "--environment", env_name, "--json"],
        capture_output=True, text=True, env=_railway_env(token, project_id),
    )
    if proc.returncode != 0:
        raise PushError(f"`railway variables` failed for {service_id} ({env_name}): {proc.stderr.strip()}")
    return {k: v for k, v in json.loads(proc.stdout).items() if not RAILWAY_INJECTED.match(k)}


def _set_vars(token, project_id, service_id, env_name, resolved):
    cmd = [_require_bin("railway"), "variables", "--service", service_id,
           "--environment", env_name, "--skip-deploys"]
    for k, v in sorted(resolved.items()):
        cmd += ["--set", f"{k}={v}"]
    proc = subprocess.run(cmd, capture_output=True, text=True, env=_railway_env(token, project_id))
    if proc.returncode != 0:
        raise PushError(f"`railway variables --set` failed for {service_id} ({env_name}): {proc.stderr.strip()}")


def _redeploy(token, project_id, service_id, env_name):
    # `railway redeploy` takes only --service; the environment is fixed by the
    # (environment-scoped) token. NON-FATAL: cron/one-off services have no
    # redeployable "latest deployment" between runs — the vars are already set
    # (--skip-deploys), the service picks them up on its next run. Returns True
    # on success, False (with a warning) otherwise.
    proc = subprocess.run(
        [_require_bin("railway"), "redeploy", "--service", service_id, "--yes"],
        capture_output=True, text=True, env=_railway_env(token, project_id),
    )
    if proc.returncode != 0:
        print(f"::warning:: redeploy skipped for {service_id} ({env_name}) — vars set, "
              f"not redeployed: {proc.stderr.strip()}", file=sys.stderr)
        return False
    return True


def _delete_var(token, project_id, service_id, env_name, name):
    proc = subprocess.run(
        [_require_bin("railway"), "variable", "delete", name,
         "--service", service_id, "--environment", env_name],
        capture_output=True, text=True, env=_railway_env(token, project_id),
    )
    if proc.returncode != 0:
        raise PushError(f"`railway variable delete {name}` failed for {service_id} ({env_name}): {proc.stderr.strip()}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--env", required=True, choices=["staging", "production"])
    ap.add_argument("--check", action="store_true", help="diff live vs desired, exit 2 on drift, change nothing")
    ap.add_argument("--prune", action="store_true", help="also DELETE Railway vars not in manifest/tfvars (RAILWAY_* and `unmanaged` are kept)")
    ap.add_argument("--no-redeploy", action="store_true", help="set variables but skip the post-set redeploy")
    ap.add_argument("services", nargs="*", help="limit to these service keys (default: all)")
    args = ap.parse_args()
    env_name = args.env

    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    sec = TF_DIR / "secrets"
    tfvars = {}
    for name in ("github-shared", f"github-{env_name}", "railway-shared", f"railway-{env_name}"):
        tfvars.update(_load_kv(sec / f"{name}.tfvars"))
    if not tfvars:
        raise PushError(f"no values parsed from secrets/{{github,railway}}-{{shared,{env_name}}}.tfvars")

    project_id = tfvars.get("railway_project_id")
    if not project_id:
        raise PushError("railway_project_id missing from secrets/railway-shared.tfvars")

    token = _railway_token(tfvars)
    if not token:
        raise PushError(
            f"no Railway token — set gh_env_railway_token in secrets/{env_name}.tfvars "
            f"(the environment-scoped project token) or export RAILWAY_TOKEN"
        )

    all_services = list(manifest["services"])
    targets = args.services or all_services
    unknown = set(targets) - set(all_services)
    if unknown:
        raise PushError(f"unknown service key(s): {', '.join(sorted(unknown))}. Known: {', '.join(all_services)}")

    drift = 0
    for svc_key in targets:
        service_id = tfvars.get(manifest["services"][svc_key]["service_id_key"])
        if not service_id:
            print(f"::warning:: {manifest['services'][svc_key]['service_id_key']} not set — skipping {svc_key}", file=sys.stderr)
            continue

        resolved, missing = _resolve(manifest, tfvars, svc_key)
        if missing:
            print(f"::warning:: {svc_key}: tfvars key(s) not found, those vars skipped: {', '.join(sorted(missing))}", file=sys.stderr)
        unmanaged = _unmanaged(manifest, svc_key)

        if args.check:
            live = _live_vars(token, project_id, service_id, env_name)
            adds = sorted(k for k in resolved if k not in live)
            # `railway variable list --json` returns RESOLVED values, so a
            # reference like "${{ Redis.REDIS_URL }}" always reads back as the
            # concrete URL — not value-comparable. Only flag a ref key if absent.
            changes = sorted(
                k for k, v in resolved.items()
                if k in live and live[k] != v and "${{" not in v
            )
            removes = sorted(k for k in live if k not in resolved and k not in unmanaged)
            if adds or changes or removes:
                drift += 1
                print(f"DRIFT {svc_key} ({env_name}):")
                for k in adds:
                    print(f"  + {k}")
                for k in changes:
                    print(f"  ~ {k}")
                for k in removes:
                    print(f"  - {k}  (on Railway, not in manifest/tfvars — `--prune` deletes it)")
            else:
                print(f"ok    {svc_key} ({env_name}): {len(resolved)} vars in sync")
            continue

        print(f"{svc_key} ({env_name}): setting {len(resolved)} vars ...")
        _set_vars(token, project_id, service_id, env_name, resolved)

        pruned = []
        if args.prune:
            live = _live_vars(token, project_id, service_id, env_name)
            for k in sorted(k for k in live if k not in resolved and k not in unmanaged):
                _delete_var(token, project_id, service_id, env_name, k)
                pruned.append(k)
            if pruned:
                print(f"  pruned: {', '.join(pruned)}")

        # manifest "redeploy": false -> known cron/one-off service, skip.
        if not args.no_redeploy and manifest["services"][svc_key].get("redeploy", True):
            if _redeploy(token, project_id, service_id, env_name):
                print(f"  redeployed {svc_key}")

    if args.check and drift:
        print(f"\n{drift} service(s) drifted.", file=sys.stderr)
        raise SystemExit(2)
    print("\ndone.")


if __name__ == "__main__":
    try:
        main()
    except PushError as e:
        raise SystemExit(f"push_railway_variables: {e}")
