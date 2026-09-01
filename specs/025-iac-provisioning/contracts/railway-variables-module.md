# Contract: `railway-services.json` (the Railway variable manifest)

**Revision 4 (2026-08-31, "Option A")** replaces the `railway-variables` Terraform
module with a JSON manifest + `scripts/push_railway_variables.py`. This file is
what earlier revisions' `railway-variables` module contract described; the module
no longer exists (see `plan.md` "Revision 4"). The GitHub half is unchanged — see
`github-ci-config-module.md`.

`infra/terraform/railway/railway-services.json` declares which environment
variables each of the ten Railway services gets. Values live in
`infra/terraform/railway/secrets/railway-{shared,<env>}.tfvars` (per-env wins),
plus `service_id_*` / `gh_env_railway_token` from `secrets/github-*.tfvars`.

## Shape

```jsonc
{
  "shared_groups": {
    "<group>": { "<RAILWAY_VAR_NAME>": "<tfvars_key>", ... },   // e.g. "grafana": { "GRAFANA_API_KEY": "grafana_api_key" }
    ...
  },
  "unmanaged_all": ["<RAILWAY_VAR_NAME>", ...],                  // never resolved / flagged / pruned, every service
  "services": {
    "<service_key>": {
      "service_id_key": "service_id_<service_key>",              // tfvars key holding the Railway service UUID
      "groups": ["<group>", ...],                                // shared_groups this service consumes
      "own": { "<RAILWAY_VAR_NAME>": "<tfvars_key>", ... },      // this service's non-shared vars
      "unmanaged": ["<RAILWAY_VAR_NAME>", ...],                  // optional, adds to unmanaged_all
      "redeploy": false                                          // optional; omit (=true) for always-on services
    },
    ...
  }
}
```

## Behavioral contract (`push_railway_variables.py`)

- **Resolve.** For a service, merge its `groups` then `own` into
  `{RAILWAY_NAME: tfvars_key}`, look each `tfvars_key` up in the merged
  `railway-{shared,<env>}.tfvars` (+ `github-*` for `service_id_*`).
  - A tfvars value that is **absent or `""`** is skipped — Railway does not store
    empty variables, so sending one makes the CLI read-back inconsistent. An
    unset var and an empty var are equivalent.
  - Names listed in `unmanaged` / `unmanaged_all` are skipped entirely (not
    resolved, not drift-checked, not pruned).
  - `"$${{ … }}"` in the tfvars (HCL-escaped) is un-escaped to `"${{ … }}"` before
    sending; Railway resolves the reference server-side (FR-014).
- **Push** (`--env <env>`): one `railway variables --set K=V … --skip-deploys` per
  service (atomic, no per-variable redeploy), then — unless `redeploy: false` or
  `--no-redeploy` — one `railway redeploy`. A redeploy that fails because the
  service has no redeployable latest deployment (cron/one-off between runs) is a
  warning, not an error.
- **Prune** (`--prune`; on in CI's `terraform.yml` apply): after the set, delete
  every live Railway var for that service that isn't in the resolved set and
  isn't `unmanaged` and isn't `RAILWAY_*` (Railway-injected). This is how a var
  removed from the manifest/tfvars is removed on Railway (FR-011).
- **Check** (`--check`): read-only diff, `+`/`~`/`-` per key, exit 2 on any drift.
  `~` is suppressed for reference-string (`${{`) values — the CLI reads them back
  resolved, so they are not value-comparable.
- Secret values arrive only via `-var-file`/the tfvars, never a literal in a
  tracked file (FR-004a). Railway service/environment/database objects stay
  manually managed (out of scope).
