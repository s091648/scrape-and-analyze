# Phase 1 Data Model: Infrastructure as Code for Deployment Environments

This feature has no application database entities — its "data model" is the
shape of the declarative configuration itself.

**Revision 2 (2026-08-28)**: one flat root config (`infra/terraform/`), no
per-environment directories, no `railway_service`, no `environments/shared`
workspace. See `plan.md`'s "Revision 2" section.

## Service Definition → `module "<svc>"` instance (`modules/railway-variables`)

One module instance per app service (10), in `infra/terraform/services/<svc>.tf`.
Railway *service objects* are NOT modelled — they stay manually managed on
Railway; only their variables are.

| Field | Type | Notes |
|---|---|---|
| `service_id` | string | Stable Railway service UUID, from `var.service_id_<svc>` (set in `secrets/shared.tfvars`) |
| `environment_id` | string | `var.railway_environment_id` (set in `secrets/<env>.tfvars`) |
| `variables` | `map(object({ value, sensitive }))` | `merge()` of the `local.shared.*` groups this service uses (`shared.tf`) + its own entries. `value == null` ⇒ the key is skipped for this environment |

**Validation rule** (FR-001/FR-010): every service in scope has a
`module "<svc>"` block in `services/`. A partially-migrated state is expressed
by which keys appear in a service's merged `variables` map — not by a
`managed: true/false` flag (revision 2 removed that concept).

## Environment → HCP Terraform workspace, selected by `TF_WORKSPACE`

| Field | Type | Notes |
|---|---|---|
| `name` | string | `staging` \| `production` — the HCP workspace name AND `var.app_env` |
| `railway_environment_id` | string | `var.railway_environment_id`, set in `secrets/<env>.tfvars`. Not read back from Railway (the provider has no data source) |
| workspace selection | — | `backend.tf` uses `cloud { workspaces { tags = [...] } }` (no hard-coded `name`); `TF_WORKSPACE=<env>` picks. `terraform.workspace` then reflects the real name |

**Isolation rule** (FR-003): each Environment is a distinct HCP workspace with
its own state — applying one cannot touch another's resources. The
`check "workspace_matches_env"` block (`locals.tf`) additionally asserts
`terraform.workspace == var.app_env` so a mismatched `TF_WORKSPACE` /
`-var-file` pair fails loudly.

## Environment Variable → `railway_variable` / `github_actions_(secret|variable)`

A variable belongs to one Service Definition (Railway) or the CI Credential
Store (GitHub) within one Environment. Every kind is Terraform-enforced.

| Kind | Representation | Value source |
|---|---|---|
| Plain config | `railway_variable` / `github_actions_variable` | A `var.*`, supplied via `-var-file` (`secrets/*.tfvars`) — non-secret ones may be typed there directly |
| Secret | `railway_variable` / `github_actions_secret` / `_environment_secret` | A `sensitive = true` `var.*`, supplied via `-var-file` / `TF_VAR_*` — never a literal in a tracked file (FR-004a) |
| Reference | `railway_variable` only | A Railway template string (`${{ Redis.REDIS_URL }}`); plain string to Terraform, resolved server-side by Railway (FR-014). `$` escaped as `$${` in `.tfvars` |

**Layering**: `-var-file=secrets/shared.tfvars -var-file=secrets/<env>.tfvars`,
later wins. A key set only in `<env>.tfvars` (leaving the shared value `null`)
is a clean per-environment difference. In CI the three `.tfvars` files are
materialized from base64 GitHub Actions secrets `TF_TFVARS_SHARED` / `_STAGING`
/ `_PRODUCTION`.

**State transitions**: create → update (value change, in place) → destroy
(key removed from the merged map). FR-011's destroy-vs-modify distinction is
native `terraform plan` output (`+`/`~`/`-`).

## Applied State → HCP Terraform remote state (per workspace)

Each workspace's Terraform state, hosted by HCP Terraform. Contains plaintext
secret values once applied — hence FR-004's encrypted, access-restricted remote
backend requirement. Drift detection (FR-009) is `terraform plan`'s native
comparison (`make terraform-drift-check ENV=<env>`, or `terraform.yml` in
`mode: drift`).

## CI Credential Store → `module "github_ci_repo"` + `module "github_ci_env"`

Repo-level (`github_ci_repo`) and environment-scoped
(`github_ci_env`, `github_environment_name = "scraper / ${var.app_env}"`)
instances of `modules/github-ci-config`.

| Field | Type | Notes |
|---|---|---|
| `secrets` | `map(string)` | Keyed by name (`CLAUDE_API_KEY`, `DATABASE_URL`, …); values from `var.gh_*`, `null` skips |
| `variables` | `map(string)` | Keyed by name (`RAILWAY_SERVICE_ID_*` derived from `var.service_id_*`, `BACKEND_URL`, …) |

**Exclusion** (FR-013): the three bootstrap credentials — `TF_API_TOKEN`,
`TF_GITHUB_TOKEN`, `TF_RAILWAY_TOKEN` — are never entries here; they authenticate
the tool to its state backend / GitHub / Railway and cannot be self-managed.
