# Module Contract: `github-ci-config`

The interface consumed by each environment root config (one instance per GitHub Environment) and optionally once at repo level, to satisfy FR-012's GitHub Actions secrets/variables scope.

## Inputs

| Name | Type | Required | Description |
|---|---|---|---|
| `repository` | `string` | yes | `owner/repo` this module targets — always this project's repo, passed once from the root config |
| `github_environment_name` | `string` | no (default `null`) | e.g. `scraper / staging`; when set, secrets/variables are created as environment-scoped (`github_actions_environment_secret`/environment variable); when `null`, they are repo-level |
| `secrets` | `map(string)`, sensitive | yes (may be empty map) | Keyed by secret name (e.g. `RAILWAY_TOKEN`, `DATABASE_URL`). Values MUST originate from `TF_VAR_*` injected at apply time (FR-004a) — a literal secret value in any `.tf`/`.tfvars` file is a contract violation |
| `variables` | `map(string)` | yes (may be empty map) | Keyed by variable name (e.g. `RAILWAY_SERVICE_ID_DASHBOARD_BACKEND`). Literal values in `terraform.tfvars` are fine — these are non-secret by definition |

## Outputs

| Name | Type | Description |
|---|---|---|
| `managed_secret_names` | `list(string)` | Names of secrets this instance manages, for `terraform plan` review — never includes values |
| `managed_variable_names` | `list(string)` | Names of variables this instance manages |

## Behavioral contract

- MUST NOT accept or emit `TF_API_TOKEN` or the GitHub PAT used by this module's own `integrations/github` provider block as entries in `secrets` — those are the two standing bootstrap credentials (FR-013, research.md §5) and are never self-referential inputs to this module.
- A `secrets`/`variables` map key removed between applies MUST result in that GitHub secret/variable being destroyed on the next apply — matching the `railway-service` module's contract, so drift/removal semantics are identical on both the Railway and GitHub sides.
- Provider authentication (the GitHub PAT) is configured once at the root `providers.tf` level, not per module instance — this module only ever *uses* an already-authenticated provider, it never manages the credential that authenticates it.
