# Implementation Plan: Infrastructure as Code for Deployment Environments

**Branch**: `025-iac-provisioning` | **Date**: 2026-08-26 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/025-iac-provisioning/spec.md`

---

## Revision 2 — 2026-08-28 (structure reset)

The first implementation pass (commits `9974b06`..`2260858`) shipped a working-but-tangled
structure that the maintainer decided to redo from a clean slate. **Both HCP Terraform
workspaces were deleted** (200+ resources, almost all subtly wrong); the `scrape-analyzer`
HCP project now holds two empty workspaces, `staging` and `production`. This revision
replaces Phases 1–6 and 8 of `tasks.md`. **Phase 7 (User Story 5 — application-code env-var
centralization, `T042`–`T051`) is unaffected and stays done** — it is pure `src/`/`shared/`/
`frontend/` code with no Terraform dependency.

### What the first pass got wrong, and the fix

| First pass | Problem | Revision 2 |
|---|---|---|
| A `railway-service` module + `railway_service` resource, imported per service, declared **production-only** (the community provider's `railway_service` can only read/write the project's *primary* environment) | Forced staging↔production **asymmetry**; staging had to read service IDs from production's state via `terraform_remote_state`. Bought almost nothing — the services are created manually anyway, and build/start config lives in each `railway.toml`. | **Drop `railway_service` entirely.** Service IDs are stable UUIDs, supplied as plain `.tfvars` values. Staging and production become identical configs. |
| A third HCP workspace `scrape-analyzer-shared` (`modules/shared-variables`) holding cross-env "constants", read by staging/production via `terraform_remote_state` | Whole extra workspace + remote-state wiring for what are just constants; every output marked `sensitive = true`, which tainted `for_each` maps and needed a `nonsensitive()` workaround | **Delete the shared workspace and `modules/shared-variables`.** Shared values become a `local.shared` map (`shared.tf`) built from `var.*`, layered via `-var-file`. |
| Two mirrored root dirs `environments/{staging,production}/`, each a full copy of every per-service file | ~2× duplication; every value change touched two files | **One flat root.** Environment = HCP workspace selected by `TF_WORKSPACE` + a `secrets/<env>.tfvars` overlay. |
| ~150 `railway_variable` entries as `managed = false` "baseline" (name tracked, value left on the dashboard via `ignore_changes`) | Every service file was ~60% `IMPORTED-BASELINE-VALUE-MANAGED-OUTSIDE-TERRAFORM` placeholder noise; "IaC migration" was permanently half-done | **All variables `managed`.** One-time `terraform import` of every live value into `.tfvars`; the dashboard becomes read-only. No `managed`/`baseline` split in the module. |
| Terraform CI logic inlined in 4 places (`ci.yml` ×2, `release.yml` ×2), each 20–30 lines; a separate `terraform-staging-manual.yml` | Changing the Terraform version / adding a `TF_VAR_*` meant editing 4 spots | **One reusable `.github/workflows/terraform.yml`** (`workflow_call` inputs `mode`+`environment`, `secrets: inherit`, plus `workflow_dispatch`). Callers shrink to `uses:` + 2-line `with:`. |

Everything in `spec.md` (FR-001…FR-019, SC-001…SC-007) is still satisfied — this is a
structural simplification, not a scope change. The Constitution Check below is unchanged.

---

## Revision 3 — 2026-08-31 (service deploy-config as version-controlled `railway.toml`)

Revision 2 dropped `railway_service`, which left each service's *deploy* config
(`dockerfilePath` / `startCommand` / `cronSchedule` / `restartPolicyType`) living only
as prose comments in one shared `src/railway.toml` plus manual Railway-dashboard entry —
i.e. the "no more dashboard clicking" half of FR-001's user story was still unmet for the
five `src/` services that share `src/Dockerfile`.

**Fix — Railway-native config-as-code, one file per service.** `src/railway.toml` is
replaced by `src/railway-<service>.toml` for each of `scrape-and-analyze`, `weekly-report`,
`refresh-metrics`, `dedup-reconcile`, `rag-backfill`. Each declares `[build] dockerfilePath
= "src/Dockerfile"` (still the one shared image) + its own `[deploy]` block. These files
are version-controlled and reviewed like any other code; config-as-code is a per-deploy
overlay merged on top of dashboard settings, so an omitted key (e.g. `scrape-and-analyze`'s
still-unrecorded `cronSchedule`) safely falls through to the dashboard.

**Residual manual step (accepted):** each service's **Config File Path** is set once, by
hand, in the Railway service settings (`/src/railway-<service>.toml`). Railway exposes no
service variable for this (`RAILWAY_CONFIG_PATH` does not exist), and the only Terraform
route — re-adding `railway_service` with `config_path` — reintroduces exactly the
primary-environment-only asymmetry Revision 2 removed, to manage a value that never changes.
Not worth it.

**`UV_GROUP`** (the per-service build ARG selecting that service's uv dependency-group
subset) stays a Terraform-managed service variable (`var.uv_group_<service>`, already in
place). Revision 3 also fixes a latent name mismatch: `src/Dockerfile` declared `ARG
UV_GROUPS` (plural) while the live/Terraform variable is `UV_GROUP` (singular), so Railway's
by-name build-arg injection never reached it and every `src/` service built with the
Dockerfile default `"scraper llm http-clients"`. The ARG is renamed to `UV_GROUP`;
`refresh-metrics` / `dedup-reconcile` / `rag-backfill` / `weekly-report` will now build with
their intended narrower group sets.

**Cutover order:** set the five Config File Paths in Railway *before* this merges/deploys —
a deploy that still points at the deleted `src/railway.toml` would fall back to
dashboard/Nixpacks defaults.

FR-001's intent ("build settings … in version-controlled declarative files … no manual
dashboard clicking") is now met more fully than Revision 2 had it. Still no `spec.md` FR
change.

---

## Revision 4 — 2026-08-31 ("Option A": Railway variables leave Terraform)

Revisions 1–3 kept the Railway service **variables** in Terraform (a
`railway-variables` module, one `<svc>.tf` per service, `shared.tf` groups). The
`terraform-community-providers/railway` provider (v0.6.2, latest) does not hold up
at this project's scale:

| Symptom (observed on the staging bootstrap) | Cause |
|---|---|
| `serviceInstanceRedeploy Service deployment rate limit exceeded` after ~3 vars | `railway_variable` triggers a service **redeploy per variable**; a first apply of one service = 30–40 redeploys in seconds. |
| `Error: Provider produced inconsistent result after apply … .variables: inconsistent values for sensitive attribute` on every large service | `railway_variable_collection`'s Create writes all vars, then immediately re-reads; Railway's write is not read-your-writes consistent, so the read-back is short → Terraform core rejects it. Retrying re-races; empty-string values (Railway drops them) make it worse. |
| GitHub `github_actions_variable` 409 on first apply | provider POSTs (no upsert) — needs a one-time import or `gh variable delete` + recreate. |

**Fix.** Drop the `railway` provider. Terraform now manages **only** the GitHub
Actions secrets/variables (`github-ci.tf` + `modules/github-ci-config`). Railway
service env vars are pushed by `scripts/push_railway_variables.py`:

- structure (which service gets which var) → `infra/terraform/railway/railway-services.json`
  (shared groups + per-service `own` + an `unmanaged` allow-list + per-service
  `redeploy: false` for cron/one-off services)
- values → `secrets/railway-{shared,<env>}.tfvars` (the `secrets/*.tfvars` set is
  split: `github-*` for Terraform, `railway-*` for the script)
- one batched `railway variables --set … --skip-deploys` per service, then **one**
  `railway redeploy` — no per-variable redeploy, no racy read-back
- `--prune` (default in CI's `terraform.yml` apply path) deletes Railway vars the
  manifest/tfvars don't produce → same converge-both-ways semantics as
  `terraform apply` on the GitHub side
- `--check` (drift) and `pull_railway_variables.py` (inventory) unchanged in spirit

`spec.md`'s FR-001/002/003 intent (declarative, version-controlled, single source
of truth, applied through CI on the same triggers as the code deploy) is
preserved — only the *executor* for the Railway half changed from a Terraform
provider to a stdlib script + the official CLI. FR-010 (import existing state)
becomes a non-issue for the Railway half: the script upserts idempotently, no
state to reconcile.

---

## Revision 6 — 2026-09-02 (Railway half → Railway-native IaC `.railway/railway.ts`)

Revision 5 (a `push_railway_service_config.py` setting each service's
`railwayConfigFile` via GraphQL) was abandoned the day it was written: Railway
**deprecated config-as-code** (`railway.toml` / `railway.json`) with a **hard
cutoff of 2026-12-01**, after which those files stop being read. This
invalidates Revision 3's `src/railway-<svc>.toml` files *and* the four
auto-detected `railway.toml` (backend / frontend / chatbot-plugin / fastembed).
See `research.md` §11.

**Fix — Railway-native IaC.** The whole Railway half (service deploy config
**and**, later, env-var values) moves onto Railway's replacement: a single
project-wide **`.railway/railway.ts`** driven by `railway config plan` /
`railway config apply`. This subsumes both `src/railway-*.toml` (Revision 3) and
`scripts/push_railway_variables.py` + `railway-services.json` (Revision 4) —
`railway config`'s plan/apply is one batched diff, so the per-variable-redeploy
rate-limit that killed the `railway` *Terraform provider* in Revision 4 does not
apply to the CLI. **Terraform keeps only the GitHub Actions half**
(`github-ci.tf` + `modules/github-ci-config`) — Railway IaC does not manage
GitHub, and a real multi-cloud need is imminent (fastembed → GCP).

**Toolchain — a dedicated `railway_cli` container.** The Windows Railway CLI
build can't evaluate the `.ts` config (Node type-stripping). A
`.railway/Dockerfile` (`node:24` + the genuine standalone Railway CLI + the
`railway` npm SDK) + a `railway_cli` compose service (profile `tools`) run it.
`Makefile` targets `railway-cli`, `railway-config-{plan,apply,pull,migrate}` are
dual-mode: on the host they wrap into the container; in-container they call
`railway` directly. See `.railway/README.md` and its gotchas list (npm CLI too
old for the engine; SDK still required for `import "railway/iac"`; `$_`-based
version self-check; ESM resolution needs `/node_modules`; `RAILWAY_TOKEN`
blocks `railway login`).

**Auth.** `railway config` uses a **project token scoped to one environment**
(`RAILWAY_TOKEN`) — no `--environment` flag; the token (or a persisted `railway
link`) selects the env. `infra/terraform/railway/.env` carries
`RAILWAY_TOKEN_STAGING` / `RAILWAY_TOKEN_PRODUCTION`; the Makefile targets read
`RAILWAY_TOKEN_<ENV>` and inject it for that one command. Same token model as
the official `railwayapp/config` GitHub Action.

**v1 — faithful reproduction (this revision, DONE).** Every service env var in
`railway.ts` is `preserve()` (value left exactly as Railway holds it, not
managed here yet); only build / start / networking / replicas + the genuine
staging↔production differences (volume name, cron schedules, `backfill_rag`
`--limit`) are expressed. **Gate: `railway config plan` shows 0 changes on
BOTH environments.** Met — production's 5 branchless service sources (`weekly
report`, `dedup_reconcile`, `refresh metrics`, `fastembed`, `backfill_rag`)
were normalised to `branch: "master"` via a one-off `railway config apply`
(safe, non-destructive; `null` already meant "default branch" = master, and
the other 5 services were already pinned).

| FR-014 (managed databases stay hands-off) | how v1 honours it |
|---|---|
| `Redis` / `Postgres` / their volumes are declared in `railway.ts` | only so the project-wide `railway config` does not propose **deleting** them; nothing about them is managed |
| `postgres()` helper injects a default image pin the live DB lacks | `Postgres.source = null` nulls it back out to match live |
| any `plan` diff against Redis/Postgres/volumes | **STOP** — pull them out of `resources`, do not apply |

**v2 — de-`preserve()` (later).** Replace each `preserve()` group with a real
literal (non-secret) / `process.env.X` (secret, injected at `railway config
apply` from the GitHub Actions secrets `.github/workflows/*` already carry —
**not** routed through Terraform/HCP, which would resurrect the "third place
secrets live" §9 rejected) / `Redis.env.* / Postgres.env.*` reference. One
group at a time, `plan`-verified. Only once `railway.ts` manages every value do
`push_railway_variables.py`, `railway-services.json`, `src/railway-*.toml`, and
their Makefile targets retire.

**CI.** A job using `railwayapp/config@v1` — `plan` on a PR touching
`.railway/**`, `apply` on merge — with the per-env project token as a
`RAILWAY_TOKEN` secret in the `scraper / staging` and `scraper / production`
GitHub environments. Placement (fold into the reusable `terraform.yml` vs. its
own `railway.yml`) is a `[MAINTAINER]` decision.

`spec.md`'s FR-001/002/003 intent (declarative, version-controlled, single
source of truth, applied through CI on the same triggers as the code deploy) is
preserved; the *executor* for the Railway half changes once more — from the
Revision-4 script to Railway's own IaC engine — because the platform withdrew
the surface Revisions 3–4 were built on. No `spec.md` FR change.

---

## Summary

Replace manual Railway-dashboard and GitHub-Settings configuration with one flat Terraform
root config, applied per environment against its own HCP Terraform workspace. A
`railway-variables` module declares each of the ten app services' environment variables from
a `merge()` of shared groups (`local.shared`, defined once in `shared.tf`) and the service's
own entries; a `github-ci-config` module declares the GitHub Actions secrets/variables
`ci.yml`/`release.yml` read. Every value is Terraform-managed — no "baseline" half-state.
Non-secret and secret values alike are supplied via layered `-var-file` (`secrets/shared.tfvars`
+ `secrets/<env>.tfvars`, both git-ignored); in CI those three files are materialized from
three GitHub Actions secrets (`TF_TFVARS_SHARED` / `_STAGING` / `_PRODUCTION`, base64). The
environment is chosen by `TF_WORKSPACE`, guarded by a `check` block asserting it matches
`var.app_env`. Railway service/environment objects, Railway's managed databases, and exactly
three standing bootstrap credentials (HCP token, GitHub secrets-scoped PAT, account-level
Railway token) stay manually managed. Applies run only from the existing PR-gated staging
job (`ci.yml`) and tag-gated production job (`release.yml`), via a single reusable
`terraform.yml` workflow — never a bare merge to `master` (Constitution Principle V).

## Technical Context

**Language/Version**: HCL (Terraform CLI >= 1.9 — needs config-driven `import {}` blocks and
`check` blocks), plus Bash for CI glue and Makefile targets (Principle IV)

**Primary Dependencies**: `terraform-community-providers/railway` (~> 0.6 — used only for
`railway_variable`; `railway_service`/data sources deliberately unused, see research.md §9),
`integrations/github` (~> 6.0)

**Storage**: Remote Terraform state in HCP Terraform, free tier, **one workspace per
environment** (`staging`, `production`, in the `scrape-analyzer` project) — encrypted at
rest, access-restricted, state locking built in. The `cloud {}` block uses
`workspaces { tags = [...] }` (not a hard-coded `name`) so `TF_WORKSPACE` selects the target
at runtime and `terraform.workspace` reflects the real name for the `check` guard.

**Testing**: `terraform fmt -check` + `terraform validate` + `terraform plan` via the
reusable `terraform.yml` in `mode: plan` on PR open/reopen (rate-limit gated, see below);
real applies via the same workflow in `mode: apply` from the existing staging/production
deploy jobs.

**Target Platform**: GitHub Actions (`ubuntu-latest`) runners invoking the Terraform CLI;
managed resources live on Railway and in this repo's GitHub Actions secrets/variables store.

**Project Type**: Infra/tooling addition to an existing multi-service monorepo — a top-level
`infra/terraform/` directory, not a runtime service.

**Performance Goals**: N/A. Operationally, one environment's full `terraform apply` must not
materially lengthen the pipeline.

**Constraints**:
- Secret plaintext MUST NOT enter git (FR-004/FR-004a). `secrets/*.tfvars` are git-ignored;
  only `*.tfvars.example` (keys, no values) are tracked.
- IaC applies fire only on the triggers `railway up` already uses — PR events for staging,
  `v*` tags for production (Principle V) — never on a bare push to `master`.
- **Railway API rate limit**: every `plan`/`apply` refreshes every `railway_variable`
  (~150+ once fully migrated), one API call each; Railway's own limit (hit well before HCP's)
  can be exhausted by a few review-iteration pushes on one PR (observed retry-after
  ~40 min). Mitigations carried over from revision 1: the `plan`/`apply` jobs run on PR
  `opened`/`reopened` only (not every `synchronize`); `terraform.yml`'s `workflow_dispatch`
  is the manual re-run path; prefer `plan -out` + `apply <plan>` in one job; `make
  terraform-* TARGET=<addr>` narrows refresh for single-service changes.
- HCP free tier: 1 concurrent run/workspace (non-issue — staging/production already serialize
  via `concurrency:` groups), ≤500 managed resources (footprint ~150–200).

**Scale/Scope**: 10 app services × 2 environments (FR-001) + the GitHub Actions
secrets/variables `ci.yml`/`release.yml` reference (FR-012) + 3 standing bootstrap
credentials outside IaC scope (FR-013 — revised from 2 to 3, adding the account-level Railway
token) + Railway managed databases stay manual (FR-014).

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Check | Result |
|---|---|---|
| V. Explicit CI/CD Deployment Boundary | IaC apply fires only on the same PR/tag triggers `railway up` uses, never on bare `master` push | **PASS by design** — the reusable `terraform.yml` is invoked as a job from the existing `deploy-staging-*` / `release.yml` slots, reusing their `if:`/`concurrency:` gating; it adds no trigger of its own beyond an opt-in `workflow_dispatch` |
| IV. Docker-First Local Dev / "Makefile as interface" | All developer-facing operations exposed via Makefile targets | **PASS** — `make terraform-fmt/validate/plan/apply/drift-check` (now `-chdir=infra/terraform` + `TF_WORKSPACE=$(ENV)` + layered `-var-file`), plus `make push-tfvars` to sync the three `.tfvars` files to GitHub secrets. Terraform runs on a plain binary, not a container (needs real provider creds + remote backend) — same documented exception as revision 1 |
| IX. FastAPI Microservice Structure — env var discipline | `.env.example` documented as "the Railway shared-variable source of truth" | **No conflict** — `.env.example` still documents *which keys* a service expects for local dev; Terraform is authoritative for *what value* reaches Railway/CI per environment. `secrets/*.tfvars.example` mirror this on the Terraform side |
| III. Test Discipline / Docker-only test execution | All test runs execute inside Docker via Makefile targets | **Adapted, not violated** — Terraform's "test" is `validate`/`plan`, run as a CI job (needs remote-backend creds, can't be a local Docker test container). No prior HCL convention is bypassed |
| I/II/VI/VII/VIII | Not applicable — touches no `src/`/`backend/`/`frontend/` application code (US5, already complete, is the exception and was itself gated on those principles) | **N/A** |

No violations requiring Complexity Tracking justification.

## Project Structure

### Documentation (this feature)

```text
specs/025-iac-provisioning/
├── plan.md              # This file
├── research.md          # Phase 0 — §9's railway_service findings still hold as FACTS;
│                        #   revision 2's CONCLUSION is "don't declare railway_service at all"
├── data-model.md        # Phase 1 — needs re-alignment to revision 2 (see tasks T002)
├── quickstart.md        # Phase 1 — needs re-alignment to revision 2 (see tasks T002)
├── contracts/
│   ├── railway-variables-module.md   # renamed from railway-service-module.md (T002)
│   └── github-ci-config-module.md
└── tasks.md             # Phase 2 output — Phases 1–6/8 rewritten for revision 2; Phase 7 kept
```

### Source Code (repository root)

```text
infra/terraform/
├── versions.tf              # required_version >= 1.9, required_providers (railway, github)
├── providers.tf             # provider "railway" { token = var.railway_token }
│                            # provider "github" { owner = var.github_owner, token = var.github_token }
├── backend.tf               # cloud { organization = "scrape-analyzer"
│                            #         workspaces { tags = ["scrape-analyzer"] } }   ← no hard-coded name
├── variables.tf             # EVERY variable{}: railway_token, github_token, github_owner,
│                            #   github_repository, app_env, railway_environment_id,
│                            #   service_id_<svc> (×10), + one per env-var value (secret ⇒ sensitive = true)
├── locals.tf                # local.services list; check "workspace_matches_env" {
│                            #   assert { condition = terraform.workspace == var.app_env } }
├── shared.tf                # local.shared = { grafana = { GRAFANA_API_KEY = { value = var.grafana_api_key,
│                            #   sensitive = true }, ... }, sentry = {...}, rag_dense = {...}, ... }
├── services/
│   ├── dashboard-backend.tf     # module "dashboard_backend" { source = "../modules/railway-variables"
│   │                            #   service_id = var.service_id_dashboard_backend
│   │                            #   environment_id = var.railway_environment_id
│   │                            #   variables = merge(local.shared.grafana, local.shared.sentry, { <own> }) }
│   ├── dashboard-frontend.tf
│   ├── storybook.tf
│   ├── scrape-and-analyze.tf
│   ├── chatbot-plugin.tf
│   ├── fastembed.tf
│   ├── weekly-report.tf
│   ├── refresh-metrics.tf
│   ├── rag-backfill.tf
│   └── dedup-reconcile.tf
├── github-ci.tf            # module "github_ci_repo" (repo-level) + "github_ci_staging" +
│                           #   "github_ci_production" (env-scoped), from modules/github-ci-config
├── modules/
│   ├── railway-variables/  # one railway_variable.this per key; for_each = toset(nonsensitive(keys(...)))
│   │                       #   re-indexing into var.variables[k].value to keep sensitivity. NO managed/baseline.
│   │   ├── main.tf
│   │   ├── variables.tf    # service_id, environment_id, variables = map(object({value, sensitive=optional(bool,false)}))
│   │   └── outputs.tf      # variable_names
│   └── github-ci-config/   # repo vs environment-scoped github_actions_(secret|variable); NO managed/baseline split
│       ├── main.tf
│       ├── variables.tf
│       └── outputs.tf
└── secrets/
    ├── .gitignore          # *  then  !.gitignore  !*.example
    ├── shared.tfvars.example        # every shared key = "" (or a comment) — tracked
    ├── staging.tfvars.example
    ├── production.tfvars.example
    ├── shared.tfvars               # real values — git-ignored, == GitHub secret TF_TFVARS_SHARED (base64)
    ├── staging.tfvars              # git-ignored, == TF_TFVARS_STAGING
    └── production.tfvars           # git-ignored, == TF_TFVARS_PRODUCTION

infra/terraform/.env.local          # git-ignored — the 3 bootstrap creds only (TF_API_TOKEN,
                                    #   TF_GITHUB_TOKEN, RAILWAY_TOKEN) + optional RAILWAY_TOKEN_{STAGING,PRODUCTION}
                                    #   for pull_railway_variables.py. NOT env-var values.

.github/workflows/terraform.yml     # NEW — reusable: workflow_call(mode, environment) + workflow_dispatch
.github/workflows/ci.yml            # terraform-plan / deploy-staging-terraform jobs → uses: ./terraform.yml
.github/workflows/release.yml       # terraform-production job (uses:) before deploy; release-test-staging → uses:
.github/workflows/terraform-staging-manual.yml   # DELETED — folded into terraform.yml's workflow_dispatch
Makefile                            # terraform-* retargeted to flat root + TF_WORKSPACE + -var-file; + push-tfvars
scripts/generate_terraform_docs.py  # re-point from environments/*/main.tf to services/*.tf + shared.tf
scripts/pull_railway_variables.py   # + emit paste-ready .tfvars lines with ${ → $${ escaping (T014)
```

**Structure Decision**: One flat root config (`infra/terraform/`), applied twice — once per
HCP workspace. Environments differ only in *values*, never in *structure* (same ten services,
same wiring), so a single config + `-var-file` per environment is the textbook fit;
directory-per-environment is for environments with *different infrastructure*, which these do
not have. State isolation (FR-003) is provided by the separate HCP workspaces, not by
duplicating HCL. The one residual risk — applying the wrong environment's values into a
workspace — is closed by (a) the `check "workspace_matches_env"` block, and (b) `TF_WORKSPACE`
and the `-var-file` set always being derived together from a single `ENV=` / `environment:`
input (Makefile locally, `terraform.yml` in CI). One file per service under `services/`
mirrors the existing per-service `railway.toml` pattern: "where's this service's config" is
"the file named after it".

## Complexity Tracking

*No Constitution Check violations — this section is intentionally empty.*
