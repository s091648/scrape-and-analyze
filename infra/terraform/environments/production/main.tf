# Environment: production (Railway environment ID: see terraform.tfvars).
#
# There is no `railway_environment` data source in this provider (confirmed
# during the pre-implementation PoC — the provider has no data sources at
# all, research.md §9), so `var.railway_environment_id` is used directly as a
# plain reference rather than read/imported as a managed resource — this
# feature does not create or manage the Environment itself (spec Assumptions).

provider "railway" {
  token = var.railway_token
}

provider "github" {
  owner = var.github_owner
  token = var.github_token
}

# --- All ten app services (US1 T018/T020) ---
# Real Railway service names/root directories confirmed via the GraphQL API
# directly (research.md §9) — several differ from hyphen-guessed names.
# railway-variables instances are added in US2 (T023-T028) — US1's scope is
# service registration only.
module "dashboard_backend" {
  source = "../../modules/railway-service"

  service_name       = "dashboard-backend"
  railway_project_id = var.railway_project_id
  source_repo        = "s091648/scrape-and-analyze"
  root_directory     = "/"
}

module "dashboard_frontend" {
  source = "../../modules/railway-service"

  service_name       = "dashboard-frontend"
  railway_project_id = var.railway_project_id
  source_repo        = "s091648/scrape-and-analyze"
  root_directory     = "/frontend"
}

module "storybook" {
  source = "../../modules/railway-service"

  service_name       = "storybook UI"
  railway_project_id = var.railway_project_id
  source_repo        = "s091648/scrape-and-analyze"
  root_directory     = "/frontend"
}

module "scrape_and_analyze" {
  source = "../../modules/railway-service"

  service_name       = "scrape-and-analyze"
  railway_project_id = var.railway_project_id
  source_repo        = "s091648/scrape-and-analyze"
  root_directory     = "/"
  cron_schedule      = "0 8 * * *"
}

module "chatbot_plugin" {
  source = "../../modules/railway-service"

  service_name       = "chatbot-plugin"
  railway_project_id = var.railway_project_id
  source_repo        = "s091648/chatbot-plugin"
  root_directory     = null
}

module "fastembed" {
  source = "../../modules/railway-service"

  service_name       = "fastembed"
  railway_project_id = var.railway_project_id
  source_repo        = "s091648/scrape-and-analyze"
  root_directory     = "/"
}

module "weekly_report" {
  source = "../../modules/railway-service"

  service_name       = "weekly report"
  railway_project_id = var.railway_project_id
  source_repo        = "s091648/scrape-and-analyze"
  root_directory     = "/"
  cron_schedule      = "0 0 * * 1"
}

module "refresh_metrics" {
  source = "../../modules/railway-service"

  service_name       = "refresh metrics"
  railway_project_id = var.railway_project_id
  source_repo        = "s091648/scrape-and-analyze"
  root_directory     = "/"
  cron_schedule      = "0 20 * * *"
}

module "rag_backfill" {
  source = "../../modules/railway-service"

  service_name       = "backfill_rag"
  railway_project_id = var.railway_project_id
  source_repo        = "s091648/scrape-and-analyze"
  root_directory     = "/"
  cron_schedule      = "0 20 * * *"
}

module "dedup_reconcile" {
  source = "../../modules/railway-service"

  service_name       = "dedup_reconcile"
  railway_project_id = var.railway_project_id
  source_repo        = "s091648/scrape-and-analyze"
  root_directory     = "/"
  cron_schedule      = "0 20 * * *"
}

output "service_ids" {
  value = {
    dashboard-backend  = module.dashboard_backend.railway_service_id
    dashboard-frontend = module.dashboard_frontend.railway_service_id
    storybook          = module.storybook.railway_service_id
    scrape-and-analyze = module.scrape_and_analyze.railway_service_id
    chatbot-plugin     = module.chatbot_plugin.railway_service_id
    fastembed          = module.fastembed.railway_service_id
    weekly-report      = module.weekly_report.railway_service_id
    refresh-metrics    = module.refresh_metrics.railway_service_id
    rag-backfill       = module.rag_backfill.railway_service_id
    dedup-reconcile    = module.dedup_reconcile.railway_service_id
  }
  description = "Consumed by environments/staging/main.tf via terraform_remote_state (railway_service only ever exists here — research.md §9)."
}

module "dashboard_backend_variables" {
  source = "../../modules/railway-variables"

