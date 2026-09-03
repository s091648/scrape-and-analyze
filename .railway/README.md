# Railway configuration

This project defines its Railway infrastructure in code.

```txt
.railway/railway.ts
```

Use this file to describe the Railway project you want: services, databases, buckets, custom domains, replicas, groups, and environment variables.

`railway config plan` needs **both** the genuine Rust CLI (>= 5.42.1) **and** the
`railway` npm SDK that `railway.ts` imports (`import "railway/iac"`). The
`railway_cli` container bakes both in: the CLI from Railway's official standalone
installer (the `npm i -g @railway/cli` binary has shipped too old for the IaC
engine even at `@latest`), and the SDK at `/node_modules` so a parent-dir walk
from `/work/.railway/railway.ts` resolves it. The SDK's `assertMinimumIacCliVersion`
shells out to `$_ --version`, which under `make`/`sh` isn't `railway` — the
`make railway-config-*` targets run `env _=/usr/local/bin/railway railway …` so
that check sees the real CLI.

## Running it (Docker — the Windows CLI can't evaluate this .ts)

`railway config` evaluates `railway.ts` via Node type-stripping and the Windows
CLI build trips on it. Run everything in the `railway_cli` container instead
(`.railway/Dockerfile`, compose profile `tools`):

```bash
make railway-cli                          # interactive shell — `railway login` / `railway link` persist
make railway-config-plan  ENV=staging     # preview, safe
make railway-config-plan  ENV=production
make railway-config-apply ENV=production  # apply, interactive confirm
make railway-config-pull  ENV=staging     # fresh ground truth -> .railway/pulled.staging.ts (railway.ts untouched)
make railway-config-migrate               # fold every railway.toml into railway.ts
```

The targets are dual-mode: from the host they spawn the container; inside a
`make railway-cli` shell the *same* `make railway-config-*` commands run directly
(`make` and the Makefile are both in the container — `.` is mounted at `/work`).

**Auth** — two ways, in this order of preference:

1. **Per-env project token** in git-ignored `infra/terraform/railway/.env` as
   `RAILWAY_TOKEN_STAGING` / `RAILWAY_TOKEN_PRODUCTION` (Railway dashboard →
   project → Settings → Tokens → New Token → pick the env). The targets read
   `RAILWAY_TOKEN_<ENV>` and pass it as `-e RAILWAY_TOKEN` for that one command.
   The token pins the environment, so `ENV=` is enforced.
2. **Persisted `railway login`** — if `RAILWAY_TOKEN_<ENV>` is empty, the command
   uses the login session in the `/root/.railway` volume (do `railway login
   --browserless` once in `make railway-cli`). `railway config` has **no
   `--environment` flag**, so it targets whatever `railway link` last selected —
   `ENV=` is NOT enforced; run `railway status` to confirm before `apply`.

Add flags via `ARGS=`, e.g. `make railway-config-plan ENV=staging ARGS="--out railway-plan.json"`.

### Verifying this file against live (the v1 goal)

`railway.staging.ts` / `railway.production.ts` are the raw `railway config pull`
of each environment; `railway.ts` is the hand-merged ctx-aware union of them.
`railway config plan` **is** the authoritative diff between `railway.ts` and live,
so the v1 gate is simply:

```bash
make railway-config-plan ENV=staging      # must report no changes
make railway-config-plan ENV=production   # must report no changes
```

Any diff → reconcile `railway.ts` (or a `// REVIEW:` marker) and re-plan. Re-pull
fresh ground truth with `make railway-config-pull ENV=<env>` if the two reference
files are stale. **FR-014**: if a plan shows ANY change to Redis / Postgres / a
volume, stop — do not apply.

**v2 (T6-08c) — plan needs `process.env` populated.** `railway.ts` now reads
secret / `${{...}}`-reference values via `process.env.X` (in CI:
`railway-config.yml` runs `scripts/tfvars_to_env.py --env <env>` into
`$GITHUB_ENV`). To plan locally the same way:

```bash
python scripts/tfvars_to_env.py --env staging > .railway/.env.staging.generated
# then, in the railway_cli container (all git-ignored):
node .railway/.plan-with-env.mjs .railway/.env.staging.generated plan --show-values
```

`.plan-with-env.mjs` just loads the `KEY=value` file into `process.env` (first
`=` splits) and execs `railway config …` — `railway config` can't take an
`--env-file` and `source`-ing the file mangles `${{ }}` / trailing `=`.

## Common commands

Create the configuration files:

```bash
railway config init
```

Import an existing Railway project into code:

```bash
railway config pull
```

Preview what Railway would change:

```bash
railway config plan
```

Apply the planned changes:

```bash
railway config apply
```

## Notes

- `railway config plan` is safe and does not change Railway.
- `railway config apply` previews changes and asks before applying unless you pass `--yes`.
- Destructive changes in non-interactive or agent sessions require `railway config apply --confirm-destructive` after reviewing the plan.
- CI should pin a plan (`railway config plan --out railway-plan.json`) and apply that file on merge (`railway config apply --plan railway-plan.json --yes --confirm-destructive`) so the reviewed change set is what lands. On GitHub Actions, use https://github.com/railwayapp/config.
- Services already managed by `railway.json` must be migrated before `.railway/railway.ts` can manage them.
- Keep one `.railway` file for the whole project. A named `export const partial` (or `PARTIAL` / `const Partial`) is a last resort for separate repos that cannot share that file. Do not add it unless omit=delete across repos is a blocker.
- Use `replicas` for scaling; advanced placement can still specify region names.
- Use `group("Name", [resources])` to keep large projects organized on the Railway canvas.
- Secrets imported from Railway are rendered as `preserve()` so existing values are retained without writing secret values to source. Use `railway config pull --omit-preserved-variables` for a smaller import. `railway config pull --include-variables` decrypts and inlines non-sealed values (including secrets that were never sealed).
- `railway config migrate` finds every `railway.json` / `railway.toml` in the repository and writes them into this one file.
