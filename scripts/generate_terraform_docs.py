"""Generate a Terraform services/variables catalog from infra/terraform/ via static
HCL2 parsing (python-hcl2) — same static-analysis philosophy as
scripts/generate_db_schema.py / generate_uml.py / generate_exceptions.py, except the
"source code" here is HCL rather than Python: this module never runs `terraform`
itself (no state, no provider credentials needed), it only parses the *declared*
`environments/{staging,production}/main.tf` files as text/syntax.

Output:
  - site/public/guide/architecture/terraform-services-data.json

See specs/025-iac-provisioning/ for the Terraform layout this parses
(railway-service / railway-variables / github-ci-config modules).
"""
import json
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path

import hcl2

REPO_ROOT = Path(__file__).resolve().parent.parent
TF_ENVIRONMENTS_DIR = REPO_ROOT / "infra" / "terraform" / "environments"
OUTPUT_DIR = REPO_ROOT / "site" / "public" / "guide" / "architecture"

ENVIRONMENTS = ["production", "staging"]

RAILWAY_SERVICE_SOURCE = "../../modules/railway-service"
RAILWAY_VARIABLES_SOURCE = "../../modules/railway-variables"
GITHUB_CI_CONFIG_SOURCE = "../../modules/github-ci-config"


class TerraformDocsParseError(Exception):
    pass


@dataclass
class VarEntry:
    name: str
    managed: bool
    sensitive: bool = False
    # Only ever populated for managed + non-sensitive entries (FR-004a: a managed
    # sensitive value is only ever injected via TF_VAR_* at apply time, and a
    # non-managed/baseline value's live value is intentionally left untracked here
    # via lifecycle.ignore_changes) — never a real secret.
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
    source_repo: str | None = None
    root_directory: str | None = None
    cron_schedule: str | None = None
    environments: dict = field(default_factory=dict)  # env name -> ServiceEnvVariables


@dataclass
class GithubCiConfigInfo:
    key: str
    environment: str
    scope: str  # "repo" | "environment"
    github_environment_name_ref: str | None
    secrets: list = field(default_factory=list)
    variables: list = field(default_factory=list)


# ─── HCL value cleanup ──────────────────────────────────────────────────────────

_QUOTED_LITERAL = re.compile(r'^"(.*)"$', re.DOTALL)
_INTERPOLATION = re.compile(r'^\$\{(.*)\}$', re.DOTALL)


def _clean_scalar(raw):
    """python-hcl2 keeps literal string values wrapped in their source-text quotes
    (`'"foo"'`) and interpolations as `'${expr}'` — unwrap both into plain display
    text. Non-string values (bool, already-parsed dict/list) pass through as-is."""
    if not isinstance(raw, str):
        return raw
    m = _QUOTED_LITERAL.match(raw)
    if m:
        return m.group(1)
    m = _INTERPOLATION.match(raw)
    if m:
        return m.group(1)
    return raw


def _strip_label(label):
    """Block labels (module/resource names) come back HCL-quoted too, e.g. '"foo"'."""
    return _clean_scalar(label)


# ─── HCL parsing ────────────────────────────────────────────────────────────────

def _load_main_tf(env):
    path = TF_ENVIRONMENTS_DIR / env / "main.tf"
    if not path.is_file():
        raise TerraformDocsParseError(f"missing {path}")
    with path.open(encoding="utf-8") as f:
        try:
            return hcl2.load(f)
        except Exception as e:  # python-hcl2 raises lark exceptions, not a common base
            raise TerraformDocsParseError(f"{path}: failed to parse — {e}") from e


def _iter_modules(parsed):
    """Yields (module_name, module_body) for every `module "x" {...}` block."""
    for entry in parsed.get("module", []):
        for label, body in entry.items():
            yield _strip_label(label), body


def _source_of(module_body):
    return _clean_scalar(module_body.get("source", ""))