  service_id             = module.dashboard_backend.railway_service_id
  railway_environment_id = var.railway_environment_id
  variables = {
    APP_ENV                    = { value = "IMPORTED-BASELINE-VALUE-MANAGED-OUTSIDE-TERRAFORM", sensitive = true, managed = false }
    CACHE_REDIS_URL            = { value = "IMPORTED-BASELINE-VALUE-MANAGED-OUTSIDE-TERRAFORM", sensitive = true, managed = false }
    CHAT_SERVICE_API_KEY       = { value = "IMPORTED-BASELINE-VALUE-MANAGED-OUTSIDE-TERRAFORM", sensitive = true, managed = false }
    CHAT_SERVICE_URL           = { value = "IMPORTED-BASELINE-VALUE-MANAGED-OUTSIDE-TERRAFORM", sensitive = true, managed = false }
    DATABASE_URL               = { value = "IMPORTED-BASELINE-VALUE-MANAGED-OUTSIDE-TERRAFORM", sensitive = true, managed = false }
    FRONTEND_ORIGIN            = { value = "IMPORTED-BASELINE-VALUE-MANAGED-OUTSIDE-TERRAFORM", sensitive = true, managed = false }
    GEMINI_API_KEY             = { value = "IMPORTED-BASELINE-VALUE-MANAGED-OUTSIDE-TERRAFORM", sensitive = true, managed = false }
    GRAFANA_API_KEY            = { value = "IMPORTED-BASELINE-VALUE-MANAGED-OUTSIDE-TERRAFORM", sensitive = true, managed = false }
    GRAFANA_LOKI_URL           = { value = "IMPORTED-BASELINE-VALUE-MANAGED-OUTSIDE-TERRAFORM", sensitive = true, managed = false }
    GRAFANA_LOKI_USER          = { value = "IMPORTED-BASELINE-VALUE-MANAGED-OUTSIDE-TERRAFORM", sensitive = true, managed = false }
    GRAFANA_OTLP_ENDPOINT      = { value = "IMPORTED-BASELINE-VALUE-MANAGED-OUTSIDE-TERRAFORM", sensitive = true, managed = false }
    GRAFANA_OTLP_USER          = { value = "IMPORTED-BASELINE-VALUE-MANAGED-OUTSIDE-TERRAFORM", sensitive = true, managed = false }
    GRAFANA_PROMETHEUS_URL     = { value = "IMPORTED-BASELINE-VALUE-MANAGED-OUTSIDE-TERRAFORM", sensitive = true, managed = false }
    GRAFANA_PROMETHEUS_USER    = { value = "IMPORTED-BASELINE-VALUE-MANAGED-OUTSIDE-TERRAFORM", sensitive = true, managed = false }
    GRAFANA_TEMPO_URL          = { value = "IMPORTED-BASELINE-VALUE-MANAGED-OUTSIDE-TERRAFORM", sensitive = true, managed = false }
    GRAFANA_TEMPO_USER         = { value = "IMPORTED-BASELINE-VALUE-MANAGED-OUTSIDE-TERRAFORM", sensitive = true, managed = false }
    MAXMIND_LICENSE_KEY        = { value = "IMPORTED-BASELINE-VALUE-MANAGED-OUTSIDE-TERRAFORM", sensitive = true, managed = false }
    NEXTAUTH_SECRET            = { value = "IMPORTED-BASELINE-VALUE-MANAGED-OUTSIDE-TERRAFORM", sensitive = true, managed = false }
    RAG_DENSE_API_KEY_ENV      = { value = "IMPORTED-BASELINE-VALUE-MANAGED-OUTSIDE-TERRAFORM", sensitive = true, managed = false }
    RAG_DENSE_DIMENSION        = { value = "IMPORTED-BASELINE-VALUE-MANAGED-OUTSIDE-TERRAFORM", sensitive = true, managed = false }
    RAG_DENSE_ENDPOINT_URL     = { value = "IMPORTED-BASELINE-VALUE-MANAGED-OUTSIDE-TERRAFORM", sensitive = true, managed = false }
    RAG_DENSE_MODEL            = { value = "IMPORTED-BASELINE-VALUE-MANAGED-OUTSIDE-TERRAFORM", sensitive = true, managed = false }
    RAG_DENSE_PROVIDER         = { value = "IMPORTED-BASELINE-VALUE-MANAGED-OUTSIDE-TERRAFORM", sensitive = true, managed = false }
    RAG_DENSE_RPD              = { value = "IMPORTED-BASELINE-VALUE-MANAGED-OUTSIDE-TERRAFORM", sensitive = true, managed = false }
    RAG_DENSE_RPM              = { value = "IMPORTED-BASELINE-VALUE-MANAGED-OUTSIDE-TERRAFORM", sensitive = true, managed = false }
    RAG_DENSE_TPM              = { value = "IMPORTED-BASELINE-VALUE-MANAGED-OUTSIDE-TERRAFORM", sensitive = true, managed = false }
    RAG_GEMINI_API_KEY         = { value = "IMPORTED-BASELINE-VALUE-MANAGED-OUTSIDE-TERRAFORM", sensitive = true, managed = false }
    RAG_SPARSE_DIMENSION       = { value = "IMPORTED-BASELINE-VALUE-MANAGED-OUTSIDE-TERRAFORM", sensitive = true, managed = false }
    RAG_SPARSE_ENDPOINT_URL    = { value = "IMPORTED-BASELINE-VALUE-MANAGED-OUTSIDE-TERRAFORM", sensitive = true, managed = false }
    RAG_SPARSE_MODEL           = { value = "IMPORTED-BASELINE-VALUE-MANAGED-OUTSIDE-TERRAFORM", sensitive = true, managed = false }
    RAG_SPARSE_PROVIDER        = { value = "IMPORTED-BASELINE-VALUE-MANAGED-OUTSIDE-TERRAFORM", sensitive = true, managed = false }
    RAG_SPARSE_RPD             = { value = "IMPORTED-BASELINE-VALUE-MANAGED-OUTSIDE-TERRAFORM", sensitive = true, managed = false }
    RAG_SPARSE_RPM             = { value = "IMPORTED-BASELINE-VALUE-MANAGED-OUTSIDE-TERRAFORM", sensitive = true, managed = false }
    RAG_SPARSE_TPM             = { value = "IMPORTED-BASELINE-VALUE-MANAGED-OUTSIDE-TERRAFORM", sensitive = true, managed = false }
    REDIS_URL                  = { value = "IMPORTED-BASELINE-VALUE-MANAGED-OUTSIDE-TERRAFORM", sensitive = true, managed = false }
    SEARCH_INDEX_REDIS_URL     = { value = "IMPORTED-BASELINE-VALUE-MANAGED-OUTSIDE-TERRAFORM", sensitive = true, managed = false }
    SENTRY_DSN                 = { value = "IMPORTED-BASELINE-VALUE-MANAGED-OUTSIDE-TERRAFORM", sensitive = true, managed = false }
    SWAGGER_TRY_IT_OUT_ENABLED = { value = "IMPORTED-BASELINE-VALUE-MANAGED-OUTSIDE-TERRAFORM", sensitive = true, managed = false }
  }
}

module "dashboard_frontend_variables" {
  source = "../../modules/railway-variables"

