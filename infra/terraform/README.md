# infra/terraform

Declarative infrastructure for this project's Railway services and the GitHub Actions secrets/variables `ci.yml`/`release.yml` read. See `specs/025-iac-provisioning/` for the full spec/plan/research, and `specs/025-iac-provisioning/quickstart.md` for the bootstrap and day-to-day workflow.

## Out of scope

- **Railway's own managed database services** (Redis, Postgres, etc.) stay manually provisioned on Railway, as today. This feature only declares the app-service variables that *reference* them (e.g. a value like `${{Redis.REDIS_URL}}`) — see spec.md FR-014 and research.md §2/§9.
- **Creating a brand-new Railway service** still requires a manual first step (Railway dashboard, or `railway up --environment <name>`) — the `railway_service` Terraform resource has no way to target a specific environment at creation time, and separately only reads/writes the project's *primary* environment (production, for this project) once a service exists. See research.md §9. Once a service exists, everything else (variables, drift detection) is fully Terraform-managed.

## Layout

- `modules/railway-service/` — one instance per app service; registers the service (via its existing `railway.toml`, not duplicated here) and its environment variables.
- `modules/github-ci-config/` — one instance per GitHub Environment (`scraper / staging`, `scraper / production`) plus one repo-level instance, for the secrets/variables `ci.yml`/`release.yml` read.
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
