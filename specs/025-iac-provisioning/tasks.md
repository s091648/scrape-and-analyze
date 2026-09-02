---

description: "Task list for Infrastructure as Code for Deployment Environments"
---

# Tasks: Infrastructure as Code for Deployment Environments

**Input**: Design documents from `/specs/025-iac-provisioning/` (see `plan.md` "Revision 2 — 2026-08-28", "Revision 4 — 2026-08-31")

---

## Revision 4 — 2026-08-31 ("Option A": Railway variables leave Terraform)

The `terraform-community-providers/railway` provider proved unusable at scale
(per-variable redeploys trip Railway's deploy rate limit; `railway_variable_collection`
races on read-back). See `plan.md` "Revision 4". Net effect on the tasks below:

- **Superseded** (Terraform-managed Railway variables): `R04`, `R09`–`R11`, `R19`, `R20`,
  and the Railway half of `R08`, `R13`, `R28b`, `R29`, `R36`. The `railway-variables`
  module, `shared.tf`, and the ten `<svc>.tf` files are deleted.
- **New** (Option A): `infra/terraform/railway/railway-services.json` (manifest) +
  `scripts/push_railway_variables.py` (push / `--check` / `--prune`); `secrets/*.tfvars`
  split into `github-*` (Terraform) / `railway-*` (script) with `scripts/split_tfvars.py`;
  `variables.tf` trimmed to the ~25 GitHub-side vars; `terraform.yml`'s apply path runs
  the script with `--prune`; `Makefile` gains `push/check-railway-variables`.
- **Unchanged**: everything about the GitHub Actions half (`github-ci.tf`,
  `modules/github-ci-config`, `R05`, `R12`, `R21`), the reusable `terraform.yml` shell
  (`R30`–`R33`), and Phase 7 (User Story 5).