  service_id             = module.dashboard_frontend.railway_service_id
  railway_environment_id = var.railway_environment_id
  variables = {
    APP_ENV                 = { value = "IMPORTED-BASELINE-VALUE-MANAGED-OUTSIDE-TERRAFORM", sensitive = true, managed = false }
    BACKEND_URL             = { value = "http://dashboard-backend2.railway.internal:8000", managed = true }
    CHAT_SERVICE_API_KEY    = { value = "IMPORTED-BASELINE-VALUE-MANAGED-OUTSIDE-TERRAFORM", sensitive = true, managed = false }
    CHAT_SERVICE_URL        = { value = "IMPORTED-BASELINE-VALUE-MANAGED-OUTSIDE-TERRAFORM", sensitive = true, managed = false }
    GITHUB_PACKAGE_TOKEN    = { value = "IMPORTED-BASELINE-VALUE-MANAGED-OUTSIDE-TERRAFORM", sensitive = true, managed = false }
    GOOGLE_CLIENT_ID        = { value = "IMPORTED-BASELINE-VALUE-MANAGED-OUTSIDE-TERRAFORM", sensitive = true, managed = false }
    GOOGLE_CLIENT_SECRET    = { value = "IMPORTED-BASELINE-VALUE-MANAGED-OUTSIDE-TERRAFORM", sensitive = true, managed = false }
    GRAFANA_SA_TOKEN        = { value = "IMPORTED-BASELINE-VALUE-MANAGED-OUTSIDE-TERRAFORM", sensitive = true, managed = false }
    GRAFANA_URL             = { value = "IMPORTED-BASELINE-VALUE-MANAGED-OUTSIDE-TERRAFORM", sensitive = true, managed = false }
    NEXTAUTH_SECRET         = { value = "IMPORTED-BASELINE-VALUE-MANAGED-OUTSIDE-TERRAFORM", sensitive = true, managed = false }
    NEXTAUTH_URL            = { value = "IMPORTED-BASELINE-VALUE-MANAGED-OUTSIDE-TERRAFORM", sensitive = true, managed = false }
  }
}

module "storybook_variables" {
  source = "../../modules/railway-variables"

  service_id             = module.storybook.railway_service_id
  railway_environment_id = var.railway_environment_id
  variables = {
    GITHUB_PACKAGE_TOKEN = { value = "IMPORTED-BASELINE-VALUE-MANAGED-OUTSIDE-TERRAFORM", sensitive = true, managed = false }
  }
}

module "scrape_and_analyze_variables" {
  source = "../../modules/railway-variables"

  service_id             = module.scrape_and_analyze.railway_service_id
  railway_environment_id = var.railway_environment_id
  variables = {
    APP_ENV                 = { value = "IMPORTED-BASELINE-VALUE-MANAGED-OUTSIDE-TERRAFORM", sensitive = true, managed = false }
    CACHE_REDIS_URL         = { value = "IMPORTED-BASELINE-VALUE-MANAGED-OUTSIDE-TERRAFORM", sensitive = true, managed = false }
    CONTACT_EMAIL           = { value = "IMPORTED-BASELINE-VALUE-MANAGED-OUTSIDE-TERRAFORM", sensitive = true, managed = false }
    DATABASE_URL            = { value = "IMPORTED-BASELINE-VALUE-MANAGED-OUTSIDE-TERRAFORM", sensitive = true, managed = false }
    FIXIE_URL               = { value = "IMPORTED-BASELINE-VALUE-MANAGED-OUTSIDE-TERRAFORM", sensitive = true, managed = false }
    GEMINI_API_KEY          = { value = "IMPORTED-BASELINE-VALUE-MANAGED-OUTSIDE-TERRAFORM", sensitive = true, managed = false }
    GITHUB_PACKAGE_TOKEN    = { value = "IMPORTED-BASELINE-VALUE-MANAGED-OUTSIDE-TERRAFORM", sensitive = true, managed = false }
    GRAFANA_API_KEY         = { value = "IMPORTED-BASELINE-VALUE-MANAGED-OUTSIDE-TERRAFORM", sensitive = true, managed = false }
    GRAFANA_LOKI_URL        = { value = "IMPORTED-BASELINE-VALUE-MANAGED-OUTSIDE-TERRAFORM", sensitive = true, managed = false }
    GRAFANA_LOKI_USER       = { value = "IMPORTED-BASELINE-VALUE-MANAGED-OUTSIDE-TERRAFORM", sensitive = true, managed = false }
    GRAFANA_OTLP_ENDPOINT   = { value = "IMPORTED-BASELINE-VALUE-MANAGED-OUTSIDE-TERRAFORM", sensitive = true, managed = false }
    GRAFANA_OTLP_USER       = { value = "IMPORTED-BASELINE-VALUE-MANAGED-OUTSIDE-TERRAFORM", sensitive = true, managed = false }
    OPENROUTER_API_KEY      = { value = "IMPORTED-BASELINE-VALUE-MANAGED-OUTSIDE-TERRAFORM", sensitive = true, managed = false }
    RAG_CHUNK_OVERLAP       = { value = "IMPORTED-BASELINE-VALUE-MANAGED-OUTSIDE-TERRAFORM", sensitive = true, managed = false }
    RAG_CHUNK_SIZE          = { value = "IMPORTED-BASELINE-VALUE-MANAGED-OUTSIDE-TERRAFORM", sensitive = true, managed = false }
    RAG_DENSE_API_KEY_ENV   = { value = "IMPORTED-BASELINE-VALUE-MANAGED-OUTSIDE-TERRAFORM", sensitive = true, managed = false }
    RAG_DENSE_DIMENSION     = { value = "IMPORTED-BASELINE-VALUE-MANAGED-OUTSIDE-TERRAFORM", sensitive = true, managed = false }
    RAG_DENSE_ENDPOINT_URL  = { value = "IMPORTED-BASELINE-VALUE-MANAGED-OUTSIDE-TERRAFORM", sensitive = true, managed = false }
    RAG_DENSE_MODEL         = { value = "IMPORTED-BASELINE-VALUE-MANAGED-OUTSIDE-TERRAFORM", sensitive = true, managed = false }
    RAG_DENSE_PROVIDER      = { value = "IMPORTED-BASELINE-VALUE-MANAGED-OUTSIDE-TERRAFORM", sensitive = true, managed = false }
    RAG_DENSE_RPD           = { value = "IMPORTED-BASELINE-VALUE-MANAGED-OUTSIDE-TERRAFORM", sensitive = true, managed = false }
    RAG_DENSE_RPM           = { value = "IMPORTED-BASELINE-VALUE-MANAGED-OUTSIDE-TERRAFORM", sensitive = true, managed = false }
    RAG_DENSE_TPM           = { value = "IMPORTED-BASELINE-VALUE-MANAGED-OUTSIDE-TERRAFORM", sensitive = true, managed = false }
    RAG_EMBED_BATCH_SIZE    = { value = "IMPORTED-BASELINE-VALUE-MANAGED-OUTSIDE-TERRAFORM", sensitive = true, managed = false }
    RAG_GEMINI_API_KEY      = { value = "IMPORTED-BASELINE-VALUE-MANAGED-OUTSIDE-TERRAFORM", sensitive = true, managed = false }
    RAG_SPARSE_DIMENSION    = { value = "IMPORTED-BASELINE-VALUE-MANAGED-OUTSIDE-TERRAFORM", sensitive = true, managed = false }
    RAG_SPARSE_ENDPOINT_URL = { value = "IMPORTED-BASELINE-VALUE-MANAGED-OUTSIDE-TERRAFORM", sensitive = true, managed = false }
    RAG_SPARSE_MODEL        = { value = "IMPORTED-BASELINE-VALUE-MANAGED-OUTSIDE-TERRAFORM", sensitive = true, managed = false }
    RAG_SPARSE_PROVIDER     = { value = "IMPORTED-BASELINE-VALUE-MANAGED-OUTSIDE-TERRAFORM", sensitive = true, managed = false }
    RAG_SPARSE_RPD          = { value = "IMPORTED-BASELINE-VALUE-MANAGED-OUTSIDE-TERRAFORM", sensitive = true, managed = false }
    RAG_SPARSE_RPM          = { value = "IMPORTED-BASELINE-VALUE-MANAGED-OUTSIDE-TERRAFORM", sensitive = true, managed = false }
    RAG_SPARSE_TPM          = { value = "IMPORTED-BASELINE-VALUE-MANAGED-OUTSIDE-TERRAFORM", sensitive = true, managed = false }
    SENTRY_DSN              = { value = "IMPORTED-BASELINE-VALUE-MANAGED-OUTSIDE-TERRAFORM", sensitive = true, managed = false }
    TELEGRAM_BOT_TOKEN      = { value = "IMPORTED-BASELINE-VALUE-MANAGED-OUTSIDE-TERRAFORM", sensitive = true, managed = false }
    TELEGRAM_CHAT_ID        = { value = "IMPORTED-BASELINE-VALUE-MANAGED-OUTSIDE-TERRAFORM", sensitive = true, managed = false }
    VECTOR_DB_HOST          = { value = "IMPORTED-BASELINE-VALUE-MANAGED-OUTSIDE-TERRAFORM", sensitive = true, managed = false }
    VECTOR_DB_NAME          = { value = "IMPORTED-BASELINE-VALUE-MANAGED-OUTSIDE-TERRAFORM", sensitive = true, managed = false }
    VECTOR_DB_PASSWORD      = { value = "IMPORTED-BASELINE-VALUE-MANAGED-OUTSIDE-TERRAFORM", sensitive = true, managed = false }
    VECTOR_DB_PORT          = { value = "IMPORTED-BASELINE-VALUE-MANAGED-OUTSIDE-TERRAFORM", sensitive = true, managed = false }
    VECTOR_DB_SCHEMA        = { value = "IMPORTED-BASELINE-VALUE-MANAGED-OUTSIDE-TERRAFORM", sensitive = true, managed = false }
    VECTOR_DB_USER          = { value = "IMPORTED-BASELINE-VALUE-MANAGED-OUTSIDE-TERRAFORM", sensitive = true, managed = false }
  }
}

