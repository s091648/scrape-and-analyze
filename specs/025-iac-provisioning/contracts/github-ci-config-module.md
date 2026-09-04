# Module Contract: `github-ci-config`

Instantiated from `infra/terraform/github-ci.tf` — once repo-level
(`github_ci_repo`) and once environment-scoped (`github_ci_env`, with
`github_environment_name = "scraper / ${var.app_env}"`). Satisfies FR-012's
GitHub-Actions-secrets/variables scope.

**Revision 2 (2026-08-28)**: no `managed`/`baseline` split — every entry is
enforced.

## Inputs

| Name | Type | Required | Description |
|---|---|---|---|
| `repository` | `string` | yes | Repo name, no owner (the provider block is already owner-scoped). |
| `github_environment_name` | `string` | no (default `null`) | When set, entries are created environment-scoped (`github_actions_environment_secret`/`_variable`); when `null`, repo-level. |
| `secrets` | `map(string)` | yes (may be empty) | Keyed by secret name. Values MUST come from a `TF_VAR_*`/`-var-file` root variable, never a literal (FR-004a). A `null` value skips that key. |
| `variables` | `map(string)` | yes (may be empty) | Keyed by name. Non-secret; `null` skips. |

## Outputs

| Name | Type | Description |
|---|---|---|
| `managed_secret_names` | `list(string)` | Sorted names of the secrets this instance manages (never values). |
| `managed_variable_names` | `list(string)` | Sorted names of the variables this instance manages. |

## Behavioral contract

- Repo-level entries are declared ONLY in the repo-level instance (a repo secret
  is singular — declaring it per environment would make both workspaces fight
  over the same object). Keep their values in `secrets/shared.tfvars`.
- MUST NOT accept `TF_API_TOKEN` / `TF_GITHUB_TOKEN` / `TF_RAILWAY_TOKEN` as
  entries — those are the three FR-013 bootstrap credentials, created and stored
  manually.
- A key removed between applies MUST be destroyed on the next apply — same
  removal semantics as `railway-variables`.
- Provider auth (the GitHub PAT) is configured once at the root `providers.tf`,
  never per module instance.
