#!/usr/bin/env bash
# Rebuilds the git-ignored infra/terraform/github/secrets/*.tfvars from the
# base64 TF_TFVARS_* repo secrets (the same source terraform.yml consumes), then
# runs scripts/tfvars_to_env.py to explode the secret / ${{...}}-reference values
# .railway/railway.ts reads via process.env.X (025-iac-provisioning T6-08c) into
# $GITHUB_ENV for the steps that follow.
#
# `need()` in railway.ts throws on a missing var, so a bad materialize fails the
# plan loudly rather than surfacing later at apply.
#
# Arg:  $1 = staging | production
# Env:  TF_TFVARS_{GITHUB,RAILWAY}_{SHARED,STAGING,PRODUCTION}
#         - base64-encoded tfvars, set as step `env:` from repo secrets
#       GITHUB_WORKSPACE, GITHUB_ENV
#         - provided by Actions
set -euo pipefail

ENV_NAME="${1:?usage: railway-materialize-tfvars.sh <staging|production>}"

cd "$GITHUB_WORKSPACE/infra/terraform/github"
printf '%s' "$TF_TFVARS_GITHUB_SHARED"  | base64 -d > secrets/github-shared.tfvars
printf '%s' "$TF_TFVARS_RAILWAY_SHARED" | base64 -d > secrets/railway-shared.tfvars
case "$ENV_NAME" in
  staging)
    printf '%s' "$TF_TFVARS_GITHUB_STAGING"  | base64 -d > secrets/github-staging.tfvars
    printf '%s' "$TF_TFVARS_RAILWAY_STAGING" | base64 -d > secrets/railway-staging.tfvars ;;
  production)
    printf '%s' "$TF_TFVARS_GITHUB_PRODUCTION"  | base64 -d > secrets/github-production.tfvars
    printf '%s' "$TF_TFVARS_RAILWAY_PRODUCTION" | base64 -d > secrets/railway-production.tfvars ;;
  *)
    echo "::error::unknown environment '$ENV_NAME' (expected staging|production)"; exit 1 ;;
esac

cd "$GITHUB_WORKSPACE"
python scripts/tfvars_to_env.py --env "$ENV_NAME" >> "$GITHUB_ENV"