module "chatbot_plugin_variables" {
  source = "../../modules/railway-variables"

  service_id             = module.chatbot_plugin.railway_service_id
  railway_environment_id = var.railway_environment_id
  variables = {
    APP_ENV                 = { value = "IMPORTED-BASELINE-VALUE-MANAGED-OUTSIDE-TERRAFORM", sensitive = true, managed = false }
    CHATBOT_MAX_TOKENS      = { value = "IMPORTED-BASELINE-VALUE-MANAGED-OUTSIDE-TERRAFORM", sensitive = true, managed = false }
    GEMINI_API_KEY          = { value = "IMPORTED-BASELINE-VALUE-MANAGED-OUTSIDE-TERRAFORM", sensitive = true, managed = false }
    GRAFANA_API_KEY         = { value = "IMPORTED-BASELINE-VALUE-MANAGED-OUTSIDE-TERRAFORM", sensitive = true, managed = false }
    GRAFANA_LOKI_URL        = { value = "IMPORTED-BASELINE-VALUE-MANAGED-OUTSIDE-TERRAFORM", sensitive = true, managed = false }
    GRAFANA_LOKI_USER       = { value = "IMPORTED-BASELINE-VALUE-MANAGED-OUTSIDE-TERRAFORM", sensitive = true, managed = false }
    GRAFANA_OTLP_ENDPOINT   = { value = "IMPORTED-BASELINE-VALUE-MANAGED-OUTSIDE-TERRAFORM", sensitive = true, managed = false }
    GRAFANA_OTLP_USER       = { value = "IMPORTED-BASELINE-VALUE-MANAGED-OUTSIDE-TERRAFORM", sensitive = true, managed = false }
    RAG_DENSE_API_KEY_ENV   = { value = "IMPORTED-BASELINE-VALUE-MANAGED-OUTSIDE-TERRAFORM", sensitive = true, managed = false }
    RAG_DENSE_DIMENSION     = { value = "IMPORTED-BASELINE-VALUE-MANAGED-OUTSIDE-TERRAFORM", sensitive = true, managed = false }
    RAG_DENSE_MODEL         = { value = "IMPORTED-BASELINE-VALUE-MANAGED-OUTSIDE-TERRAFORM", sensitive = true, managed = false }
    RAG_DENSE_PROVIDER      = { value = "IMPORTED-BASELINE-VALUE-MANAGED-OUTSIDE-TERRAFORM", sensitive = true, managed = false }
    RAG_DENSE_RPD           = { value = "IMPORTED-BASELINE-VALUE-MANAGED-OUTSIDE-TERRAFORM", sensitive = true, managed = false }
    RAG_DENSE_RPM           = { value = "IMPORTED-BASELINE-VALUE-MANAGED-OUTSIDE-TERRAFORM", sensitive = true, managed = false }
    RAG_DENSE_TPM           = { value = "IMPORTED-BASELINE-VALUE-MANAGED-OUTSIDE-TERRAFORM", sensitive = true, managed = false }
    RAG_GEMINI_API_KEY      = { value = "IMPORTED-BASELINE-VALUE-MANAGED-OUTSIDE-TERRAFORM", sensitive = true, managed = false }
    RAG_SPARSE_DIMENSION    = { value = "IMPORTED-BASELINE-VALUE-MANAGED-OUTSIDE-TERRAFORM", sensitive = true, managed = false }
    RAG_SPARSE_ENDPOINT_URL = { value = "IMPORTED-BASELINE-VALUE-MANAGED-OUTSIDE-TERRAFORM", sensitive = true, managed = false }
    RAG_SPARSE_MODEL        = { value = "IMPORTED-BASELINE-VALUE-MANAGED-OUTSIDE-TERRAFORM", sensitive = true, managed = false }
    RAG_SPARSE_PROVIDER     = { value = "IMPORTED-BASELINE-VALUE-MANAGED-OUTSIDE-TERRAFORM", sensitive = true, managed = false }
    VECTOR_DB_HOST          = { value = "IMPORTED-BASELINE-VALUE-MANAGED-OUTSIDE-TERRAFORM", sensitive = true, managed = false }
    VECTOR_DB_NAME          = { value = "IMPORTED-BASELINE-VALUE-MANAGED-OUTSIDE-TERRAFORM", sensitive = true, managed = false }
    VECTOR_DB_PASSWORD      = { value = "IMPORTED-BASELINE-VALUE-MANAGED-OUTSIDE-TERRAFORM", sensitive = true, managed = false }
    VECTOR_DB_PORT          = { value = "IMPORTED-BASELINE-VALUE-MANAGED-OUTSIDE-TERRAFORM", sensitive = true, managed = false }
    VECTOR_DB_SCHEMA        = { value = "IMPORTED-BASELINE-VALUE-MANAGED-OUTSIDE-TERRAFORM", sensitive = true, managed = false }
    VECTOR_DB_USER          = { value = "IMPORTED-BASELINE-VALUE-MANAGED-OUTSIDE-TERRAFORM", sensitive = true, managed = false }
  }
}

