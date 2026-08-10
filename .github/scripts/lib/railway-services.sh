# Central declaration of the staging Railway services managed by this repo's
# CI: name -> service ID. Meant to be `source`d (not executed) by
# check-staging-deployments.sh, which iterates over staging services to
# revive any that were REMOVED.
#
# close-staging.yml (teardown) does NOT source this — it's a workflow_call
# reusable workflow invoked once per service directly from ci.yml, each call
# passing its own service_id input, so there's no shared loop to centralize.
#
# Requires the SERVICE_ID_* env vars already exported by the calling step
# (ci.yml sets these from vars.RAILWAY_SERVICE_ID_*).
#
# postgres/redis are intentionally NOT here: Railway's CLI has no reliable
# way to revive a fully-removed DB service (no deployment/image snapshot
# left to redeploy from — proven out by a `railway redeploy` failure: "No
# deployment found for service" once a DB's deployment history is gone).
# They stay up permanently instead; idle DB/cache cost is negligible next to
# the risk of an unrecoverable staging DB.
declare -A SERVICES=(
  [dashboard-backend]="$SERVICE_ID_DASHBOARD_BACKEND"
  [dashboard-frontend]="$SERVICE_ID_DASHBOARD_FRONTEND"
  [storybook]="$SERVICE_ID_STORYBOOK"
  [scrape-and-analyze]="$SERVICE_ID_SCRAPE_AND_ANALYZE"
  [chatbot-plugin]="$SERVICE_ID_CHATBOT_PLUGIN"
  [fastembed]="$SERVICE_ID_FASTEMBED"
  [weekly-report]="$SERVICE_ID_WEEKLY_REPORT"
  [refresh-metrics]="$SERVICE_ID_REFRESH_METRICS"
  [rag-backfill]="$SERVICE_ID_RAG_BACKFILL"
  [dedup-reconcile]="$SERVICE_ID_DEDUP_RECONCILE"
)
