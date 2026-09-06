# infra/terraform/github  (+ `.railway/`)

IaC for the two deploy environments (staging, production). One `secrets/*.tfvars` source of truth (see Layout), **two independent halves**:

| Half | What | How |
| --- | --- | --- |
| **GitHub Actions secrets/variables** | the secrets/variables `ci.yml` / `release.yml` read | Terraform (`github-ci.tf` + `modules/github-ci-config`, `github` provider), per-env HCP Terraform workspace via `TF_WORKSPACE`. CI: `.github/workflows/terraform.yml` |
| **Railway service deploy config + env vars** | every service's build/start/networking/replicas + env vars | `.railway/railway.ts` + `railway config plan\|apply` (Revision 6). CI: `.github/workflows/railway-config.yml` |

> **Revision 6 (2026-09):** Railway deprecated config-as-code (`railway.toml`,
> hard cutoff 2026-12-01). The Railway half moved to Railway-native IaC — a
> single `.railway/railway.ts` driven by `railway config`. This retired the
> Revision-3/4 path (`src/railway-<svc>.toml`, `scripts/push_railway_variables.py`,
> `railway-services.json` as an authority). `railway-services.json` is **kept**
> only as the `scripts/tfvars_to_env.py` name-map + `generate_terraform_docs.py`
> source — no longer the "which service gets which var" authority (`railway.ts` is).

## Out of scope

- **Railway managed databases (Redis / Postgres) + environment objects** —
  hands-off (FR-014). `railway.ts` declares Redis/Postgres only so the
  whole-project `railway config` won't propose deleting them.
- Non-secret env values are literals in `.railway/constants.ts`; secret /
  `${{…}}`-reference values come from `scripts/tfvars_to_env.py` (reads
  `secrets/railway-*.tfvars`) → `process.env`, read in `railway.ts` via `need()`.
- Vars listed `unmanaged` in `railway-services.json` (`OPENROUTER_API_KEY`,
  `RESEND_API_KEY`, `RESEND_FROM_EMAIL`) stay hand-set on Railway — `railway.ts`
  keeps them `preserve()`.

## Layout

```
infra/terraform/github/
  versions.tf providers.tf backend.tf   github provider pin / auth / HCP backend (workspace via TF_WORKSPACE)
  variables.tf                          input schema (github_* used; the rest declared only so -var-file doesn't warn)
  locals.tf                             the workspace/app_env check block
  github-ci.tf                          module github_ci_repo + github_ci_env
  modules/github-ci-config/             repo-level vs environment-scoped GitHub secrets/variables
  railway-services.json                 RETAINED — tfvars_to_env.py name-map + docs source (not the authority)
  secrets/                              git-ignored except *.example
    github-{shared,staging,production}.tfvars   Terraform reads these (github-ci.tf)
    railway-{shared,staging,production}.tfvars  tfvars_to_env.py reads these (→ process.env for railway config)
    *.tfvars.example                            tracked — key lists, no values
                                               real files == GitHub secret TF_TFVARS_{GITHUB,RAILWAY}_* base64
  .env / .env.example                   bootstrap credentials (git-ignored / tracked template)

.railway/                               the Railway half (Revision 6)
  railway.ts                            the ctx-aware config `railway config` applies
  constants.ts                          de-preserve()d non-secret literal values
  Dockerfile / README.md               the railway_cli container + usage/gotchas
```

Environment selection: `TF_WORKSPACE=<env>` picks the HCP workspace;
`-var-file=secrets/github-shared.tfvars -var-file=secrets/github-<env>.tfvars`
layers the values (later wins) for Terraform. `railway config` picks the env from
its per-env project token (no `--environment` flag). `make terraform-* ENV=<env>`
/ `make railway-config-* ENV=<env>`; CI: `terraform.yml` + `railway-config.yml`.

## Bootstrap credentials

Read from `infra/terraform/github/.env` (git-ignored). Copy `.env.example`
(tracked — keys + docs, no values). `.env.local` is honoured as a fallback name.

| `.env` key | Used by | Notes |
| --- | --- | --- |
| `TF_API_TOKEN` | `terraform` (HCP backend / state) | re-exported as `TF_TOKEN_app_terraform_io`. CI: secret `TF_API_TOKEN` |
| `TF_GITHUB_TOKEN` | `github` provider (repo Secrets+Variables write) | dedicated PAT, not reused by other CI steps. re-exported as `GITHUB_TOKEN` / `TF_VAR_github_token`. CI: secret `TF_GITHUB_TOKEN` |
| `RAILWAY_TOKEN_STAGING` / `RAILWAY_TOKEN_PRODUCTION` | `make railway-config-*` | project-scoped, environment-bound Railway tokens (`railway config` has no `--environment` flag — the token picks the env). CI: the `scraper / <env>` Environment's `RAILWAY_TOKEN` (`gh_env_railway_token`) |

## Day-to-day

**Normal path:** edit the value in `secrets/*.tfvars` (or `.railway/railway.ts` /
`.railway/constants.ts` for non-secret / structural changes) → `make push-tfvars`
→ open a PR. CI applies both halves: `terraform.yml` (GitHub) + `railway-config.yml`
(Railway) — staging on the PR, production on a `v*` tag. `make push-tfvars` is
the only command you have to remember.

**Applying locally** (optional — when you don't want to wait for CI; needs `.env`):

```
# GitHub-side (github-ci.tf — DATABASE_URL, FRONTEND_URL, RAILWAY_SERVICE_ID_*, API keys, …)
make terraform-plan  ENV=staging
make terraform-apply ENV=staging

# Railway-side (.railway/railway.ts — deploy config + env vars; runs in railway_cli container)
make railway-config-plan  ENV=staging     # a clean plan == no drift
make railway-config-apply ENV=staging

# then, so CI doesn't report drift, sync all six tfvars to the TF_TFVARS_* secrets:
make push-tfvars
```

For the Railway half's toolchain, auth, and gotchas see **`.railway/README.md`**.
To plan-verify the `process.env` values locally, see that file's "v2 (T6-08c)"
note (`scripts/tfvars_to_env.py` + `.railway/.plan-with-env.mjs`).

## Browsing what's declared

`site/guide/architecture/terraform-services.md` (VitePress) is auto-generated by
`scripts/generate_terraform_docs.py` from `railway-services.json` +
`github-ci.tf` (static parse, no `terraform` call, never a secret value).
Regenerate with `make uml-terraform-docs`.