module "fastembed_variables" {
  source = "../../modules/railway-variables"

  service_id             = module.fastembed.railway_service_id
  railway_environment_id = var.railway_environment_id
  variables = {
    APP_ENV               = { value = "IMPORTED-BASELINE-VALUE-MANAGED-OUTSIDE-TERRAFORM", sensitive = true, managed = false }
    GRAFANA_API_KEY       = { value = "IMPORTED-BASELINE-VALUE-MANAGED-OUTSIDE-TERRAFORM", sensitive = true, managed = false }
    GRAFANA_LOKI_URL      = { value = "IMPORTED-BASELINE-VALUE-MANAGED-OUTSIDE-TERRAFORM", sensitive = true, managed = false }
    GRAFANA_LOKI_USER     = { value = "IMPORTED-BASELINE-VALUE-MANAGED-OUTSIDE-TERRAFORM", sensitive = true, managed = false }
    GRAFANA_OTLP_ENDPOINT = { value = "IMPORTED-BASELINE-VALUE-MANAGED-OUTSIDE-TERRAFORM", sensitive = true, managed = false }
    GRAFANA_OTLP_USER     = { value = "IMPORTED-BASELINE-VALUE-MANAGED-OUTSIDE-TERRAFORM", sensitive = true, managed = false }
  }
}

module "weekly_report_variables" {
  source = "../../modules/railway-variables"

  service_id             = module.weekly_report.railway_service_id
  railway_environment_id = var.railway_environment_id
  variables = {
    APP_ENV               = { value = "IMPORTED-BASELINE-VALUE-MANAGED-OUTSIDE-TERRAFORM", sensitive = true, managed = false }
    CACHE_REDIS_URL       = { value = "IMPORTED-BASELINE-VALUE-MANAGED-OUTSIDE-TERRAFORM", sensitive = true, managed = false }
    CONTACT_EMAIL         = { value = "IMPORTED-BASELINE-VALUE-MANAGED-OUTSIDE-TERRAFORM", sensitive = true, managed = false }
    DATABASE_URL          = { value = "IMPORTED-BASELINE-VALUE-MANAGED-OUTSIDE-TERRAFORM", sensitive = true, managed = false }
    FIXIE_URL             = { value = "IMPORTED-BASELINE-VALUE-MANAGED-OUTSIDE-TERRAFORM", sensitive = true, managed = false }
    FRONTEND_ORIGIN       = { value = "IMPORTED-BASELINE-VALUE-MANAGED-OUTSIDE-TERRAFORM", sensitive = true, managed = false }
    GEMINI_API_KEY        = { value = "IMPORTED-BASELINE-VALUE-MANAGED-OUTSIDE-TERRAFORM", sensitive = true, managed = false }
    GRAFANA_API_KEY       = { value = "IMPORTED-BASELINE-VALUE-MANAGED-OUTSIDE-TERRAFORM", sensitive = true, managed = false }
    GRAFANA_LOKI_URL      = { value = "IMPORTED-BASELINE-VALUE-MANAGED-OUTSIDE-TERRAFORM", sensitive = true, managed = false }
    GRAFANA_LOKI_USER     = { value = "IMPORTED-BASELINE-VALUE-MANAGED-OUTSIDE-TERRAFORM", sensitive = true, managed = false }
    GRAFANA_OTLP_ENDPOINT = { value = "IMPORTED-BASELINE-VALUE-MANAGED-OUTSIDE-TERRAFORM", sensitive = true, managed = false }
    GRAFANA_OTLP_USER     = { value = "IMPORTED-BASELINE-VALUE-MANAGED-OUTSIDE-TERRAFORM", sensitive = true, managed = false }
    HF_TOKEN              = { value = "IMPORTED-BASELINE-VALUE-MANAGED-OUTSIDE-TERRAFORM", sensitive = true, managed = false }
    OPENROUTER_API_KEY    = { value = "IMPORTED-BASELINE-VALUE-MANAGED-OUTSIDE-TERRAFORM", sensitive = true, managed = false }
    R2_ACCESS_KEY_ID      = { value = "IMPORTED-BASELINE-VALUE-MANAGED-OUTSIDE-TERRAFORM", sensitive = true, managed = false }
    R2_ACCOUNT_ID         = { value = "IMPORTED-BASELINE-VALUE-MANAGED-OUTSIDE-TERRAFORM", sensitive = true, managed = false }
    R2_BUCKET_NAME        = { value = "IMPORTED-BASELINE-VALUE-MANAGED-OUTSIDE-TERRAFORM", sensitive = true, managed = false }
    R2_PUBLIC_URL         = { value = "IMPORTED-BASELINE-VALUE-MANAGED-OUTSIDE-TERRAFORM", sensitive = true, managed = false }
    R2_SECRET_ACCESS_KEY  = { value = "IMPORTED-BASELINE-VALUE-MANAGED-OUTSIDE-TERRAFORM", sensitive = true, managed = false }
    RESEND_API_KEY        = { value = "IMPORTED-BASELINE-VALUE-MANAGED-OUTSIDE-TERRAFORM", sensitive = true, managed = false }
    RESEND_FROM_EMAIL     = { value = "IMPORTED-BASELINE-VALUE-MANAGED-OUTSIDE-TERRAFORM", sensitive = true, managed = false }
    SENTRY_DSN            = { value = "IMPORTED-BASELINE-VALUE-MANAGED-OUTSIDE-TERRAFORM", sensitive = true, managed = false }
    TELEGRAM_BOT_TOKEN    = { value = "IMPORTED-BASELINE-VALUE-MANAGED-OUTSIDE-TERRAFORM", sensitive = true, managed = false }
    TELEGRAM_CHAT_ID      = { value = "IMPORTED-BASELINE-VALUE-MANAGED-OUTSIDE-TERRAFORM", sensitive = true, managed = false }
    UV_GROUP              = { value = "IMPORTED-BASELINE-VALUE-MANAGED-OUTSIDE-TERRAFORM", sensitive = true, managed = false }
  }
}

