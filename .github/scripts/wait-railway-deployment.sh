#!/usr/bin/env bash
# Polls a Railway service's most recent deployment until it is live (SUCCESS), so a job
# that `needs:` the deploy (ci.yml's lighthouse-check) audits *this* build rather than the
# previous one still serving traffic. `railway up --ci` already blocks until the build
# finishes, but the deployment still has to boot and pass its healthcheck after that.
#
# Before this existed the frontend deploy used `railway up --detach` (returns as soon as the
# upload is accepted) and lighthouse.yml's reachability probe was satisfied immediately by the
# old deployment — every Lighthouse report measured the previous commit's frontend.
#
# `railway up` doesn't report the ID of the deployment it creates, so the caller records the
# latest deployment ID *before* `railway up` (`--latest-id`) and passes it back in: until a
# deployment with a different ID tops the list, the listed SUCCESS is the old deployment and
# doesn't count.
#
# Usage: wait-railway-deployment.sh --latest-id <service_id> <environment>
#        wait-railway-deployment.sh <service_id> <environment> [previous_deployment_id] [timeout_seconds]
# Requires RAILWAY_TOKEN. Parsing lives in lib/latest-deployment.js (first object with both
# `id` and `status` in `railway deployment list --json`, i.e. the most recent deployment).
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

latest() {  # prints "<id> <status>" of the service's most recent deployment
  local json
  if json=$(railway deployment list --service "$1" --environment "$2" --json 2>&1); then
    node "$SCRIPT_DIR/lib/latest-deployment.js" "$json"
  else
    echo "UNKNOWN UNKNOWN"
  fi
}

if [ "${1:-}" = "--latest-id" ]; then
  read -r ID _ <<< "$(latest "$2" "$3")"
  echo "$ID"
  exit 0
fi

SERVICE_ID="$1"
ENVIRONMENT="$2"
PREVIOUS_ID="${3:-}"
TIMEOUT="${4:-600}"
DEADLINE=$(( $(date +%s) + TIMEOUT ))

while true; do
  read -r ID STATUS <<< "$(latest "$SERVICE_ID" "$ENVIRONMENT")"
  if [ -n "$PREVIOUS_ID" ] && [ "$PREVIOUS_ID" != "UNKNOWN" ] && [ "$ID" = "$PREVIOUS_ID" ]; then
    echo "Latest deployment is still the pre-existing $ID ($STATUS); waiting for the new one"
    STATUS="PENDING_NEW"
  else
    echo "Latest deployment $ID status: $STATUS"
  fi
  case "$STATUS" in
    SUCCESS) exit 0 ;;
    FAILED|CRASHED|REMOVED)
      echo "::error::Latest deployment ended as $STATUS"
      exit 1 ;;
  esac
  if [ "$(date +%s)" -ge "$DEADLINE" ]; then
    echo "::error::Deployment did not become live within ${TIMEOUT}s (last status: $STATUS)"
    exit 1
  fi
  sleep 10
done