def _variables_to_entries(variables_map, force_sensitive=None):
    """`force_sensitive` overrides the (possibly absent) `sensitive` field for
    github-ci-config's `secrets`/`variables` maps, whose module schema has no
    `sensitive` key at all — a `secrets` entry is a GitHub Actions Secret and thus
    always sensitive by definition, and a `variables` entry is always non-sensitive
    by definition (railway-variables' schema, which does carry a real per-entry
    `sensitive` field, passes force_sensitive=None to use it as declared)."""
    entries = []
    for name, spec in (variables_map or {}).items():
        managed = bool(spec.get("managed", False))
        sensitive = bool(spec.get("sensitive", False)) if force_sensitive is None else force_sensitive
        value = _clean_scalar(spec.get("value")) if (managed and not sensitive) else None
        entries.append(VarEntry(name=name, managed=managed, sensitive=sensitive, value=value))
    entries.sort(key=lambda e: e.name)
    return entries


def _service_env_variables(entries):
    return ServiceEnvVariables(
        variables=[asdict(e) for e in entries],
        managed_count=sum(1 for e in entries if e.managed),
        sensitive_count=sum(1 for e in entries if e.sensitive),
    )


# ─── Assembly ───────────────────────────────────────────────────────────────────

def generate():
    parsed_by_env = {env: _load_main_tf(env) for env in ENVIRONMENTS}

    services: dict[str, ServiceInfo] = {}

    # Pass 1: railway-service registrations only ever live in production
    # (research.md §9 — a railway_service resource reads/writes only the
    # project's primary environment).
    for name, body in _iter_modules(parsed_by_env["production"]):
        if _source_of(body) != RAILWAY_SERVICE_SOURCE:
            continue
        services[name] = ServiceInfo(
            key=name,
            service_name=_clean_scalar(body.get("service_name")),
            source_repo=_clean_scalar(body.get("source_repo")),
            root_directory=_clean_scalar(body.get("root_directory")),
            cron_schedule=_clean_scalar(body.get("cron_schedule")),
        )

    # Pass 2: railway-variables instances in each environment, matched back to
    # their service by module-name convention (`<service_key>_variables`).
    github_ci: list[GithubCiConfigInfo] = []
    for env in ENVIRONMENTS:
        for name, body in _iter_modules(parsed_by_env[env]):
            source = _source_of(body)

            if source == RAILWAY_VARIABLES_SOURCE:
                service_key = name[: -len("_variables")] if name.endswith("_variables") else name
                svc = services.get(service_key)
                if svc is None:
                    # A railway-variables instance with no matching railway-service
                    # module — shouldn't happen given the current layout, but don't
                    # silently drop it: surface it as its own entry.
                    svc = services[service_key] = ServiceInfo(key=service_key)
                entries = _variables_to_entries(body.get("variables"))
                svc.environments[env] = asdict(_service_env_variables(entries))

            elif source == GITHUB_CI_CONFIG_SOURCE:
                env_name_ref = body.get("github_environment_name")
                github_ci.append(GithubCiConfigInfo(
                    key=name,
                    environment=env,
                    scope="repo" if env_name_ref is None else "environment",
                    github_environment_name_ref=_clean_scalar(env_name_ref) if env_name_ref else None,
                    secrets=[asdict(e) for e in _variables_to_entries(body.get("secrets"), force_sensitive=True)],
                    variables=[asdict(e) for e in _variables_to_entries(body.get("variables"), force_sensitive=False)],
                ))

    service_list = [asdict(s) for s in services.values()]
    service_list.sort(key=lambda s: s["key"])

    return {
        "generated_from": [
            f"infra/terraform/environments/{env}/main.tf" for env in ENVIRONMENTS
        ],
        "services": service_list,
        "github_ci": [asdict(g) for g in github_ci],
    }


def main():
    result = generate()
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    out_path = OUTPUT_DIR / "terraform-services-data.json"
    out_path.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Wrote {out_path} ({len(result['services'])} services, {len(result['github_ci'])} github-ci-config instances)")


if __name__ == "__main__":
    main()