- `R34`–`R46` (`[MAINTAINER]`) still apply, re-read through the Option A lens: `R35`
  populates the six `secrets/{github,railway}-*.tfvars`; `R36` is now "GitHub `terraform
  apply` + `make push-railway-variables` per env, both clean" (no `import {}` for the
  Railway side); `R37` syncs six `TF_TFVARS_*` secrets; `R46` = this doc pass.

---

## Revision 6 — 2026-09-02 (Railway half → Railway-native IaC `.railway/railway.ts`)

Railway deprecated config-as-code (`railway.toml` / `railway.json`), hard cutoff
**2026-12-01**. The whole Railway half migrates to a project-wide
`.railway/railway.ts` + `railway config plan/apply`; Terraform keeps only the
GitHub Actions half. See `plan.md` "Revision 6" and `research.md` §11. Net
effect on the tasks above:

- **Superseded** (Revision 3 `src/railway-<svc>.toml`, Revision 4
  `push_railway_variables.py` + `railway-services.json` + `check/push-railway-variables`
  Makefile targets + the `terraform.yml` apply-path script call): all replaced by
  `.railway/railway.ts`. They are **not deleted yet** — that is `T6-08`, gated on
  v2 completing.
- **Unchanged**: the GitHub Actions half (`github-ci.tf`, `modules/github-ci-config`),
  the reusable `terraform.yml` shell for the GitHub side, Phase 7 (User Story 5),
  and FR-014 (managed DBs stay manually managed — `railway.ts` declares Redis/
  Postgres/volumes only so `railway config` won't propose deleting them).

### Format: `[ID] [P?] [role] Description`  (roles per Revision 2's Division of labour)

| ID | Role | Description | State |
|---|---|---|---|
| `T6-01` | [AGENT] | `.railway/Dockerfile` + `railway_cli` compose service (profile `tools`); `railway` standalone CLI + npm SDK; `/node_modules` symlink | ✅ done |
| `T6-02` | [AGENT] | `Makefile`: `railway-cli`, `railway-config-{plan,apply,pull,migrate}`, dual-mode host/container, per-env `RAILWAY_TOKEN_<ENV>` from `infra/terraform/railway/.env` | ✅ done |
| `T6-03` | [AGENT] | `.railway/railway.ts` v1 — faithful reproduction, every env var `preserve()`; `.railway/railway.{staging,production}.ts` pull references; `.gitignore` for `pulled.*.ts` / `.railway.ts.keep` / `railway-plan*.json` | ✅ done |
| `T6-04` | [MAINTAINER] | v1 gate: `railway config plan` clean on **both** envs. Normalise production's 5 branchless service sources to `branch: "master"` via one-off `railway config apply` | ✅ done (commit `bbfc655c`) |
| `T6-05` | [AGENT] | Commit v1 (`.railway/**` + Dockerfile + `docker-compose.yml` + `Makefile` + `.gitignore`) | ✅ done (`bbfc655c`) |
| `T6-06` | [AGENT] | This doc pass — `plan.md` "Revision 6" + `tasks.md` "Revision 6", fold `research.md` §11 | ✅ done |
| `T6-07` | [AGENT] + [MAINTAINER] | CI job with `railwayapp/config@v1` — `plan` on PR touching `.railway/**`, `apply` on merge. [MAINTAINER]: create `RAILWAY_TOKEN` secret in the `scraper / staging` + `scraper / production` GitHub environments; decide `terraform.yml` vs. new `railway.yml` | ☐ pending |
| `T6-08` | [AGENT] | **v2** — replace each `preserve()` group with real literal / `process.env.X` (secret) / `Redis.env.*` ref, one group at a time, `plan`-verified each | ☐ pending |
| `T6-09` | [AGENT] | Retire the old Railway-vars path once `T6-08` done: delete `scripts/push_railway_variables.py`, `railway-services.json`, `src/railway-*.toml`, the `push/check-railway-variables` Makefile targets, the `terraform.yml` script call; update `CLAUDE.md` + `infra/terraform/railway/README.md` + `site/guide/architecture/terraform-services.md` | ☐ pending |
| `T6-10` | [AGENT] | Decide `src/railway-scrape-and-analyze.toml` staged TOML-syntax fix — fold into `T6-09`'s deletion or drop | ☐ pending |

---

## Revision 2 — 2026-08-28 (structure reset)

The first pass (`T001`–`T041`) is **superseded**. Both HCP workspaces were deleted; the
`scrape-analyzer` HCP project now has two empty workspaces (`staging`, `production`). Tasks
below (`R01`–`R38`) replace the old Phases 1–6 and 8. **Phase 7 (User Story 5, `T042`–`T051`)
is retained verbatim and stays done** — pure application code, no Terraform dependency.

### Division of labour

- **`[AGENT]`** — file/code changes only. Never runs `terraform import`/`plan`/`apply`, never
  touches a real HCP workspace or GitHub secret.
- **`[MAINTAINER]`** — the maintainer runs it; it touches real state (import, apply, GitHub
  secret creation, test-tag). The agent provides the exact command / generated input and the
  expected output to check against, and stops.

### Format: `[ID] [P?] [role] Description`

- **[P]**: can run in parallel (different files, no unmet dependency)
- File paths are relative to the repository root

---

## Phase R1: Teardown & flat skeleton

- [X] R01 [AGENT] Delete the superseded tree: `infra/terraform/environments/` (all of
  `staging/`, `production/`, `shared/`), `infra/terraform/modules/railway-service/`,
  `infra/terraform/modules/shared-variables/`, and the stray `mig.sh` / `mig2.sh` at repo
  root. Keep `infra/terraform/modules/railway-variables/`, `modules/github-ci-config/`,
  `.terraform-docs.yml`, `.env.local`, `.live-variables.json`.
- [X] R02 [AGENT] Create the flat-root skeleton per `plan.md`'s Project Structure:
  `infra/terraform/{versions,providers,backend,variables,locals,shared,github-ci}.tf` (empty
  or stub), `infra/terraform/services/` (empty), `infra/terraform/secrets/` with a
  `.gitignore` (`*` then `!.gitignore` `!*.example`).
- [X] R03 [AGENT] Update the root `.gitignore`: replace the `infra/terraform/**/*.auto.tfvars`
  line's intent with `infra/terraform/secrets/*` + `!infra/terraform/secrets/.gitignore`
  `!infra/terraform/secrets/*.example`; keep the `.terraform/`, `*.tfstate*`, `crash.log`,
  `.env.local`, `.live-variables.json` rules.

**Checkpoint**: old structure gone, flat skeleton + secret-dir ignore rules in place.

---

## Phase R2: Spec-doc re-alignment (keep the spec dir internally consistent)

- [X] R04 [P] [AGENT] `contracts/railway-service-module.md` → rename to
  `contracts/railway-variables-module.md`; drop the `railway-service` half entirely; revise
  the `railway-variables` half: inputs `service_id`, `environment_id`, `variables =
  map(object({ value = string, sensitive = optional(bool, false) }))`; no `managed` field;
  behavioural contract keeps the reference-string (`${{...}}`) and key-removal-⇒-destroy
  clauses.
- [X] R05 [P] [AGENT] `contracts/github-ci-config-module.md` — drop any `managed`/`baseline`
  language; module is repo-level vs environment-scoped only, every entry enforced.
- [X] R06 [P] [AGENT] `data-model.md` — rewrite the "Service Definition" and "Environment"
  sections: no `railway-service` module, no `config_path`, no `terraform_remote_state`; one
  flat root; Environment = HCP workspace selected by `TF_WORKSPACE`; the `check` guard.
  Environment-Variable table loses the `managed`/baseline notion — every kind is enforced;
  values arrive via layered `-var-file`.
- [X] R07 [P] [AGENT] `quickstart.md` — rewrite: 3 bootstrap creds (add account-level Railway
  token), `secrets/*.tfvars` + `.example` templates, `make terraform-plan ENV=…`, the
  config-driven `import {}` flow, `make push-tfvars`, day-to-day loop via `terraform.yml`.
- [X] R08 [P] [AGENT] `research.md` §9 — add a dated note: the `railway_service`
  single-primary-environment finding still stands; revision 2's conclusion is **not to
  declare `railway_service` at all** (service IDs become `.tfvars` values), which removes the
  production-only asymmetry the old note worked around.

**Checkpoint**: every doc in `specs/025-iac-provisioning/` describes revision 2, not the old design.

---

## Phase R3: Modules

- [X] R09 [AGENT] `modules/railway-variables/variables.tf` — `service_id` (string),
  `environment_id` (string), `variables` (`map(object({ value = string, sensitive =
  optional(bool, false) }))`, default `{}`). Remove the `managed` attribute and its long
  doc block.
- [X] R10 [AGENT] `modules/railway-variables/main.tf` — a single `railway_variable "this"`:
  `for_each = toset(nonsensitive(keys(var.variables)))`, `name = each.value`, `value =
  var.variables[each.value].value` (re-index into the original map so a `sensitive` value
  keeps its marking), `service_id`/`environment_id` from vars. Delete the
  `managed`/`baseline` resources and all `lifecycle { ignore_changes = [value] }`. Comment
  explaining the `nonsensitive(keys(...))` pattern (Terraform forbids `for_each` over a
  map any of whose values is sensitive).
- [X] R11 [AGENT] `modules/railway-variables/outputs.tf` — `variable_names = keys(var.variables)`.
  Drop `managed_variable_names`.
- [X] R12 [AGENT] `modules/github-ci-config/main.tf` + `variables.tf` + `outputs.tf` — drop
  the `managed`/`baseline` split (the `for k,v ... if v.managed` locals, the paired
  `*.baseline` resources, the `ignore_changes`). Keep the repo-level vs
  `github_environment_name`-scoped split. `secrets`/`variables` become
  `map(object({ value = string }))` (or just `map(string)`); every entry enforced.
- [X] R13 [AGENT] `make uml-terraform-modules` still points at
  `modules/{railway-variables,github-ci-config}` — confirm `.terraform-docs.yml` needs no
  change now that `railway-service`/`shared-variables` are gone (edit if it enumerates them).

**Checkpoint**: both modules compile conceptually, all-enforced, no baseline machinery.

---

## Phase R4: Root config

- [X] R14 [AGENT] `infra/terraform/versions.tf` — `required_version >= 1.9`;
  `required_providers` railway `~> 0.6`, github `~> 6.0`.
- [X] R15 [AGENT] `infra/terraform/backend.tf` — `terraform { cloud { organization =
  "scrape-analyzer"; workspaces { tags = ["scrape-analyzer"] } } }`. **No hard-coded
  `name`** — `TF_WORKSPACE` selects; `terraform.workspace` then reflects `staging`/`production`.
- [X] R16 [AGENT] `infra/terraform/providers.tf` — `railway` provider (`token =
  var.railway_token`), `github` provider (`owner = var.github_owner`, `token =
  var.github_token`).
- [X] R17 [AGENT] `infra/terraform/variables.tf` — declare **every** input:
  `railway_token`/`github_token` (`sensitive`), `github_owner`, `github_repository`,
  `app_env`, `railway_environment_id`, `service_id_<svc>` ×10, and one `variable` per
  environment-variable value the services/`shared.tf`/`github-ci.tf` consume (each secret
  one `sensitive = true`, each with a one-line `description`). This file is the schema; the
  `.example` tfvars (R25) mirror its names.
- [X] R18 [AGENT] `infra/terraform/locals.tf` — `local.services` (the ten module keys, for
  any list-driven docs/asserts) + `check "workspace_matches_env" { assert { condition =
  terraform.workspace == var.app_env, error_message = "TF_WORKSPACE=${terraform.workspace}
  != app_env=${var.app_env}" } }`.
- [X] R19 [AGENT] `infra/terraform/shared.tf` — `local.shared` = a map of named groups
  (`grafana`, `sentry`, `rag_dense`, `rag_dense_endpoint_url`, `rag_sparse`,
  `rag_sparse_limits`, `vector_db`, `rag_chunking`, `notifications`, `database_url`,
  `cache_redis_url`, `gemini_api_key`, `openrouter_api_key`, `github_package_token`,
  `app_env`), each already shaped as the `railway-variables` `variables` input
  (`{ KEY = { value = var.x, sensitive = true } }`). Group membership per service is the
  same set the first pass validated via `pull_railway_variables.py` (see the old
  `modules/shared-variables/outputs.tf` descriptions — carry those `# consumed by …`
  comments across).

**Checkpoint**: `terraform validate` (once R20–R21 land) would parse; no resources yet beyond modules' shape.

---

## Phase R5: Per-service files + GitHub CI

- [X] R20 [AGENT] `infra/terraform/services/<svc>.tf` ×10 — one `module "<svc>"` per file:
  `source = "../modules/railway-variables"`, `service_id = var.service_id_<svc>`,
  `environment_id = var.railway_environment_id`, `variables = merge(<the local.shared.*
  groups this service uses>, { <this service's own entries> })`. Own entries: the genuinely
  per-service keys the first pass identified as *not* shareable (`CONTACT_EMAIL`,
  `RAG_SPARSE_ENDPOINT_URL`, `UV_GROUPS`, `SEARCH_*`, `CHAT_SERVICE_*`, `FRONTEND_ORIGIN`,
  `NEXTAUTH_SECRET`, `MAXMIND_LICENSE_KEY`, `SWAGGER_TRY_IT_OUT_ENABLED`, `GRAFANA_TEMPO_*`,
  `GRAFANA_PROMETHEUS_*`, `REDIS_URL`, `SEARCH_INDEX_REDIS_URL`, …) — each `{ value =
  var.<name>, sensitive = <bool> }`, value supplied per-`.tfvars`. Service-specific-but-
  otherwise-shared keys use a suffixed var name (`var.uv_groups__scrape_and_analyze`).
- [X] R21 [AGENT] `infra/terraform/github-ci.tf` — `module "github_ci_repo"` (repo-level:
  `CLAUDE_API_KEY`, `CODECOV_TOKEN`, `GEMINI_API_KEY`, `GIST_ID`, `GIST_SECRET`,
  `NEXTAUTH_SECRET`, `NPM_TOKEN`, `OPENROUTER_API_KEY`, `RELEASE_PAT` as secrets;
  `BACKEND_URL`/`FRONTEND_URL`/`STORYBOOK_URL` + `RAILWAY_SERVICE_ID_*` ×10 as variables —
  the service-ID variables now come straight from `var.service_id_<svc>`, not a module
  output) + `module "github_ci_staging"` / `module "github_ci_production"`
  (`github_environment_name = "scraper / staging"` / `"… / production"`, secrets
  `DATABASE_URL`, `RAILWAY_TOKEN`). Every value from a `var.*`.
- [X] R22 [AGENT] `terraform fmt -recursive` the whole `infra/terraform/` tree; eyeball
  `terraform validate -backend=false` mentally (agent can't run it against the cloud
  backend, but `-backend=false` needs no creds — note it for R30's maintainer run).

**Checkpoint**: full config written; every value is a `var.*`; nothing references a deleted module or `terraform_remote_state`.

---

## Phase R6: `secrets/` templates

- [X] R23 [P] [AGENT] `infra/terraform/secrets/shared.tfvars.example` — every shared key
  (the `local.shared` inputs + `service_id_<svc>` ×10 + `github_owner`/`github_repository`)
  as `key = ""  # description`. Tracked in git.
- [X] R24 [P] [AGENT] `secrets/staging.tfvars.example` + `secrets/production.tfvars.example`
  — only the env-specific keys: `app_env`, `railway_environment_id`, plus any value the
  first pass confirmed genuinely differs per environment. Tracked.
- [X] R25 [AGENT] Header comment in each `.example`: "real file is git-ignored and ==
  GitHub Actions secret `TF_TFVARS_<LAYER>` (base64); sync via `make push-tfvars`".

---

## Phase R7: Makefile + pull script

- [X] R26 [AGENT] `Makefile` — retarget `terraform-fmt/validate/plan/apply/drift-check`:
  `TF_DIR := infra/terraform` (flat), add `TF_WORKSPACE=$(ENV)` to the env-export, append
  `-var-file=secrets/shared.tfvars -var-file=secrets/$(ENV).tfvars` to `plan`/`apply`/
  `drift-check` (paths resolve under `-chdir=infra/terraform`). Keep `ENV` default
  `staging`, validate `ENV ∈ {staging,production}`. Keep `TARGET=`, `terraform-force-unlock`.
  `.env.local` still sources the 3 bootstrap creds only.
- [X] R27 [AGENT] `Makefile` — new `push-tfvars` target: for each layer in
  `shared|staging|production`, `base64 < infra/terraform/secrets/$$layer.tfvars | gh secret
  set TF_TFVARS_$${layer^^}`. Guard: fail if a `.tfvars` file is missing. Add to `.PHONY`
  and the `CLAUDE.md` command table (R37).
- [X] R28 [AGENT] `scripts/pull_railway_variables.py` — added `--as-tfvars` output mode:
  emits paste-ready `.tfvars` lines to `.live-variables.tfvars` (git-ignored), `${` → `$${`
  escaped, `RAILWAY_*` filtered, grouped by shared / per-env / env-only with `# DIFFERS`
  hints. Still read-only, not in CI.
- [X] R28b [AGENT] `scripts/generate_terraform_imports.py` (NEW) — generates the throwaway
  `infra/terraform/imports.tf` for R36 from `.live-variables.json` + `secrets/*.tfvars`.
  `python scripts/generate_terraform_imports.py --env staging|production`. The Railway
  import-ID format is a `RAILWAY_IMPORT_ID_TEMPLATE` constant at the top — **the v0.6
  provider docs disagree on it**, so R36 must confirm with one manual `terraform import`
  before trusting the whole file. GitHub-side import blocks are left as commented
  templates (only ~20, stable format).

---

## Phase R8: Docs generator

- [X] R29 [AGENT] `scripts/generate_terraform_docs.py` — re-point the static HCL parse from
  `infra/terraform/environments/*/main.tf` to `infra/terraform/services/*.tf` +
  `shared.tf` + `github-ci.tf`. Resolve `merge(local.shared.X, {...})` by reading
  `shared.tf`'s `local.shared` map. Output shape (`terraform-services-data.json`, the
  VitePress page) stays the same — still never prints a value, still per-environment usage.
  Update `site/guide/architecture/terraform-services.md` prose if it names the old layout.
  `make uml-terraform-docs` target unchanged.

**Checkpoint**: `make uml-terraform-docs` regenerates cleanly from the flat structure.

---

## Phase R9: Reusable Terraform workflow + CI rewire

- [X] R30 [AGENT] `.github/workflows/terraform.yml` — NEW reusable workflow.
  `on: workflow_call` inputs `mode` (`plan`|`apply`) + `environment` (`staging`|
  `production`); `on: workflow_dispatch` same inputs (defaults `plan`/`staging`).
  One job: `environment: scraper / ${{ inputs.environment }}`; `hashicorp/setup-terraform@v3`
  (`terraform_wrapper: false`); a "Materialize tfvars" step that `base64 -d`s
  `secrets.TF_TFVARS_SHARED` → `secrets/shared.tfvars` and
  `secrets.TF_TFVARS_<ENV>` → `secrets/<env>.tfvars`; `terraform -chdir=infra/terraform
  init`; then `terraform -chdir=infra/terraform ${{ inputs.mode }} [-auto-approve if apply]
  -no-color -var-file=secrets/shared.tfvars -var-file=secrets/${{ inputs.environment }}.tfvars`.
  `env:` on the terraform steps: `TF_WORKSPACE: ${{ inputs.environment }}`,
  `TF_TOKEN_app_terraform_io`, `GITHUB_TOKEN` (= `secrets.TF_GITHUB_TOKEN`),
  `TF_VAR_railway_token` (= `secrets.TF_RAILWAY_TOKEN`), `TF_VAR_github_token`. Optional: on
  `mode: plan` + PR context, post the plan as a sticky PR comment (lighthouse.yml pattern).
- [X] R31 [AGENT] `.github/workflows/ci.yml` — replace the `terraform-plan` job body with
  `uses: ./.github/workflows/terraform.yml` + `with: { mode: plan, environment: staging }` +
  `secrets: inherit`; keep its `if:` (PR `opened`/`reopened`) and `needs:`. Replace
  `deploy-staging-terraform` the same way (`mode: apply`), keeping its `if:`, `needs:
  [terraform-plan]`, and `concurrency: staging-terraform-${{ pr.number }}`.
- [X] R32 [AGENT] `.github/workflows/release.yml` — extract the inline `terraform
  init`/`apply (production)` steps out of the `release` job into a new
  `terraform-production` job (`needs: detect`, `if: needs.detect.outputs.is_master_tag ==
  'true'`, `uses: ./.github/workflows/terraform.yml`, `with: { mode: apply, environment:
  production }`, `secrets: inherit`). Add `needs: [terraform-production]` to whatever job
  now performs the production Railway deploy so infra still lands first. Replace the inline
  `terraform apply (staging)` in `release-test-staging` with a `uses:` job the same way
  (`environment: staging`). **Flag for maintainer review**: this changes the production
  apply from an in-job step to a `needs:`-ordered separate job — confirm the resulting job
  graph in R34.
- [X] R33 [AGENT] Delete `.github/workflows/terraform-staging-manual.yml` — superseded by
  `terraform.yml`'s `workflow_dispatch`. Update `infra/terraform/README.md`'s rate-limit
  section to point at "Actions → Terraform → Run workflow" instead.

**Checkpoint**: all Terraform CI logic lives in one reusable workflow; callers are `uses:` + 2-line `with:`.

---

## Phase R10: [MAINTAINER] Import & verify (touches real state)

- [X] R34 [MAINTAINER] Review the four changed workflow call-sites (R31/R32) — confirm the
  `release.yml` job graph (`terraform-production` before the prod deploy) is what you want.
- [X] R35 [MAINTAINER] Populate `infra/terraform/secrets/{shared,staging,production}.tfvars`:
  1. `cp` each `*.tfvars.example` → `*.tfvars`; fill in the NON-secret UUIDs first —
     `railway_project_id`, `service_id_<svc>` ×10 (in `shared.tfvars`),
     `railway_environment_id` + `app_env` (in each `<env>.tfvars`), `github_owner`,
     `github_repository`. (`make pull-railway-variables` needs those before it can run.)
  2. `make pull-railway-variables AS_TFVARS=1` → writes `.live-variables.tfvars` (a draft).
     Runs on the HOST via plain `python` (stdlib only now, no `uv`/hcl2, NOT docker); needs
     the `railway` CLI + `RAILWAY_TOKEN_STAGING`/`_PRODUCTION` in `.env.local`.
  3. Sort the draft's lines into the three files (shared = identical across both envs;
     `<env>.tfvars` = the rest + env-only keys), hand-fix every `$${{ … }}` reference,
     resolve `## DIFFERS` lines by suffixing the var. Cross-check against `*.tfvars.example`.
- [ ] R36 [MAINTAINER] Import, one workspace at a time.
  `make terraform-imports ENV=staging` writes the throwaway `infra/terraform/imports.tf`
  (git-ignored) — config-driven `import {}` blocks for every `railway_variable` (address
  `module.<svc>.railway_variable.this["<KEY>"]`). **First** run
  ONE manual `terraform import 'module.storybook.railway_variable.this["GITHUB_PACKAGE_TOKEN"]' <id>`
  to confirm which ID format the v0.6 provider accepts, then set
  `RAILWAY_IMPORT_ID_TEMPLATE` in the script and regenerate. Fill in the ~20 GitHub-side
  `import {}` blocks by hand (commented templates are in the generated file). Then:
  `make terraform-plan ENV=staging` → MUST read "**N to import, 0 to add, 0 to change, 0 to
  destroy**". Any `+`/`~`/`-` ⇒ stop, reconcile the `.tfvars` value or the declaration
  (e.g. the `SEARCH_INDEX_REDIS_URL` / staging-only stray notes in the service files, or
  moving a value between `shared.tfvars` and `<env>.tfvars`). When clean:
  `make terraform-apply ENV=staging`. Repeat `ENV=production`. Delete `imports.tf`; a final
  `make terraform-plan ENV=<both>` MUST say "No changes." (spec.md US1 AS1, SC-003).

**Checkpoint**: both workspaces hold every service's every variable + the GitHub CI store, all Terraform-managed, `plan` clean. FR-001/FR-002/FR-003/FR-010/SC-001/SC-003 met.

---

## Phase R11: [MAINTAINER] CI secret sync & pipeline validation

- [ ] R37 [MAINTAINER] `make push-tfvars` — creates/updates `TF_TFVARS_SHARED` /
  `TF_TFVARS_STAGING` / `TF_TFVARS_PRODUCTION` GitHub Actions secrets. Confirm
  `TF_API_TOKEN`, `TF_GITHUB_TOKEN`, `TF_RAILWAY_TOKEN` already exist (carried over from
  revision 1).
- [ ] R38 [MAINTAINER] Validate via the test-tag path: push a tag on this branch (not
  master) → `release.yml`'s `release-test-staging` → `terraform.yml` applies `staging` →
  expect "No changes." Then open a PR → `ci.yml`'s `terraform-plan` job posts a clean plan;
  `deploy-staging-terraform` applies "No changes." (spec.md US3 AS1/AS2/AS3, FR-006/FR-008).
  Break a declaration deliberately once, confirm the job fails loudly, revert (FR-006).

**Checkpoint**: infra changes ship through `ci.yml` (staging) and `release.yml` (production) via the shared `terraform.yml`, on the same PR/tag triggers as `railway up`. US1–US3 all independently functional.

---

## Phase 6 (retained): User Story 4 — drift detection

- [X] R39 [AGENT] `Makefile` `terraform-drift-check` already runs `terraform plan
  -detailed-exitcode` per env — confirm it works against the flat root + `-var-file` (R26
  covers the retarget). Exit `2` = drift, `0` = in sync, `1` = error.
- [X] R40 [AGENT] `.github/workflows/terraform.yml` — add an optional `mode: drift` (or a
  `workflow_dispatch`-only path) running `plan -detailed-exitcode` and writing the result to
  `$GITHUB_STEP_SUMMARY`.
- [ ] R41 [MAINTAINER] Change one Railway dashboard value out-of-band, run
  `make terraform-drift-check ENV=staging`, confirm it reports exactly that key, revert
  (spec.md US4 AS2).

---

## Phase R12: Polish

- [X] R42 [P] [AGENT] `CLAUDE.md` Commands table — update the `terraform-*` rows (flat root,
  `ENV=`, `-var-file`), add `make push-tfvars`.
- [X] R43 [P] [AGENT] `CLAUDE.md` Architecture section — `infra/terraform/` one-liner: flat
  root, per-env HCP workspace, `railway-variables` + `github-ci-config` modules, no
  `railway_service`.
- [X] R44 [P] [AGENT] `infra/terraform/README.md` — rewrite Layout, Bootstrap credentials
  (now 3), the `TF_VAR_*`/`.tfvars` mapping, "Browsing what's declared", and the rate-limit
  section (manual re-run is now `terraform.yml` `workflow_dispatch`).
- [X] R45 [P] [AGENT] Repo-wide grep across `infra/terraform/**/*.tf` + tracked
  `*.tfvars.example` for anything resembling a literal secret — expect zero (every value is
  `var.*`; `.example` files have no values). Confirms SC-005.
- [ ] R46 [MAINTAINER] Re-run `quickstart.md` end-to-end, correct any drift between doc and reality.

---

## Phase 7: User Story 5 — Centralize application-side environment variable reads (RETAINED, DONE)

**Unchanged by revision 2.** Pure `src/`/`shared/`/`frontend/` code; no Terraform dependency.
See spec.md FR-015–FR-019, SC-007.

### Tests for User Story 5

- [X] T050 [P] [US5] Added `test_get_run_immediately_reflects_live_change_without_reload`/`test_get_grafana_loki_config_reflects_live_change_without_reload` to `src/tests/unit/config/test_config.py`, plus `test_geoip_db_path_reads_env`/`test_geoip_db_path_has_default` to `backend/tests/test_config.py`. Full existing suites (`test_config.py`, `test_main.py`, `test_loki_logging.py`, `test_geoip.py`, `backend/tests/test_config.py`, `test_bootstrap.py`) all re-run and pass — no regressions
- [X] T051 [P] [US5] Added `frontend/tests/unit/env-server.test.ts` + `env-client.test.ts` (Vitest, using `vi.resetModules()` + dynamic import per case). Full frontend suite re-run: **1324/1324 tests, 102/102 files pass**

### Implementation for User Story 5

- [X] T042 [US5] Added `get_run_immediately()` to `src/config/settings.py`; `src/entrypoints/cli/main.py` now calls it instead of reading `os.environ` directly (unused `import os` removed) (spec.md US5 Acceptance Scenario 1)
- [X] T043 [US5] Added `get_grafana_loki_config()` to `src/config/settings.py` (returns `(url, user, key)`); `src/infrastructure/shared/observability/loki_logging.py` now calls it instead of three direct `os.environ.get` calls (spec.md US5 Acceptance Scenario 1)
- [X] T044 [US5] Added `GEOIP_DB_PATH` to `backend/config.py`; `shared/utils/geoip.py` now exposes `configure(db_path)` instead of reading `os.environ` at import time, called once from `backend/main.py`'s module-level startup sequence (spec.md US5 Acceptance Scenario 2, FR-017)
- [X] T045 [P] [US5] Created `frontend/lib/env.server.ts` — raw (no baked-in defaults, matching each call site's own historical fallback) re-exports of every non-`NEXT_PUBLIC_` var this app reads (FR-018)
- [X] T046 [P] [US5] Created `frontend/lib/env.client.ts` — `NEXT_PUBLIC_*` vars plus `APP_ENV`/`SENTRY_DSN` (next.config.ts-whitelisted for client exposure — documented in the file's header, not just NEXT_PUBLIC_-prefixed ones) (FR-018)
- [X] T047 [US5] Migrated all 12 real app-runtime call sites (proxy route, grafana-embed route, link-google start/callback routes, monitoring page, `lib/auth.ts`, `lib/server/ssr-fetch.ts`, `lib/loki-logger.ts`, `instrumentation-client.ts`, `nav-bar.tsx`, both chat providers) to import from `env.server.ts`/`env.client.ts`. Verification grep confirms the only remaining direct `process.env` reads are in explicitly-excluded test/tooling/build-config files (spec.md US5 Acceptance Scenario 3) — depends on T045, T046
- [X] T048 [US5] Added an ESLint `no-restricted-properties` rule forbidding `process.env` access outside `env.server.ts`/`env.client.ts`/config/tooling files (`frontend/eslint.config.mjs`), plus `.github/scripts/check-env-var-centralization.sh` covering both the frontend rule and the Python side (`os.environ` outside each service's `config.py`/`settings.py`, with narrow documented exceptions for the two data-driven `api_key_env` redirects). Wired into CI as an extra step on the existing `check-lockfile` job (renamed "Verify uv.lock & Env Var Centralization") rather than a new standalone job — same enforcement, no extra runner/checkout overhead (FR-019, spec.md US5 Acceptance Scenario 4)
- [X] T049 [US5] Ran `.github/scripts/check-env-var-centralization.sh` locally — passes cleanly across `backend/`, `src/`, `chatbot-plugin/src/`, `fastembed/src/`, `shared/`, and `frontend/` — satisfies SC-007

**Checkpoint**: Application code and the Terraform-side inventory (US2) describe the same reality, with an automated guard against future drift.

---

## Dependencies & Execution Order (revision 2)

- **R1** (teardown/skeleton) → everything.
- **R2** (spec docs) — parallel with R3+, independent.
- **R3** (modules) → **R4** (root config) → **R5** (service files) → **R6** (templates).
- **R7** (Makefile/pull script), **R8** (docs gen), **R9** (workflows) — each depends only on
  R5 landing; mutually parallel.
- **R10** (`[MAINTAINER]` import) — depends on R5–R9 all done.
- **R11** (`[MAINTAINER]` CI validation) — depends on R10 + R9.
- **Phase 6** (drift, R39–R41) — depends on R9/R10.
- **R12** (polish) — after the desired stories are done.
- **Phase 7** (US5) — already complete, no dependency either way.

### Guardrails (carried over from revision 1's Notes)

- Every `[MAINTAINER]` `terraform apply` MUST be preceded by reviewing the matching `plan`.
  During import (R36) the only acceptable plan is "N to import, 0 add / 0 change / 0 destroy".
- No secret value ever authored into a `.tf` or a tracked `.tfvars.example` (FR-004/FR-004a).
- Applies fire only on PR (staging) / `v*` tag (production) — never a bare `master` push
  (Principle V).
- Commit after each task or logical group; `<emoji> [TYPE] <msg>` message format.
