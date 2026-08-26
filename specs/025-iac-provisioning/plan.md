# Implementation Plan: Infrastructure as Code for Deployment Environments

**Branch**: `025-iac-provisioning` | **Date**: 2026-08-26 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/025-iac-provisioning/spec.md`

**Note**: This template is filled in by the `/speckit-plan` command. See `.specify/templates/plan-template.md` for the execution workflow.

## Summary

Replace manual Railway-dashboard and GitHub-Settings configuration with Terraform: a `railway-service` module declares each of the ten app services' environment variables per environment (staging/production), and a `github-ci-config` module declares the GitHub Actions secrets/variables `ci.yml`/`release.yml` read — both applied from the same declarative source of truth. Two HCP Terraform (Terraform Cloud) workspaces hold remote, encrypted, access-restricted state (one per environment), satisfying the spec's secret-handling requirement without introducing a new cloud account. Applies are wired into the existing PR-gated staging deploy (`ci.yml`) and tag-gated production release (`release.yml`) jobs — never a bare merge to `master` — per Constitution Principle V. Railway's own managed database services (Redis/Postgres) and exactly two bootstrap credentials (an HCP Terraform API token and a GitHub secrets-scoped PAT) stay manually managed, as the spec's Clarifications already establish.

## Technical Context

**Language/Version**: HCL (Terraform CLI >= 1.9), plus Bash for CI glue (matches the existing `.github/scripts/*.sh` convention) and Makefile targets (matches Principle IV's "Makefile as interface")

**Primary Dependencies**: `terraform-community-providers/railway` (~> 0.6, community-maintained — see research.md for known gaps), `integrations/github` (~> 6.0, HashiCorp-registry tier)

**Storage**: Remote Terraform state in HCP Terraform (Terraform Cloud), free tier, one workspace per environment (`scrape-analyzer-staging`, `scrape-analyzer-production`) — encrypted at rest, access-restricted, with built-in state locking; no application database involved

**Testing**: `terraform fmt -check` + `terraform validate` + `terraform plan` (plan-only) run in `ci.yml` for any PR touching `infra/terraform/**`, giving a reviewable diff on the PR itself; real applies happen only in the existing staging/production deploy jobs

**Target Platform**: GitHub Actions (`ubuntu-latest`) runners invoking the Terraform CLI; managed resources live on Railway and in this repository's GitHub Actions secrets/variables store

**Project Type**: Infra/tooling addition to an existing multi-service monorepo — a new top-level `infra/terraform/` directory, not a runtime service

**Performance Goals**: N/A (not a runtime service); operationally, a full `terraform apply` for one environment should stay well under the existing CI job timeouts (staging jobs have no explicit timeout today; production/`release.yml` has none either, so no new numeric budget is introduced — just "doesn't materially lengthen the pipeline")

**Constraints**: HCP Terraform free tier allows 1 concurrent run per workspace (non-issue — staging and production already apply sequentially via existing `concurrency:` groups) and up to 500 managed resources (this feature's footprint is ~100–150: 10 services × ~handful of variables × 2 environments + GitHub Actions secrets/variables); secret plaintext MUST NOT enter git (FR-004); IaC applies MUST fire only on the same triggers `railway up` already uses today — PR events for staging, `v*` tags for production (Constitution Principle V) — never on a bare push to `master`

**Scale/Scope**: 10 app services × 2 environments (FR-001) + the GitHub Actions secrets/variables `ci.yml`/`release.yml` already reference (FR-012) + 2 standing bootstrap credentials outside IaC scope (FR-013); Railway's managed database services stay manual (FR-014)

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Check | Result |
|---|---|---|
| V. Explicit CI/CD Deployment Boundary | IaC apply MUST fire only on the same PR/tag triggers `railway up` already uses, never on bare `master` push | **PASS by design** — Phase 1 wires the new Terraform apply step into the existing `deploy-staging-*`/`release.yml` jobs, reusing their `if:`/`concurrency:` gating rather than adding a new trigger |
| IV. Docker-First Local Development / "Makefile as interface" | All developer-facing operations MUST be exposed via Makefile targets | **PASS by design** — Phase 1 adds `make terraform-plan`/`make terraform-apply ENV=...` alongside the existing `make migrate`/`make scrape` targets |
| IX. FastAPI Microservice Structure — env var discipline | `.env.example` is documented as "the Railway shared-variable source of truth" | **No conflict** — `.env.example` continues to document *which keys* a service expects for local dev; Terraform becomes authoritative for *what value* is actually applied to Railway/CI per environment. Phase 1's data-model notes this split explicitly so it isn't rediscovered as an ambiguity later |
| III. Test Discipline / Docker-only test execution | All test runs MUST execute inside Docker via Makefile targets | **Adapted, not violated** — Terraform has no pytest/Vitest equivalent; its "test" is `terraform validate`/`plan`, which this plan runs as a CI job (not a local Docker test container, since it needs real provider credentials against a remote backend). No existing project convention is bypassed — there was none for HCL before this feature |
| I/II/VI/VII/VIII (DDD, Atomic Frontend, Observability, Code Style, UML) | Not applicable — this feature touches no `src/`, `backend/`, or `frontend/` application code | **N/A** |

No violations requiring Complexity Tracking justification.

**Post-Phase-1 re-check**: data-model.md, contracts/, and quickstart.md were reviewed against this table after Phase 1 design — no new violations introduced. The `railway-service` module's explicit "does not re-declare `railway.toml` build/start config" rule (data-model.md, contracts/railway-service-module.md) and the CI integration steps in quickstart.md (PR-gated staging apply, tag-gated production apply, no bare-`master`-push apply) both confirm the "PASS by design" rows above rather than introduce new risk. Gate remains **PASS**.

## Project Structure

### Documentation (this feature)

```text
specs/025-iac-provisioning/
├── plan.md              # This file (/speckit-plan command output)
├── research.md          # Phase 0 output (/speckit-plan command)
├── data-model.md        # Phase 1 output (/speckit-plan command)
├── quickstart.md        # Phase 1 output (/speckit-plan command)
├── contracts/           # Phase 1 output (/speckit-plan command)
│   ├── railway-service-module.md
│   └── github-ci-config-module.md
└── tasks.md             # Phase 2 output (/speckit-tasks command - NOT created by /speckit-plan)
```

### Source Code (repository root)

```text
infra/terraform/
├── modules/
│   ├── railway-service/         # One instance per app service (dashboard-backend, scrape-and-analyze, ...)
│   │   ├── main.tf              # railway_service (points at the service's existing railway.toml via config_path) + railway_variable resources
│   │   ├── variables.tf         # service name, railway project/environment IDs, map of variable name -> value|secret-ref
│   │   └── outputs.tf
│   └── github-ci-config/        # One instance per GitHub Environment (staging, production) + repo-level
│       ├── main.tf              # github_actions_secret / github_actions_variable / github_actions_environment_secret resources
│       ├── variables.tf
│       └── outputs.tf
├── environments/
│   ├── staging/
│   │   ├── main.tf               # instantiates railway-service x10 + github-ci-config, environment="staging"
│   │   ├── variables.tf
│   │   ├── terraform.tfvars      # non-secret values only; secret values come from TF_VAR_* injected by CI
│   │   └── backend.tf            # HCP Terraform workspace: scrape-analyzer-staging
│   └── production/
│       ├── main.tf                # same shape, environment="production"
│       ├── variables.tf
│       ├── terraform.tfvars
│       └── backend.tf            # HCP Terraform workspace: scrape-analyzer-production
├── versions.tf                    # shared required_providers version pins
└── README.md                      # links back to specs/025-iac-provisioning/quickstart.md

Makefile                           # + terraform-plan / terraform-apply targets (existing file, extended)
.github/workflows/ci.yml           # + terraform plan/apply step in the staging deploy path (existing file, extended)
.github/workflows/release.yml      # + terraform apply step before/alongside the Railway deploy step (existing file, extended)
```

**Structure Decision**: A new top-level `infra/terraform/` directory, sibling to `src/`, `backend/`, `frontend/`, `models/` — this is cross-cutting deployment infrastructure, not part of any one service. Two shared modules (`railway-service`, `github-ci-config`) are instantiated once per app service / once per GitHub Environment respectively from two per-environment root configs (`environments/staging/`, `environments/production/`), each bound to its own HCP Terraform workspace. This mirrors the existing per-service `railway.toml` pattern (one small, focused config unit per service) while keeping the two environments structurally isolated (satisfies FR-003) and letting FR-010's incremental migration happen by adding one `module "railway-service"` block — and one corresponding `terraform import` — at a time.

## Complexity Tracking

*No Constitution Check violations — this section is intentionally empty.*
