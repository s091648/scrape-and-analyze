# infra/terraform

Declarative infrastructure for this project's Railway services and the GitHub Actions secrets/variables `ci.yml`/`release.yml` read. See `specs/025-iac-provisioning/` for the full spec/plan/research, and `specs/025-iac-provisioning/quickstart.md` for the bootstrap and day-to-day workflow.

## Out of scope

- **Railway's own managed database services** (Redis, Postgres, etc.) stay manually provisioned on Railway, as today. This feature only declares the app-service variables that *reference* them (e.g. a value like `${{Redis.REDIS_URL}}`) — see spec.md FR-014 and research.md §2/§9.
- **Creating a brand-new Railway service** still requires a manual first step (Railway dashboard, or `railway up --environment <name>`) — the `railway_service` Terraform resource has no way to target a specific environment at creation time, and separately only reads/writes the project's *primary* environment (production, for this project) once a service exists. See research.md §9. Once a service exists, everything else (variables, drift detection) is fully Terraform-managed.

## Layout

- `modules/railway-service/` — one instance per app service; registers the service (via its existing `railway.toml`, not duplicated here) and its environment variables.
- `modules/github-ci-config/` — one instance per GitHub Environment (`scraper / staging`, `scraper / production`) plus one repo-level instance, for the secrets/variables `ci.yml`/`release.yml` read.
- `modules/shared-variables/` — CDK-style central "constants": one secret input per shared value, grouped into named output maps (e.g. `grafana`, `sentry`) that multiple services `merge()` into their own `variables` map instead of each declaring the same baseline entry separately. One instance per environment (`module.shared_vars` in each root config) — the *grouping* is shared, each environment still supplies its own actual value via `TF_VAR_*`.
- `environments/staging/`, `environments/production/` — root configs, each its own HCP Terraform workspace (`scrape-analyzer-staging`, `scrape-analyzer-production` respectively) and its own state.

## Bootstrap credentials

Two credentials must exist before any `terraform` command in this directory will work — see quickstart.md for how to obtain them. They are read from `infra/terraform/.env.local` (gitignored, never commit):

| Credential | Purpose | Env var Terraform actually reads |
| --- | --- | --- |
| `TF_API_TOKEN` | Authenticates to the HCP Terraform backend (`app.terraform.io`) | Re-export as `TF_TOKEN_app_terraform_io` before invoking `terraform` (the `cloud` block only recognizes the CLI-standard `TF_TOKEN_<host>` name, not a custom one) |
| `TF_GITHUB_TOKEN` | Authenticates the `github` provider (needs repo Secrets+Variables write) | Re-export as `GITHUB_TOKEN` (the `github` provider's default; there is no `token_env_name` argument on the provider block) |
| `RAILWAY_TOKEN` (local `.env.local` name only) | Authenticates the `railway` provider — MUST be an **account/workspace-level** token, not the narrower project-scoped token `ci.yml`/`release.yml` already use for `railway up`/`railway down` | Read as-is locally (`RAILWAY_TOKEN` is the provider's own default env var name). **In CI, this same-shaped value MUST be stored under a *different* GitHub secret name — `TF_RAILWAY_TOKEN` — never as `secrets.RAILWAY_TOKEN`**, since that name is already the existing environment-scoped, project-level secret `railway up`/`railway down` depend on; overwriting it with the account-level value would break those steps. CI wires `TF_VAR_railway_token: ${{ secrets.TF_RAILWAY_TOKEN }}` |

## `TF_VAR_*` mapping (secret values injected at apply time, FR-004a)

Populated incrementally as secrets are brought under management — see Phase 4 (User Story 2) of `tasks.md`.

| `TF_VAR_*` | Consumed by | Notes |
| --- | --- | --- |
| `grafana_api_key`, `grafana_loki_url`, `grafana_loki_user`, `grafana_otlp_endpoint`, `grafana_otlp_user` | `module.shared_vars.grafana` (both environments) | Must exactly match the live value (pull it first with `make pull-railway-variables`) — this flips these from baseline (`managed=false`) to Terraform-owned (`managed=true`); a mismatched value overwrites the live one on apply |
| `sentry_dsn` | `module.shared_vars.sentry` (both environments) | Same caveat as above |

## Browsing what's declared

`site/guide/architecture/terraform-services.md` (VitePress docs site) covers both, from two complementary auto-generated sources — neither is ever hand-maintained, both regenerate on every docs build (`.github/workflows/speckit-github-pages.yml`):

- The main page content — every service declared here and which environment variables/GitHub Actions secrets each one needs *per environment* (**usage**) — comes from static HCL parsing (`scripts/generate_terraform_docs.py`, `python-hcl2` — never calls `terraform` itself, no credentials needed). Regenerate locally with `make uml-terraform-docs`. Never shows a secret's actual value (per FR-004a), only whether it's Terraform-managed or a Railway/GitHub-side baseline import.
- The collapsed "Terraform Modules" section at the bottom — each of the three modules' own inputs/outputs/resources/requirements (**interface**) — comes from the official [terraform-docs](https://terraform-docs.io/) tool (config: `infra/terraform/.terraform-docs.yml`), reformatted into nested `<details>` blocks by `scripts/wrap_terraform_module_doc.py`. Regenerate locally with `make uml-terraform-modules` (runs the official `quay.io/terraform-docs/terraform-docs` image, no credentials needed either).

## CI trigger cadence & Railway's API rate limit

Every `terraform plan`/`apply` against either environment refreshes **all** existing `railway_variable` resources (~150+ across both environments), one API call per resource. This is Railway's own API rate limit — independent of, and hit well before, HCP Terraform's — and a routine run of several review-iteration pushes on one PR can exhaust it (observed retry-after: ~40-45 minutes).

Because of this, `ci.yml`'s `terraform-plan`/`deploy-staging-terraform` jobs deliberately do **not** run on every PR push — only on `opened`/`reopened`. If a later push to an already-open PR changes `infra/terraform/**` and needs staging re-applied before merge, trigger it manually: Actions tab → **Terraform Staging (Manual)** → Run workflow (pick the PR's branch). That workflow also uses `plan -out=tfplan.out` + `apply tfplan.out` in the same job (rather than a bare `terraform apply`, which would refresh everything a second time) to roughly halve the API calls one run makes — prefer this pattern for any new terraform automation added here.

`release.yml`'s production apply isn't gated this way — it only runs once per tagged release, so it doesn't hit the same pattern in practice.

Local `make terraform-plan`/`terraform-apply` runs count against the same Railway rate limit budget as CI — avoid running one immediately after another (e.g. a `plan` right before an `apply`) when possible.

When a change is scoped to a single service/module, pass `TARGET=<resource address>` — e.g. `make terraform-apply ENV=staging TARGET=module.storybook_variables` — instead of a full-state `plan`/`apply`. Terraform's `-target` narrows *refresh* (not just the diff) to the targeted address and its dependencies, so it only makes API calls for that address's own `railway_variable`/`github_actions_*` resources rather than refreshing everything else already in state. Prefer a bare (untargeted) `plan`/`apply` only when you actually need to catch drift anywhere else in the environment too.
