# Phase 1 Data Model: Infrastructure as Code for Deployment Environments

This feature has no application database entities — its "data model" is the shape of the declarative configuration itself. Each entity below maps a spec Key Entity to its concrete Terraform representation.

**Revised during implementation** (research.md §9, contracts/railway-service-module.md): `railway_service` and `railway_variable` turned out to need separate modules, not one combined `railway-service` module as originally described below — `railway_service` is single-instance-per-service (declared only in production), while `railway_variable` is genuinely per-environment. The entity descriptions below still hold; only the Terraform module boundary changed.

## Service Definition → `module "railway-service"` instance (registration only, production-only) + `module "railway-variables"` instance (per environment)

One module instance per app service (10 total per environment: `dashboard-backend`, `dashboard-frontend`, `storybook`, `scrape-and-analyze`, `chatbot-plugin`, `fastembed`, `weekly-report`, `refresh-metrics`, `rag-backfill`, `dedup-reconcile`).

| Field | Type | Notes |
|---|---|---|
| `service_name` | string | Matches the existing Railway service name (e.g. `scrape-and-analyze`) |
| `railway_project_id` | string | Shared across all services in an environment; passed from the root config |
| `railway_environment_id` | string | The environment's Railway environment ID (see Environment below) |
| `config_path` | string | Points at the service's existing `railway.toml` (e.g. `src/railway.toml`) for build/start settings — **not** re-declared here, per research.md §6 |
| `variables` | map(object) | Keyed by variable name; see Environment Variable below |

**Validation rules** (from FR-001/FR-010): every service in the "Scale/Scope" list above must have a corresponding module instance in both `environments/staging/main.tf` and `environments/production/main.tf` once fully migrated; a service not yet migrated (FR-010's incremental path) simply has no module instance yet — its absence from Terraform is the unambiguous signal that it's still manually managed, with no separate "managed: true/false" flag needed.

## Environment → HCP Terraform workspace + `railway_environment` reference

| Field | Type | Notes |
|---|---|---|
| `name` | string | `staging` \| `production` — matches `ci.yml`'s/`release.yml`'s existing `scraper / staging` / `scraper / production` GitHub Environment names |
| `railway_environment_id` | string | Read via a `railway_environment` data source (or imported, if the environment itself predates this feature — expected, since staging/production already exist) — this feature does not create new Railway environments (per spec Assumptions: "does not introduce new environment tiers") |
| `terraform_workspace` | string | `scrape-analyzer-staging` \| `scrape-analyzer-production` — one-to-one with `name`, giving state isolation (FR-003) at the backend level, not just via Terraform variables |

**Isolation rule** (FR-003): because each Environment is a distinct HCP Terraform workspace with its own state, applying one environment structurally cannot touch another's resources — isolation is enforced by the backend, not by convention.

## Environment Variable → `railway_variable` / `github_actions_secret` / `github_actions_variable`

A variable belongs to exactly one Service Definition (Railway-side) or the CI Credential Store (GitHub-side) within exactly one Environment, and is exactly one of three kinds:

| Kind | Representation | Value source |
|---|---|---|
| **Plain config** | `railway_variable` (Railway-side) or `github_actions_variable` (GitHub-side) | Literal value in `terraform.tfvars`, safe to commit |
| **Secret** | `railway_variable` or `github_actions_secret`/`github_actions_environment_secret` | Injected at apply time via `TF_VAR_*` from the existing GitHub Actions secrets store (FR-004a) — never literal in any `.tf`/`.tfvars` file |
| **Reference** | `railway_variable` only | Literal value is a Railway template string (e.g. `${{Redis.REDIS_URL}}`); resolved server-side by Railway regardless of how the variable was set (FR-014) — from Terraform's point of view this is just a plain-config string, but it's called out as its own kind because its *meaning* depends on a resource this feature does not manage |

**State transitions**: none in the traditional sense — a variable's lifecycle is create → update (value change, in place) → destroy (removed from declaration). FR-011 requires destroy/replace to be visually distinguishable from create/update in the `terraform plan` output, which is native `terraform plan` behavior (`+`/`~`/`-` symbols) and needs no additional design.

## Applied State → HCP Terraform remote state (per workspace)

Not a custom entity — this *is* each workspace's Terraform state file, hosted by HCP Terraform. Contains the full resource graph including plaintext secret values (research.md §4), which is exactly why FR-004 requires it to live in an encrypted, access-restricted remote backend rather than the repository. Drift detection (FR-009) is `terraform plan`'s native comparison between this record and the provider's live read of actual resource state — no custom drift-tracking mechanism is needed.

## CI Credential Store → `module "github-ci-config"` instance

One module instance per Environment (mirroring the existing `scraper / staging` / `scraper / production` GitHub Environments used in `ci.yml`/`release.yml`'s `environment:` key) plus optionally one repo-level (non-environment-scoped) instance for secrets/variables not tied to either environment (e.g. `CODECOV_TOKEN`, `GIST_SECRET`, which today are plain repo secrets, not environment-scoped).

| Field | Type | Notes |
|---|---|---|
| `github_environment_name` | string \| null | `scraper / staging`, `scraper / production`, or null for repo-level | 
| `secrets` | map(string), sensitive | Keyed by secret name (e.g. `RAILWAY_TOKEN`, `DATABASE_URL`); values injected via `TF_VAR_*`, never literal (FR-004a) |
| `variables` | map(string) | Keyed by variable name (e.g. `RAILWAY_SERVICE_ID_DASHBOARD_BACKEND`); literal values in `terraform.tfvars`, safe to commit |

**Exclusion** (FR-013): `TF_API_TOKEN` and the GitHub PAT used by this module's own provider block are never themselves entries in `secrets` above — they are the two standing bootstrap credentials from research.md §5, created and stored manually outside this module's scope.
