"""Generate the infra services/variables catalog for the VitePress infra page.

Post 025-iac-provisioning "Revision 6" the infra is split across two engines,
and this catalog reads one source per engine — none of them requires running
`terraform` / `railway` or any credentials:

  1. Railway service ENV VARS + DEPLOY CONFIG — `.railway/railway.ts`
     (+ `infra/terraform/railway/railway-services.json`, retained after T6-09
     purely as the var-name / tfvars-key map + this catalog's source; the
     routing authority is `railway.ts`). Managed by `railway config apply`,
     NOT Terraform. Deploy config (cronSchedule, startCommand,
     restartPolicyType, privateNetworkEndpoint) is regex-scraped from
     `railway.ts` here so the page can surface it.

  2. GitHub Actions secrets / variables — `infra/terraform/railway/github-ci.tf`,
     still Terraform-managed. Static `python-hcl2` parse, never runs `terraform`.

Output: site/public/guide/architecture/terraform-services-data.json
(consumed by site/.vitepress/theme/TerraformServicesViewer.vue).
"""
import json
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path

import hcl2

REPO_ROOT = Path(__file__).resolve().parent.parent
TF_ROOT = REPO_ROOT / "infra" / "terraform" / "railway"
MANIFEST = TF_ROOT / "railway-services.json"
GITHUB_CI_TF = TF_ROOT / "github-ci.tf"
RAILWAY_TS = REPO_ROOT / ".railway" / "railway.ts"
OUTPUT_DIR = REPO_ROOT / "site" / "public" / "guide" / "architecture"

ENVIRONMENTS = ["production", "staging"]
GITHUB_CI_CONFIG_SOURCE = "./modules/github-ci-config"

# `railway.ts` service("<display name>", …) → railway-services.json key, for the
# two whose normalised display name doesn't match their manifest key.
_TS_NAME_ALIASES = {"backfill_rag": "rag_backfill", "storybook_ui": "storybook"}

# RAILWAY_* variable names that hold secrets (rendered as `preserve()` /
# `need()`-with-a-secret-tfvar in railway.ts). Kept here so the page can still
# show a sensitive count without decrypting anything.
SENSITIVE_KEYS = {
    "GRAFANA_API_KEY", "SENTRY_DSN", "RAG_GEMINI_API_KEY", "VECTOR_DB_PASSWORD",
    "TELEGRAM_BOT_TOKEN", "FIXIE_URL", "DATABASE_URL", "CACHE_REDIS_URL",
    "SEARCH_INDEX_REDIS_URL", "GEMINI_API_KEY", "OPENROUTER_API_KEY",
    "GITHUB_PACKAGE_TOKEN", "CHAT_SERVICE_API_KEY", "MAXMIND_LICENSE_KEY",
    "NEXTAUTH_SECRET", "REDIS_URL", "GOOGLE_CLIENT_ID", "GOOGLE_CLIENT_SECRET",
    "GRAFANA_SA_TOKEN", "HF_TOKEN", "R2_ACCESS_KEY_ID", "R2_SECRET_ACCESS_KEY",
    "RESEND_API_KEY",
}


class TerraformDocsParseError(Exception):
    pass


@dataclass
class VarEntry:
    name: str
    # Railway service vars: declared in railway.ts (True) vs hand-managed on
    # Railway / `preserve()`d (False). GitHub-CI vars: Terraform-managed (True).
    managed: bool = True
    sensitive: bool = False
    value: str | None = None


@dataclass
class ServiceEnvVariables:
    variables: list = field(default_factory=list)
    managed_count: int = 0
    sensitive_count: int = 0


@dataclass
class ServiceInfo:
    key: str
    service_name: str | None = None
    # Deploy config, scraped from .railway/railway.ts (production values;
    # staging cron is an "0 0 1 1 1" placeholder — services are torn down /
    # revived per-PR). None where railway.ts sets nothing (image CMD / no cron).
    cron_schedule: str | None = None
    start_command: str | None = None
    restart_policy: str | None = None
    network_endpoint: str | None = None
    deploy_config_source: str | None = None
    environments: dict = field(default_factory=dict)


@dataclass
class GithubCiConfigInfo:
    key: str
    environment: str
    scope: str
    github_environment_name_ref: str | None
    secrets: list = field(default_factory=list)
    variables: list = field(default_factory=list)


def _clean_scalar(raw):
    if isinstance(raw, str) and len(raw) >= 2 and raw[0] == '"' and raw[-1] == '"':
        return raw[1:-1]
    if isinstance(raw, str) and raw.startswith("${") and raw.endswith("}"):
        return raw[2:-1]
    return raw


# ── Railway service env vars (railway-services.json) ─────────────────────────

def _manifest_var_entries(manifest, svc_key):
    svc = manifest["services"][svc_key]
    names = set()
    for group in svc["groups"]:
        names.update(manifest["shared_groups"][group])
    own = svc["own"]
    names.update(own.keys() if isinstance(own, dict) else own)
    unmanaged = set(manifest.get("unmanaged_all", [])) | set(svc.get("unmanaged", []))
    return sorted(
        (
            VarEntry(name=n, managed=(n not in unmanaged), sensitive=(n in SENSITIVE_KEYS))
            for n in names
        ),
        key=lambda e: e.name,
    )


