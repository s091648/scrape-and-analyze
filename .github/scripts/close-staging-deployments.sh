#!/usr/bin/env bash
# Removes each staging Railway service's deployment once its PR is merged.
# Called from close-staging.yml — counterpart to check-staging-deployments.sh,
# which revives these same services at PR start.
#
# Reads service IDs from SERVICE_ID_* env vars (set by the calling step) and
# RAILWAY_TOKEN for CLI auth. Exits non-zero if any removal fails.
set -uo pipefail
FAILED=0

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/lib/railway-services.sh"

for name in "${!SERVICES[@]}"; do
  id="${SERVICES[$name]}"
  echo "::group::Removing $name ($id)"
  if ! railway down --yes --service "$id" --environment staging; then
    echo "::error::Failed to remove staging deployment for $name"
    FAILED=1
  fi
  echo "::endgroup::"
done

exit $FAILED