module "refresh_metrics_variables" {
  source = "../../modules/railway-variables"

  service_id             = module.refresh_metrics.railway_service_id
  railway_environment_id = var.railway_environment_id
  variables = {
    APP_ENV               = { value = "IMPORTED-BASELINE-VALUE-MANAGED-OUTSIDE-TERRAFORM", sensitive = true, managed = false }
    CONTACT_EMAIL         = { value = "IMPORTED-BASELINE-VALUE-MANAGED-OUTSIDE-TERRAFORM", sensitive = true, managed = false }
    DATABASE_URL          = { value = "IMPORTED-BASELINE-VALUE-MANAGED-OUTSIDE-TERRAFORM", sensitive = true, managed = false }
    FIXIE_URL             = { value = "IMPORTED-BASELINE-VALUE-MANAGED-OUTSIDE-TERRAFORM", sensitive = true, managed = false }
    GRAFANA_API_KEY       = { value = "IMPORTED-BASELINE-VALUE-MANAGED-OUTSIDE-TERRAFORM", sensitive = true, managed = false }
    GRAFANA_LOKI_URL      = { value = "IMPORTED-BASELINE-VALUE-MANAGED-OUTSIDE-TERRAFORM", sensitive = true, managed = false }
    GRAFANA_LOKI_USER     = { value = "IMPORTED-BASELINE-VALUE-MANAGED-OUTSIDE-TERRAFORM", sensitive = true, managed = false }
    GRAFANA_OTLP_ENDPOINT = { value = "IMPORTED-BASELINE-VALUE-MANAGED-OUTSIDE-TERRAFORM", sensitive = true, managed = false }
    GRAFANA_OTLP_USER     = { value = "IMPORTED-BASELINE-VALUE-MANAGED-OUTSIDE-TERRAFORM", sensitive = true, managed = false }
    SENTRY_DSN            = { value = "IMPORTED-BASELINE-VALUE-MANAGED-OUTSIDE-TERRAFORM", sensitive = true, managed = false }
    TELEGRAM_BOT_TOKEN    = { value = "IMPORTED-BASELINE-VALUE-MANAGED-OUTSIDE-TERRAFORM", sensitive = true, managed = false }
    TELEGRAM_CHAT_ID      = { value = "IMPORTED-BASELINE-VALUE-MANAGED-OUTSIDE-TERRAFORM", sensitive = true, managed = false }
    UV_GROUP              = { value = "IMPORTED-BASELINE-VALUE-MANAGED-OUTSIDE-TERRAFORM", sensitive = true, managed = false }
  }
}

module "rag_backfill_variables" {
  source = "../../modules/railway-variables"

