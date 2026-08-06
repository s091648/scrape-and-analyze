#!/usr/bin/env bash
# Checks each staging Railway service's latest deployment status and
# redeploys from master any that are REMOVED. Called from ci.yml's
# check-staging-deployments job — see that job for why this needs to run
# before migrate/tests fire against staging.
#
# Reads service IDs from SERVICE_ID_* env vars (set by the calling step) and
# RAILWAY_TOKEN for CLI auth. Exits non-zero if any service's status can't be
# determined or a redeploy fails.
set -uo pipefail
FAILED=0

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/lib/railway-services.sh"
source "$SCRIPT_DIR/lib/require-node.sh"
require_node

# See lib/find-status.js for what this parses and why.
find_status() {
  node "$SCRIPT_DIR/lib/find-status.js" "$1"
}

for name in "${!SERVICES[@]}"; do
  id="${SERVICES[$name]}"
  echo "::group::Checking $name ($id)"

  CLI_OK=1
  if ! JSON=$(railway deployment list --service "$id" --environment staging --json 2>&1); then
    CLI_OK=0
  fi
  STATUS=$(find_status "$JSON")
  if [ "$STATUS" = "UNKNOWN" ] && [ "$CLI_OK" = "1" ]; then
    if ! JSON=$(railway status --service "$id" --environment staging --json 2>&1); then
      CLI_OK=0
    fi
    STATUS=$(find_status "$JSON")
  fi
  echo "Latest deployment status for $name: $STATUS"

  if [ "$CLI_OK" = "0" ]; then
    echo "::error::Railway CLI call failed for $name — treating as a failure rather than assuming healthy"
    FAILED=1
  elif [ "$STATUS" = "REMOVED" ]; then
    echo "$name is REMOVED — redeploying from master"
    if [ "$name" = "chatbot-plugin" ]; then
      if ! (cd chatbot-plugin && railway up --detach --service "$id" --environment staging); then
        echo "::error::Failed to redeploy $name"
        FAILED=1
      fi
    else
      if ! railway up --detach --service "$id" --environment staging; then
        echo "::error::Failed to redeploy $name"
        FAILED=1
      fi
    fi
  elif [ "$STATUS" = "UNKNOWN" ]; then
    echo "::warning::Could not determine deployment status for $name — skipping redeploy (assumed healthy)."
  else
    echo "$name is healthy ($STATUS) — no action needed"
  fi
  echo "::endgroup::"
done

exit $FAILED
