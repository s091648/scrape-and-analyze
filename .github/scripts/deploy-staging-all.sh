#!/usr/bin/env bash
# Deploys every staging Railway service. Called from release.yml's
# release-test-staging job only — the "this tag isn't on master" path used to
# test infra/terraform changes (specs/025-iac-provisioning T030) without
# touching production. The routine per-PR staging deploy is still ci.yml's
# ten deploy-staging-* jobs; this script exists so one job can do the same
# thing in a single step for a tag-triggered run.
#
# Unlike deploy-production.sh, chatbot-plugin is deployed unconditionally
# here (no v* tag gating) — staging is a preview environment, matching
# ci.yml's check-staging-deployments.sh convention, not a real release.
# `railway up` also recreates a fully REMOVED service same as a healthy one
# (see check-staging-deployments.sh), so this alone both wakes up anything
# torn down since the last PR and puts this tag's own code on every service —
# no separate revive step needed first.
#
# Reads service IDs from SERVICE_ID_* env vars (set by the calling step) and
# RAILWAY_TOKEN for CLI auth.
set -euo pipefail

railway up --detach --service "$SERVICE_ID_DASHBOARD_FRONTEND" --environment staging  # dashboard-frontend
railway up --detach --service "$SERVICE_ID_DASHBOARD_BACKEND" --environment staging  # dashboard-backend
railway up --detach --service "$SERVICE_ID_STORYBOOK" --environment staging  # storybook UI
railway up --detach --service "$SERVICE_ID_SCRAPE_AND_ANALYZE" --environment staging  # scrape-and-analyze
(cd chatbot-plugin && railway up --detach --service "$SERVICE_ID_CHATBOT_PLUGIN" --environment staging)
railway up --detach --service "$SERVICE_ID_FASTEMBED" --environment staging  # fastembed
railway up --detach --service "$SERVICE_ID_WEEKLY_REPORT" --environment staging  # weekly-report
railway up --detach --service "$SERVICE_ID_REFRESH_METRICS" --environment staging  # refresh-metrics
railway up --detach --service "$SERVICE_ID_RAG_BACKFILL" --environment staging  # rag-backfill
railway up --detach --service "$SERVICE_ID_DEDUP_RECONCILE" --environment staging  # dedup-reconcile
