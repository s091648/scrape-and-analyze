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
# Usage: wait-railway-deployment.sh <service_id> <environment> [timeout_seconds]
# Requires RAILWAY_TOKEN. Status parsing reuses lib/find-status.js (first `status` field in
# `railway deployment list --json`, i.e. the most recent deployment).
set -uo pipefail

SERVICE_ID="$1"
ENVIRONMENT="$2"
TIMEOUT="${3:-600}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEADLINE=$(( $(date +%s) + TIMEOUT ))

while true; do
  if JSON=$(railway deployment list --service "$SERVICE_ID" --environment "$ENVIRONMENT" --json 2>&1); then
    STATUS=$(node "$SCRIPT_DIR/lib/find-status.js" "$JSON")
  else
    STATUS="UNKNOWN"
  fi
  echo "Latest deployment status: $STATUS"
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
