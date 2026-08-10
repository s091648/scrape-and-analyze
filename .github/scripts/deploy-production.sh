#!/usr/bin/env bash
# Deploys every production Railway service. Called from release.yml after
# the production DB migration step.
#
# chatbot-plugin has its own repo, own CI, and own version tags (see its
# .github/workflows/release.yml). Unlike the other services here, production
# only ever deploys a submodule commit that's actually been tagged there —
# staging (ci.yml's check-staging-deployments.sh) still deploys whatever the
# submodule pointer currently is, untagged or not, since that's a preview
# environment, not a release.
#
# Reads service IDs from SERVICE_ID_* env vars (set by the calling step) and
# RAILWAY_TOKEN for CLI auth.
set -euo pipefail

railway up --detach --service "$SERVICE_ID_DASHBOARD_FRONTEND"  # dashboard-frontend
railway up --detach --service "$SERVICE_ID_DASHBOARD_BACKEND"  # dashboard-backend
railway up --detach --service "$SERVICE_ID_STORYBOOK"  # storybook UI
railway up --detach --service "$SERVICE_ID_SCRAPE_AND_ANALYZE"  # scrape-and-analyze

CHATBOT_TAG=$(cd chatbot-plugin && git fetch --tags origin -q && git tag --points-at HEAD | grep '^v' | head -1 || true)
if [ -n "$CHATBOT_TAG" ]; then
  echo "chatbot-plugin pinned to tag $CHATBOT_TAG — deploying"
  (cd chatbot-plugin && railway up --detach --service "$SERVICE_ID_CHATBOT_PLUGIN")
else
  echo "::warning::chatbot-plugin submodule commit $(cd chatbot-plugin && git rev-parse HEAD) has no version tag (v*) — skipping its production deploy. Cut a release tag in chatbot-plugin's own repo and bump the submodule pointer to deploy it."
fi

railway up --detach --service "$SERVICE_ID_FASTEMBED"  # fastembed
railway up --detach --service "$SERVICE_ID_WEEKLY_REPORT"  # weekly-report
railway up --detach --service "$SERVICE_ID_REFRESH_METRICS"  # refresh-metrics
railway up --detach --service "$SERVICE_ID_RAG_BACKFILL"  # rag-backfill
railway up --detach --service "$SERVICE_ID_DEDUP_RECONCILE"  # dedup-reconcile
