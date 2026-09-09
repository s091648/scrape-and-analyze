#!/usr/bin/env bash
# Applies .railway/railway.ts to one Railway environment: `railway config plan`
# into a local file, then `railway config apply` of exactly that file — both in
# the one CI job, no artifact round-trip.
#
# Why not railwayapp/config@v1's `apply` (which railway-config.yml still uses for
# `mode: plan`): its apply resolves the pinned plan by commit SHA from a
# SEPARATE, already-completed workflow run's artifact (the PR's own plan job). A
# push / tag / workflow_dispatch / reusable-call has no such prior run, so it
# fails with "No railway-plan-<env> artifact found for <sha>" — even though its
# own plan step just produced one. release.yml hit exactly this.
#
# NO-OP GUARD: when `railway config plan` reports the environment is already up
# to date, `railway config apply` is SKIPPED. Applying an empty pinned plan still
# makes the CLI open a Railway ChangeSet that never reaches a terminal state, so
# its own poll hangs until it prints "Timed out waiting for Railway ChangeSet
# apply" and exits 1 (observed repeatedly on staging, 2026-09). There is nothing
# to apply in that case anyway.
#
# `--yes` skips the interactive confirm. NO `--confirm-destructive`: a
# destructive plan fails loudly rather than landing silently (v1 railway.ts is
# preserve()-heavy, so today this is a near-no-op).
#
# Arg:  $1 = staging | production
#         - log lines + plan filename only; the environment is actually selected
#           by RAILWAY_TOKEN, as `railway config` has no --environment flag
# Env:  RAILWAY_TOKEN  - env-scoped Railway project token
#       RUNNER_TEMP    - provided by Actions
#       plus the process.env.X values exported by railway-materialize-tfvars.sh
set -euo pipefail

ENV_NAME="${1:?usage: railway-config-apply.sh <staging|production>}"
PLAN_FILE="${RUNNER_TEMP:-/tmp}/railway-plan-${ENV_NAME}.json"
PLAN_LOG="${RUNNER_TEMP:-/tmp}/railway-plan-${ENV_NAME}.log"

# railway.ts's `import "railway/iac"` runs the SDK's assertMinimumIacCliVersion(),
# which shells out to `$_ --version`. Under bash `$_` is not the CLI, so pin it —
# the same `env _=` workaround the `make railway-config-*` targets use.
RAILWAY_BIN="$(command -v railway)"
rw() { env _="$RAILWAY_BIN" "$RAILWAY_BIN" "$@"; }

echo "Planning .railway/railway.ts against ${ENV_NAME}…"
# tee so the plan still streams to the CI log while we keep a copy to inspect.
# pipefail (set above) makes a `railway config plan` failure still abort here.
rw config plan --out "$PLAN_FILE" 2>&1 | tee "$PLAN_LOG"

# `railway config plan` prints "...configuration is already up to date." when the
# pinned plan holds no changes. Applying that empty plan is what hangs the CLI on
# a never-terminating ChangeSet (see NO-OP GUARD above), so short-circuit it.
if grep -qiE 'already up to date' "$PLAN_LOG"; then
  echo "No changes in the pinned plan for ${ENV_NAME} — skipping \`railway config apply\`."
  exit 0
fi

echo "Applying the pinned plan to ${ENV_NAME}…"
rw config apply --plan "$PLAN_FILE" --yes