def _service_env_variables(entries):
    return ServiceEnvVariables(
        variables=[asdict(e) for e in entries],
        managed_count=sum(1 for e in entries if e.managed),
        sensitive_count=sum(1 for e in entries if e.sensitive),
    )


# ── Railway deploy config (.railway/railway.ts) ─────────────────────────────

def _normalise_ts_name(display_name):
    key = re.sub(r"[ -]+", "_", display_name.strip().lower())
    return _TS_NAME_ALIASES.get(key, key)


def _load_railway_deploy_config():
    """Regex-scrape each `service("<name>", { … })` block in .railway/railway.ts
    for its production deploy config. Best-effort: a field that isn't matched is
    left None (e.g. services whose start command is the Dockerfile CMD, or that
    have no cron). Returns {manifest_key: {cron_schedule, start_command,
    restart_policy, network_endpoint}}."""
    if not RAILWAY_TS.is_file():
        raise TerraformDocsParseError(f"missing {RAILWAY_TS}")
    text = RAILWAY_TS.read_text(encoding="utf-8")

    out = {}
    # `const x = service("NAME", {` … up to the block's own `\n  });`
    for m in re.finditer(r'service\("([^"]+)",\s*\{(.*?)\n  \}\);', text, re.S):
        display_name, body = m.group(1), m.group(2)
        key = _normalise_ts_name(display_name)

        # Production cron only comes from `cron("…")` — a bare `cronSchedule: "…"`
        # in a `prod ? … : …` is the staging "0 0 1 1 1" placeholder.
        cron = re.search(r'cron\("([^"]+)"\)', body)
        # start: "…"  |  start: prod ? "prod-cmd" : "staging-cmd"
        start = re.search(r'start:\s*(?:prod\s*\?\s*)?"([^"]+)"', body)
        restart = re.search(r'restartPolicyType:\s*"([^"]+)"', body)
        endpoint = re.search(r'privateNetworkEndpoint:\s*"([^"]+)"', body)

        out[key] = {
            "cron_schedule": cron.group(1) if cron else None,
            "start_command": start.group(1) if start else None,
            "restart_policy": restart.group(1) if restart else None,
            "network_endpoint": endpoint.group(1) if endpoint else None,
        }
    return out


# ── GitHub Actions secrets / variables (github-ci.tf) ───────────────────────

def _ci_entries(variables_map, force_sensitive):
    out = [VarEntry(name=n, sensitive=force_sensitive) for n in (variables_map or {})]
    out.sort(key=lambda e: e.name)
    return out


def _humanize(key):
    return key.replace("_", "-")


def _load_github_ci_modules():
    if not GITHUB_CI_TF.is_file():
        raise TerraformDocsParseError(f"missing {GITHUB_CI_TF}")
    with GITHUB_CI_TF.open(encoding="utf-8") as f:
        parsed = hcl2.load(f)
    mods = []
    for entry in parsed.get("module", []):
        for label, body in entry.items():
            mods.append((_clean_scalar(label), body))
    return mods


def generate():
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    deploy_config = _load_railway_deploy_config()

    unmatched = set(manifest["services"]) - set(deploy_config)
    if unmatched:
        raise TerraformDocsParseError(
            f"railway-services.json services with no service() block in "
            f".railway/railway.ts: {sorted(unmatched)} (name map / regex out of date?)"
        )

    services = []
    for svc_key in sorted(manifest["services"]):
        entries = _manifest_var_entries(manifest, svc_key)
        dc = deploy_config[svc_key]
        has_deploy = any(dc.values())
        info = ServiceInfo(
            key=svc_key,
            service_name=_humanize(svc_key),
            cron_schedule=dc["cron_schedule"],
            start_command=dc["start_command"],
            restart_policy=dc["restart_policy"],
            network_endpoint=dc["network_endpoint"],
            deploy_config_source=".railway/railway.ts" if has_deploy else None,
        )
        # Same var set both environments (per-env value/inclusion differences
        # live in railway.ts's `prod ? … : …` and the tfvars, not the manifest).
        for env in ENVIRONMENTS:
            info.environments[env] = asdict(_service_env_variables(entries))
        services.append(asdict(info))

    github_ci = []
    for name, body in _load_github_ci_modules():
        if _clean_scalar(body.get("source", "")) != GITHUB_CI_CONFIG_SOURCE:
            continue
        env_name_ref = body.get("github_environment_name")
        ref = _clean_scalar(env_name_ref) if env_name_ref else None
        scope = "repo" if env_name_ref is None else "environment"
        for env in ENVIRONMENTS:
            github_ci.append(asdict(GithubCiConfigInfo(
                key=name,
                environment=env,
                scope=scope,
                github_environment_name_ref=(ref.replace("${var.app_env}", env) if ref else None),
                secrets=[asdict(e) for e in _ci_entries(body.get("secrets"), True)],
                variables=[asdict(e) for e in _ci_entries(body.get("variables"), False)],
            )))

    return {
        "generated_from": [
            ".railway/railway.ts",
            "infra/terraform/railway/railway-services.json",
            "infra/terraform/railway/github-ci.tf",
        ],
        "services": services,
        "github_ci": github_ci,
    }


def main():
    result = generate()
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    out_path = OUTPUT_DIR / "terraform-services-data.json"
    out_path.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Wrote {out_path} ({len(result['services'])} services, {len(result['github_ci'])} github-ci-config instances)")


if __name__ == "__main__":
    main()