  service_id             = module.rag_backfill.railway_service_id
  railway_environment_id = var.railway_environment_id
  variables = {
    APP_ENV                 = { value = "IMPORTED-BASELINE-VALUE-MANAGED-OUTSIDE-TERRAFORM", sensitive = true, managed = false }
    CONTACT_EMAIL           = { value = "IMPORTED-BASELINE-VALUE-MANAGED-OUTSIDE-TERRAFORM", sensitive = true, managed = false }
    DATABASE_URL            = { value = "IMPORTED-BASELINE-VALUE-MANAGED-OUTSIDE-TERRAFORM", sensitive = true, managed = false }
    FIXIE_URL               = { value = "IMPORTED-BASELINE-VALUE-MANAGED-OUTSIDE-TERRAFORM", sensitive = true, managed = false }
    GITHUB_PACKAGE_TOKEN    = { value = "IMPORTED-BASELINE-VALUE-MANAGED-OUTSIDE-TERRAFORM", sensitive = true, managed = false }
    GRAFANA_API_KEY         = { value = "IMPORTED-BASELINE-VALUE-MANAGED-OUTSIDE-TERRAFORM", sensitive = true, managed = false }
    GRAFANA_LOKI_URL        = { value = "IMPORTED-BASELINE-VALUE-MANAGED-OUTSIDE-TERRAFORM", sensitive = true, managed = false }
    GRAFANA_LOKI_USER       = { value = "IMPORTED-BASELINE-VALUE-MANAGED-OUTSIDE-TERRAFORM", sensitive = true, managed = false }
    GRAFANA_OTLP_ENDPOINT   = { value = "IMPORTED-BASELINE-VALUE-MANAGED-OUTSIDE-TERRAFORM", sensitive = true, managed = false }
    GRAFANA_OTLP_USER       = { value = "IMPORTED-BASELINE-VALUE-MANAGED-OUTSIDE-TERRAFORM", sensitive = true, managed = false }
    RAG_CHUNK_OVERLAP       = { value = "IMPORTED-BASELINE-VALUE-MANAGED-OUTSIDE-TERRAFORM", sensitive = true, managed = false }
    RAG_CHUNK_SIZE          = { value = "IMPORTED-BASELINE-VALUE-MANAGED-OUTSIDE-TERRAFORM", sensitive = true, managed = false }
    RAG_DENSE_API_KEY_ENV   = { value = "IMPORTED-BASELINE-VALUE-MANAGED-OUTSIDE-TERRAFORM", sensitive = true, managed = false }
    RAG_DENSE_DIMENSION     = { value = "IMPORTED-BASELINE-VALUE-MANAGED-OUTSIDE-TERRAFORM", sensitive = true, managed = false }
    RAG_DENSE_ENDPOINT_URL  = { value = "IMPORTED-BASELINE-VALUE-MANAGED-OUTSIDE-TERRAFORM", sensitive = true, managed = false }
    RAG_DENSE_MODEL         = { value = "IMPORTED-BASELINE-VALUE-MANAGED-OUTSIDE-TERRAFORM", sensitive = true, managed = false }
    RAG_DENSE_PROVIDER      = { value = "IMPORTED-BASELINE-VALUE-MANAGED-OUTSIDE-TERRAFORM", sensitive = true, managed = false }
    RAG_DENSE_RPD           = { value = "IMPORTED-BASELINE-VALUE-MANAGED-OUTSIDE-TERRAFORM", sensitive = true, managed = false }
    RAG_DENSE_RPM           = { value = "IMPORTED-BASELINE-VALUE-MANAGED-OUTSIDE-TERRAFORM", sensitive = true, managed = false }
    RAG_DENSE_TPM           = { value = "IMPORTED-BASELINE-VALUE-MANAGED-OUTSIDE-TERRAFORM", sensitive = true, managed = false }
    RAG_EMBED_BATCH_SIZE    = { value = "IMPORTED-BASELINE-VALUE-MANAGED-OUTSIDE-TERRAFORM", sensitive = true, managed = false }
    RAG_GEMINI_API_KEY      = { value = "IMPORTED-BASELINE-VALUE-MANAGED-OUTSIDE-TERRAFORM", sensitive = true, managed = false }
    RAG_SPARSE_DIMENSION    = { value = "IMPORTED-BASELINE-VALUE-MANAGED-OUTSIDE-TERRAFORM", sensitive = true, managed = false }
    RAG_SPARSE_ENDPOINT_URL = { value = "IMPORTED-BASELINE-VALUE-MANAGED-OUTSIDE-TERRAFORM", sensitive = true, managed = false }
    RAG_SPARSE_MODEL        = { value = "IMPORTED-BASELINE-VALUE-MANAGED-OUTSIDE-TERRAFORM", sensitive = true, managed = false }
    RAG_SPARSE_PROVIDER     = { value = "IMPORTED-BASELINE-VALUE-MANAGED-OUTSIDE-TERRAFORM", sensitive = true, managed = false }
    RAG_SPARSE_RPD          = { value = "IMPORTED-BASELINE-VALUE-MANAGED-OUTSIDE-TERRAFORM", sensitive = true, managed = false }
    RAG_SPARSE_RPM          = { value = "IMPORTED-BASELINE-VALUE-MANAGED-OUTSIDE-TERRAFORM", sensitive = true, managed = false }
    RAG_SPARSE_TPM          = { value = "IMPORTED-BASELINE-VALUE-MANAGED-OUTSIDE-TERRAFORM", sensitive = true, managed = false }
    SENTRY_DSN              = { value = "IMPORTED-BASELINE-VALUE-MANAGED-OUTSIDE-TERRAFORM", sensitive = true, managed = false }
    TELEGRAM_BOT_TOKEN      = { value = "IMPORTED-BASELINE-VALUE-MANAGED-OUTSIDE-TERRAFORM", sensitive = true, managed = false }
    TELEGRAM_CHAT_ID        = { value = "IMPORTED-BASELINE-VALUE-MANAGED-OUTSIDE-TERRAFORM", sensitive = true, managed = false }
    UV_GROUP                = { value = "IMPORTED-BASELINE-VALUE-MANAGED-OUTSIDE-TERRAFORM", sensitive = true, managed = false }
    VECTOR_DB_HOST          = { value = "IMPORTED-BASELINE-VALUE-MANAGED-OUTSIDE-TERRAFORM", sensitive = true, managed = false }
    VECTOR_DB_NAME          = { value = "IMPORTED-BASELINE-VALUE-MANAGED-OUTSIDE-TERRAFORM", sensitive = true, managed = false }
    VECTOR_DB_PASSWORD      = { value = "IMPORTED-BASELINE-VALUE-MANAGED-OUTSIDE-TERRAFORM", sensitive = true, managed = false }
    VECTOR_DB_PORT          = { value = "IMPORTED-BASELINE-VALUE-MANAGED-OUTSIDE-TERRAFORM", sensitive = true, managed = false }
    VECTOR_DB_SCHEMA        = { value = "IMPORTED-BASELINE-VALUE-MANAGED-OUTSIDE-TERRAFORM", sensitive = true, managed = false }
    VECTOR_DB_USER          = { value = "IMPORTED-BASELINE-VALUE-MANAGED-OUTSIDE-TERRAFORM", sensitive = true, managed = false }
  }
}

module "dedup_reconcile_variables" {
  source = "../../modules/railway-variables"

