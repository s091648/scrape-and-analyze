# Module Contract: `railway-variables`

**Revision 2 (2026-08-28)**: the `railway-service` module is deleted. Railway
service objects are not Terraform-managed — service IDs are stable UUIDs
supplied as `.tfvars` values (`service_id_<svc>`). This is the only Railway
module.

Instantiated once per service, from `infra/terraform/services/<svc>.tf`. One
flat root config, applied per environment against its own HCP workspace.

## Inputs

| Name | Type | Required | Description |
|---|---|---|---|
| `service_id` | `string` | yes | Stable Railway service UUID (from `var.service_id_<svc>`). |
| `environment_id` | `string` | yes | This environment's Railway environment UUID (`var.railway_environment_id`). |
| `variables` | `map(object({ value = optional(string), sensitive = optional(bool, false) }))` | yes (may be empty) | One entry per environment variable, keyed by name. |

## Outputs

| Name | Type | Description |
|---|---|---|
| `variable_names` | `list(string)` | Sorted names of every variable this instance manages *in the current environment* (after null-skip) — for `terraform plan` review / auditing. |

## Behavioral contract

- **Every entry is Terraform-managed.** The value is enforced on every apply.
  There is no `managed`/`baseline` split and no `lifecycle { ignore_changes }` —
  revision 2 removed it. The Railway dashboard is read-only for any variable
  declared here.
- **`value = null` (or the key absent from the merged map) ⇒ skip.** That
  variable is not created/managed for the current environment. This is how a key
  present in one environment's `secrets/<env>.tfvars` but not the other's stays a
  clean per-environment difference instead of Terraform trying to create it
  everywhere.
- `sensitive = true` entries MUST get their `value` from a `TF_VAR_*`/`-var-file`
  root variable, never a literal in a tracked file (FR-004a).
- A `variables` entry may hold a Railway reference string (e.g.
  `${{ Redis.REDIS_URL }}`) — a plain non-sensitive value Railway resolves
  server-side (FR-014). In `.tfvars` the leading `$` must be escaped as `$${`.
- A key removed from the merged map between applies MUST be destroyed on the
  next apply (visible as `-` in `terraform plan`, satisfying FR-011).
- `for_each` iterates `nonsensitive(local.active)` (a filtered copy) with the
  real value re-indexed from `local.active` — Terraform forbids `for_each` over a
  map carrying sensitive values.
