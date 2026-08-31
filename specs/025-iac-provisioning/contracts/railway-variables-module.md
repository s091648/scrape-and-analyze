# Module Contracts: `railway-service` and `railway-variables`

**Revised during implementation** (research.md §9): a single per-environment `railway-service` module — as originally specified below this line in earlier drafts — turned out not to be viable. The `railway_service` Terraform resource reads/writes exactly one Railway `ServiceInstance`, always the project's *primary* environment (production, for this project), regardless of which environment a module instance is nominally "for." Declaring it in both `environments/staging/main.tf` and `environments/production/main.tf` would make both workspaces manage the identical underlying object. `railway_variable`, by contrast, genuinely is scoped per-environment (confirmed against Railway's real API and this project's real, differing staging/production cron schedules) and has no such conflict.

The module boundary is therefore split in two:

## `railway-service` — instantiated exactly once per app service, from `environments/production/main.tf` only

### Inputs

| Name | Type | Required | Description |
|---|---|---|---|
| `service_name` | `string` | yes | Must match the service's existing Railway service name exactly (e.g. `scrape-and-analyze`) |
| `railway_project_id` | `string` | yes | Passed from the root config's shared project reference |
| `source_repo` | `string` | yes | `s091648/scrape-and-analyze` or `s091648/chatbot-plugin` (Principle V's two-repo split) — registration metadata; actual deploys still happen via `railway up` (CLI push), not git-integration auto-deploy |
| `root_directory` | `string` | no (default `/`) | Subdirectory within `source_repo` (e.g. `/frontend`) |

### Outputs

| Name | Type | Description |
|---|---|---|
| `railway_service_id` | `string` | Consumed cross-workspace by `environments/staging/main.tf` via `terraform_remote_state` (production is the only place this exists) |

### Behavioral contract

- MUST NOT set `config_path`/`railwayConfigFile` — confirmed via the real project's data that none of the ten services use it; `railway up`'s own local `railway.toml` detection at CLI-push time is what actually governs build/start config, untouched by Terraform.
- MUST NOT manage Railway database/plugin services (FR-014) — Redis/Postgres in this project stay manual.

## `railway-variables` — instantiated once per (service × environment), from both `environments/{staging,production}/main.tf`

### Inputs

| Name | Type | Required | Description |
|---|---|---|---|
| `service_id` | `string` | yes | From `railway-service`'s output (production) or `terraform_remote_state` (staging) |
| `railway_environment_id` | `string` | yes | This IS genuinely per-environment — the whole reason this module is separate from `railway-service` |
| `variables` | `map(object({ value = string, sensitive = bool }))` | yes (may be empty map) | One entry per environment variable. `sensitive = true` entries MUST receive their `value` from a `TF_VAR_*`-injected root variable, never a literal in `.tfvars` (FR-004a) |

### Outputs

| Name | Type | Description |
|---|---|---|
| `variable_names` | `list(string)` | Names of all variables this instance manages — used by `terraform plan` review and, informally, by anyone auditing which keys are IaC-managed vs. still manual (FR-010) |

### Behavioral contract

- A `variables` entry may hold a reference-string value (e.g. `${{Redis.REDIS_URL}}`) pointing at a manually-managed database service; the module never creates the referenced service itself (FR-014).
- A `variables` map key removed between applies MUST result in that variable being destroyed on the next apply (visible as a `-` in `terraform plan`, satisfying FR-011) — not silently orphaned.