  service_id             = module.dedup_reconcile.railway_service_id
  railway_environment_id = var.railway_environment_id
  variables = {
    APP_ENV               = { value = "IMPORTED-BASELINE-VALUE-MANAGED-OUTSIDE-TERRAFORM", sensitive = true, managed = false }
    CONTACT_EMAIL         = { value = "IMPORTED-BASELINE-VALUE-MANAGED-OUTSIDE-TERRAFORM", sensitive = true, managed = false }
    DATABASE_URL          = { value = "IMPORTED-BASELINE-VALUE-MANAGED-OUTSIDE-TERRAFORM", sensitive = true, managed = false }
    FIXIE_URL             = { value = "IMPORTED-BASELINE-VALUE-MANAGED-OUTSIDE-TERRAFORM", sensitive = true, managed = false }
    GRAFANA_API_KEY       = { value = "IMPORTED-BASELINE-VALUE-MANAGED-OUTSIDE-TERRAFORM", sensitive = true, managed = false }
    GRAFANA_LOKI_URL      = { value = "IMPORTED-BASELINE-VALUE-MANAGED-OUTSIDE-TERRAFORM", sensitive = true, managed = false }
    GRAFANA_LOKI_USER     = { value = "IMPORTED-BASELINE-VALUE-MANAGED-OUTSIDE-TERRAFORM", sensitive = true, managed = false }
    GRAFANA_OTLP_ENDPOINT = { value = "IMPORTED-BASELINE-VALUE-MANAGED-OUTSIDE-TERRAFORM", sensitive = true, managed = false }
    GRAFANA_OTLP_USER     = { value = "IMPORTED-BASELINE-VALUE-MANAGED-OUTSIDE-TERRAFORM", sensitive = true, managed = false }
    SENTRY_DSN            = { value = "IMPORTED-BASELINE-VALUE-MANAGED-OUTSIDE-TERRAFORM", sensitive = true, managed = false }
    TELEGRAM_BOT_TOKEN    = { value = "IMPORTED-BASELINE-VALUE-MANAGED-OUTSIDE-TERRAFORM", sensitive = true, managed = false }
    TELEGRAM_CHAT_ID      = { value = "IMPORTED-BASELINE-VALUE-MANAGED-OUTSIDE-TERRAFORM", sensitive = true, managed = false }
    UV_GROUP              = { value = "IMPORTED-BASELINE-VALUE-MANAGED-OUTSIDE-TERRAFORM", sensitive = true, managed = false }
  }
}

# --- GitHub Actions secrets/variables (US2 T023-028, FR-012) ---
# Repo-level ones are declared only here (not in staging too) — same
# single-declaration principle as railway_service (research.md §9): a repo
# secret/variable is singular, not per-environment, so declaring it in two
# workspaces' state would create the same double-management conflict.
module "github_ci_repo" {
  source = "../../modules/github-ci-config"

  repository = var.github_repository

  secrets = {
    CLAUDE_API_KEY     = { value = "IMPORTED-BASELINE-VALUE-MANAGED-OUTSIDE-TERRAFORM", managed = false }
    CODECOV_TOKEN      = { value = "IMPORTED-BASELINE-VALUE-MANAGED-OUTSIDE-TERRAFORM", managed = false }
    GEMINI_API_KEY     = { value = "IMPORTED-BASELINE-VALUE-MANAGED-OUTSIDE-TERRAFORM", managed = false }
    GIST_ID            = { value = "IMPORTED-BASELINE-VALUE-MANAGED-OUTSIDE-TERRAFORM", managed = false }
    GIST_SECRET        = { value = "IMPORTED-BASELINE-VALUE-MANAGED-OUTSIDE-TERRAFORM", managed = false }
    NEXTAUTH_SECRET    = { value = "IMPORTED-BASELINE-VALUE-MANAGED-OUTSIDE-TERRAFORM", managed = false }
    NPM_TOKEN          = { value = "IMPORTED-BASELINE-VALUE-MANAGED-OUTSIDE-TERRAFORM", managed = false }
    OPENROUTER_API_KEY = { value = "IMPORTED-BASELINE-VALUE-MANAGED-OUTSIDE-TERRAFORM", managed = false }
    RELEASE_PAT        = { value = "IMPORTED-BASELINE-VALUE-MANAGED-OUTSIDE-TERRAFORM", managed = false }
  }

  # Non-secret and already known exactly — declared as genuinely managed, not baseline.
  variables = {
    BACKEND_URL   = { value = "https://dashboard-backend2-production-e4c1.up.railway.app/", managed = true }
    FRONTEND_URL  = { value = "https://dashboard-frontend-staging-f1e3.up.railway.app", managed = true }
    STORYBOOK_URL = { value = "https://satisfied-luck-production.up.railway.app/", managed = true }

    RAILWAY_SERVICE_ID_DASHBOARD_BACKEND  = { value = module.dashboard_backend.railway_service_id, managed = true }
    RAILWAY_SERVICE_ID_DASHBOARD_FRONTEND = { value = module.dashboard_frontend.railway_service_id, managed = true }
    RAILWAY_SERVICE_ID_STORYBOOK          = { value = module.storybook.railway_service_id, managed = true }
    RAILWAY_SERVICE_ID_SCRAPE_AND_ANALYZE = { value = module.scrape_and_analyze.railway_service_id, managed = true }
    RAILWAY_SERVICE_ID_CHATBOT_PLUGIN     = { value = module.chatbot_plugin.railway_service_id, managed = true }
    RAILWAY_SERVICE_ID_FASTEMBED          = { value = module.fastembed.railway_service_id, managed = true }
    RAILWAY_SERVICE_ID_WEEKLY_REPORT      = { value = module.weekly_report.railway_service_id, managed = true }
    RAILWAY_SERVICE_ID_REFRESH_METRICS    = { value = module.refresh_metrics.railway_service_id, managed = true }
    RAILWAY_SERVICE_ID_RAG_BACKFILL       = { value = module.rag_backfill.railway_service_id, managed = true }
    RAILWAY_SERVICE_ID_DEDUP_RECONCILE    = { value = module.dedup_reconcile.railway_service_id, managed = true }
  }
}

module "github_ci_production" {
  source = "../../modules/github-ci-config"

  repository              = var.github_repository
  github_environment_name = var.github_environment_name

  secrets = {
    DATABASE_URL  = { value = "IMPORTED-BASELINE-VALUE-MANAGED-OUTSIDE-TERRAFORM", managed = false }
    RAILWAY_TOKEN = { value = "IMPORTED-BASELINE-VALUE-MANAGED-OUTSIDE-TERRAFORM", managed = false }
  }
}
