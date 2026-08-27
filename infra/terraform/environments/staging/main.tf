# Environment: staging (Railway environment ID: see terraform.tfvars).
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

# railway_service only ever exists in environments/production (research.md
# §9) — staging reads the real service IDs from production's state instead
# of re-declaring/importing railway_service here. Actual per-environment
# railway_variable instances (using these IDs) are added in US2.
data "terraform_remote_state" "production" {
  backend = "remote"

  config = {
    organization = "scrape-analyzer"
    workspaces = {
      name = "scrape-analyzer-production"
    }
  }
}

# --- Shared variable groups (specs/025-iac-provisioning shared-variable
# migration, pilot: observability) — see production/main.tf's comment. ---
module "shared_vars" {
  source = "../../modules/shared-variables"

  grafana_api_key       = var.grafana_api_key
  grafana_loki_url      = var.grafana_loki_url
  grafana_loki_user     = var.grafana_loki_user
  grafana_otlp_endpoint = var.grafana_otlp_endpoint
  grafana_otlp_user     = var.grafana_otlp_user
  sentry_dsn            = var.sentry_dsn
}

module "dashboard_backend_variables" {
  source = "../../modules/railway-variables"

  service_id             = data.terraform_remote_state.production.outputs.service_ids["dashboard-backend"]
  railway_environment_id = var.railway_environment_id
  variables = merge(module.shared_vars.grafana, module.shared_vars.sentry, {
    APP_ENV                    = { value = "IMPORTED-BASELINE-VALUE-MANAGED-OUTSIDE-TERRAFORM", sensitive = true, managed = false }
    CACHE_REDIS_URL            = { value = "IMPORTED-BASELINE-VALUE-MANAGED-OUTSIDE-TERRAFORM", sensitive = true, managed = false }
    CHAT_SERVICE_API_KEY       = { value = "IMPORTED-BASELINE-VALUE-MANAGED-OUTSIDE-TERRAFORM", sensitive = true, managed = false }
    CHAT_SERVICE_URL           = { value = "IMPORTED-BASELINE-VALUE-MANAGED-OUTSIDE-TERRAFORM", sensitive = true, managed = false }
    DATABASE_URL               = { value = "IMPORTED-BASELINE-VALUE-MANAGED-OUTSIDE-TERRAFORM", sensitive = true, managed = false }
    FRONTEND_ORIGIN            = { value = "IMPORTED-BASELINE-VALUE-MANAGED-OUTSIDE-TERRAFORM", sensitive = true, managed = false }
    GEMINI_API_KEY             = { value = "IMPORTED-BASELINE-VALUE-MANAGED-OUTSIDE-TERRAFORM", sensitive = true, managed = false }
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
    SWAGGER_TRY_IT_OUT_ENABLED = { value = "IMPORTED-BASELINE-VALUE-MANAGED-OUTSIDE-TERRAFORM", sensitive = true, managed = false }
  })
}

module "dashboard_frontend_variables" {
  source = "../../modules/railway-variables"

  service_id             = data.terraform_remote_state.production.outputs.service_ids["dashboard-frontend"]
  railway_environment_id = var.railway_environment_id
  variables = {
    APP_ENV              = { value = "IMPORTED-BASELINE-VALUE-MANAGED-OUTSIDE-TERRAFORM", sensitive = true, managed = false }
    BACKEND_URL          = { value = "http://dashboard-backend.railway.internal:8000", managed = true }
    CHAT_SERVICE_API_KEY = { value = "IMPORTED-BASELINE-VALUE-MANAGED-OUTSIDE-TERRAFORM", sensitive = true, managed = false }
    CHAT_SERVICE_URL     = { value = "IMPORTED-BASELINE-VALUE-MANAGED-OUTSIDE-TERRAFORM", sensitive = true, managed = false }
    GITHUB_PACKAGE_TOKEN = { value = "IMPORTED-BASELINE-VALUE-MANAGED-OUTSIDE-TERRAFORM", sensitive = true, managed = false }
    GOOGLE_CLIENT_ID     = { value = "IMPORTED-BASELINE-VALUE-MANAGED-OUTSIDE-TERRAFORM", sensitive = true, managed = false }
    GOOGLE_CLIENT_SECRET = { value = "IMPORTED-BASELINE-VALUE-MANAGED-OUTSIDE-TERRAFORM", sensitive = true, managed = false }
    GRAFANA_SA_TOKEN     = { value = "IMPORTED-BASELINE-VALUE-MANAGED-OUTSIDE-TERRAFORM", sensitive = true, managed = false }
    GRAFANA_URL          = { value = "IMPORTED-BASELINE-VALUE-MANAGED-OUTSIDE-TERRAFORM", sensitive = true, managed = false }
    NEXTAUTH_SECRET      = { value = "IMPORTED-BASELINE-VALUE-MANAGED-OUTSIDE-TERRAFORM", sensitive = true, managed = false }
    NEXTAUTH_URL         = { value = "IMPORTED-BASELINE-VALUE-MANAGED-OUTSIDE-TERRAFORM", sensitive = true, managed = false }
  }
}

module "storybook_variables" {
  source = "../../modules/railway-variables"

  service_id             = data.terraform_remote_state.production.outputs.service_ids["storybook"]
  railway_environment_id = var.railway_environment_id
  variables = {
    GITHUB_PACKAGE_TOKEN = { value = "IMPORTED-BASELINE-VALUE-MANAGED-OUTSIDE-TERRAFORM", sensitive = true, managed = false }
  }
}

module "scrape_and_analyze_variables" {
  source = "../../modules/railway-variables"

  service_id             = data.terraform_remote_state.production.outputs.service_ids["scrape-and-analyze"]
  railway_environment_id = var.railway_environment_id
  variables = merge(module.shared_vars.grafana, module.shared_vars.sentry, {
    APP_ENV                           = { value = "IMPORTED-BASELINE-VALUE-MANAGED-OUTSIDE-TERRAFORM", sensitive = true, managed = false }
    CACHE_REDIS_URL                   = { value = "IMPORTED-BASELINE-VALUE-MANAGED-OUTSIDE-TERRAFORM", sensitive = true, managed = false }
    CONTACT_EMAIL                     = { value = "IMPORTED-BASELINE-VALUE-MANAGED-OUTSIDE-TERRAFORM", sensitive = true, managed = false }
    DATABASE_URL                      = { value = "IMPORTED-BASELINE-VALUE-MANAGED-OUTSIDE-TERRAFORM", sensitive = true, managed = false }
    FIXIE_URL                         = { value = "IMPORTED-BASELINE-VALUE-MANAGED-OUTSIDE-TERRAFORM", sensitive = true, managed = false }
    GEMINI_API_KEY                    = { value = "IMPORTED-BASELINE-VALUE-MANAGED-OUTSIDE-TERRAFORM", sensitive = true, managed = false }
    GITHUB_PACKAGE_TOKEN              = { value = "IMPORTED-BASELINE-VALUE-MANAGED-OUTSIDE-TERRAFORM", sensitive = true, managed = false }
    OPENROUTER_API_KEY                = { value = "IMPORTED-BASELINE-VALUE-MANAGED-OUTSIDE-TERRAFORM", sensitive = true, managed = false }
    RAG_CHUNK_OVERLAP                 = { value = "IMPORTED-BASELINE-VALUE-MANAGED-OUTSIDE-TERRAFORM", sensitive = true, managed = false }
    RAG_CHUNK_SIZE                    = { value = "IMPORTED-BASELINE-VALUE-MANAGED-OUTSIDE-TERRAFORM", sensitive = true, managed = false }
    RAG_DENSE_API_KEY_ENV             = { value = "IMPORTED-BASELINE-VALUE-MANAGED-OUTSIDE-TERRAFORM", sensitive = true, managed = false }
    RAG_DENSE_DIMENSION               = { value = "IMPORTED-BASELINE-VALUE-MANAGED-OUTSIDE-TERRAFORM", sensitive = true, managed = false }
    RAG_DENSE_ENDPOINT_URL            = { value = "IMPORTED-BASELINE-VALUE-MANAGED-OUTSIDE-TERRAFORM", sensitive = true, managed = false }
    RAG_DENSE_MODEL                   = { value = "IMPORTED-BASELINE-VALUE-MANAGED-OUTSIDE-TERRAFORM", sensitive = true, managed = false }
    RAG_DENSE_PROVIDER                = { value = "IMPORTED-BASELINE-VALUE-MANAGED-OUTSIDE-TERRAFORM", sensitive = true, managed = false }
    RAG_DENSE_RPD                     = { value = "IMPORTED-BASELINE-VALUE-MANAGED-OUTSIDE-TERRAFORM", sensitive = true, managed = false }
    RAG_DENSE_RPM                     = { value = "IMPORTED-BASELINE-VALUE-MANAGED-OUTSIDE-TERRAFORM", sensitive = true, managed = false }
    RAG_DENSE_TPM                     = { value = "IMPORTED-BASELINE-VALUE-MANAGED-OUTSIDE-TERRAFORM", sensitive = true, managed = false }
    RAG_EMBED_BATCH_SIZE              = { value = "IMPORTED-BASELINE-VALUE-MANAGED-OUTSIDE-TERRAFORM", sensitive = true, managed = false }
    RAG_GEMINI_API_KEY                = { value = "IMPORTED-BASELINE-VALUE-MANAGED-OUTSIDE-TERRAFORM", sensitive = true, managed = false }
    RAG_SPARSE_DIMENSION              = { value = "IMPORTED-BASELINE-VALUE-MANAGED-OUTSIDE-TERRAFORM", sensitive = true, managed = false }
    RAG_SPARSE_ENDPOINT_URL           = { value = "IMPORTED-BASELINE-VALUE-MANAGED-OUTSIDE-TERRAFORM", sensitive = true, managed = false }
    RAG_SPARSE_MODEL                  = { value = "IMPORTED-BASELINE-VALUE-MANAGED-OUTSIDE-TERRAFORM", sensitive = true, managed = false }
    RAG_SPARSE_PROVIDER               = { value = "IMPORTED-BASELINE-VALUE-MANAGED-OUTSIDE-TERRAFORM", sensitive = true, managed = false }
    RAG_SPARSE_RPD                    = { value = "IMPORTED-BASELINE-VALUE-MANAGED-OUTSIDE-TERRAFORM", sensitive = true, managed = false }
    RAG_SPARSE_RPM                    = { value = "IMPORTED-BASELINE-VALUE-MANAGED-OUTSIDE-TERRAFORM", sensitive = true, managed = false }
    RAG_SPARSE_TPM                    = { value = "IMPORTED-BASELINE-VALUE-MANAGED-OUTSIDE-TERRAFORM", sensitive = true, managed = false }
    SEARCH_AUTOCOMPLETE_MAX_QUERY_LEN = { value = "IMPORTED-BASELINE-VALUE-MANAGED-OUTSIDE-TERRAFORM", sensitive = true, managed = false }
    SEARCH_INDEX_REDIS_URL            = { value = "IMPORTED-BASELINE-VALUE-MANAGED-OUTSIDE-TERRAFORM", sensitive = true, managed = false }
    SEARCH_MIN_DOC_FREQ               = { value = "IMPORTED-BASELINE-VALUE-MANAGED-OUTSIDE-TERRAFORM", sensitive = true, managed = false }
    TELEGRAM_BOT_TOKEN                = { value = "IMPORTED-BASELINE-VALUE-MANAGED-OUTSIDE-TERRAFORM", sensitive = true, managed = false }
    TELEGRAM_CHAT_ID                  = { value = "IMPORTED-BASELINE-VALUE-MANAGED-OUTSIDE-TERRAFORM", sensitive = true, managed = false }
    VECTOR_DB_HOST                    = { value = "IMPORTED-BASELINE-VALUE-MANAGED-OUTSIDE-TERRAFORM", sensitive = true, managed = false }
    VECTOR_DB_NAME                    = { value = "IMPORTED-BASELINE-VALUE-MANAGED-OUTSIDE-TERRAFORM", sensitive = true, managed = false }
    VECTOR_DB_PASSWORD                = { value = "IMPORTED-BASELINE-VALUE-MANAGED-OUTSIDE-TERRAFORM", sensitive = true, managed = false }
    VECTOR_DB_PORT                    = { value = "IMPORTED-BASELINE-VALUE-MANAGED-OUTSIDE-TERRAFORM", sensitive = true, managed = false }
    VECTOR_DB_SCHEMA                  = { value = "IMPORTED-BASELINE-VALUE-MANAGED-OUTSIDE-TERRAFORM", sensitive = true, managed = false }
    VECTOR_DB_USER                    = { value = "IMPORTED-BASELINE-VALUE-MANAGED-OUTSIDE-TERRAFORM", sensitive = true, managed = false }
  })
}

module "chatbot_plugin_variables" {
  source = "../../modules/railway-variables"

  service_id             = data.terraform_remote_state.production.outputs.service_ids["chatbot-plugin"]
  railway_environment_id = var.railway_environment_id
  variables = merge(module.shared_vars.grafana, {
    APP_ENV                 = { value = "IMPORTED-BASELINE-VALUE-MANAGED-OUTSIDE-TERRAFORM", sensitive = true, managed = false }
    CHATBOT_MAX_TOKENS      = { value = "IMPORTED-BASELINE-VALUE-MANAGED-OUTSIDE-TERRAFORM", sensitive = true, managed = false }
    GEMINI_API_KEY          = { value = "IMPORTED-BASELINE-VALUE-MANAGED-OUTSIDE-TERRAFORM", sensitive = true, managed = false }
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
  })
}

module "fastembed_variables" {
  source = "../../modules/railway-variables"

  service_id             = data.terraform_remote_state.production.outputs.service_ids["fastembed"]
  railway_environment_id = var.railway_environment_id
  variables = merge(module.shared_vars.grafana, {
    APP_ENV = { value = "IMPORTED-BASELINE-VALUE-MANAGED-OUTSIDE-TERRAFORM", sensitive = true, managed = false }
  })
}

module "weekly_report_variables" {
  source = "../../modules/railway-variables"

  service_id             = data.terraform_remote_state.production.outputs.service_ids["weekly-report"]
  railway_environment_id = var.railway_environment_id
  variables = merge(module.shared_vars.grafana, module.shared_vars.sentry, {
    APP_ENV              = { value = "IMPORTED-BASELINE-VALUE-MANAGED-OUTSIDE-TERRAFORM", sensitive = true, managed = false }
    CACHE_REDIS_URL      = { value = "IMPORTED-BASELINE-VALUE-MANAGED-OUTSIDE-TERRAFORM", sensitive = true, managed = false }
    CONTACT_EMAIL        = { value = "IMPORTED-BASELINE-VALUE-MANAGED-OUTSIDE-TERRAFORM", sensitive = true, managed = false }
    DATABASE_URL         = { value = "IMPORTED-BASELINE-VALUE-MANAGED-OUTSIDE-TERRAFORM", sensitive = true, managed = false }
    FIXIE_URL            = { value = "IMPORTED-BASELINE-VALUE-MANAGED-OUTSIDE-TERRAFORM", sensitive = true, managed = false }
    FRONTEND_ORIGIN      = { value = "IMPORTED-BASELINE-VALUE-MANAGED-OUTSIDE-TERRAFORM", sensitive = true, managed = false }
    GEMINI_API_KEY       = { value = "IMPORTED-BASELINE-VALUE-MANAGED-OUTSIDE-TERRAFORM", sensitive = true, managed = false }
    GITHUB_PACKAGE_TOKEN = { value = "IMPORTED-BASELINE-VALUE-MANAGED-OUTSIDE-TERRAFORM", sensitive = true, managed = false }
    HF_TOKEN             = { value = "IMPORTED-BASELINE-VALUE-MANAGED-OUTSIDE-TERRAFORM", sensitive = true, managed = false }
    OPENROUTER_API_KEY   = { value = "IMPORTED-BASELINE-VALUE-MANAGED-OUTSIDE-TERRAFORM", sensitive = true, managed = false }
    R2_ACCESS_KEY_ID     = { value = "IMPORTED-BASELINE-VALUE-MANAGED-OUTSIDE-TERRAFORM", sensitive = true, managed = false }
    R2_ACCOUNT_ID        = { value = "IMPORTED-BASELINE-VALUE-MANAGED-OUTSIDE-TERRAFORM", sensitive = true, managed = false }
    R2_BUCKET_NAME       = { value = "IMPORTED-BASELINE-VALUE-MANAGED-OUTSIDE-TERRAFORM", sensitive = true, managed = false }
    R2_PUBLIC_URL        = { value = "IMPORTED-BASELINE-VALUE-MANAGED-OUTSIDE-TERRAFORM", sensitive = true, managed = false }
    R2_SECRET_ACCESS_KEY = { value = "IMPORTED-BASELINE-VALUE-MANAGED-OUTSIDE-TERRAFORM", sensitive = true, managed = false }
    RESEND_API_KEY       = { value = "IMPORTED-BASELINE-VALUE-MANAGED-OUTSIDE-TERRAFORM", sensitive = true, managed = false }
    RESEND_FROM_EMAIL    = { value = "IMPORTED-BASELINE-VALUE-MANAGED-OUTSIDE-TERRAFORM", sensitive = true, managed = false }
    TELEGRAM_BOT_TOKEN   = { value = "IMPORTED-BASELINE-VALUE-MANAGED-OUTSIDE-TERRAFORM", sensitive = true, managed = false }
    TELEGRAM_CHAT_ID     = { value = "IMPORTED-BASELINE-VALUE-MANAGED-OUTSIDE-TERRAFORM", sensitive = true, managed = false }
    UV_GROUP             = { value = "IMPORTED-BASELINE-VALUE-MANAGED-OUTSIDE-TERRAFORM", sensitive = true, managed = false }
  })
}

module "refresh_metrics_variables" {
  source = "../../modules/railway-variables"

  service_id             = data.terraform_remote_state.production.outputs.service_ids["refresh-metrics"]
  railway_environment_id = var.railway_environment_id
  variables = merge(module.shared_vars.grafana, module.shared_vars.sentry, {
    APP_ENV            = { value = "IMPORTED-BASELINE-VALUE-MANAGED-OUTSIDE-TERRAFORM", sensitive = true, managed = false }
    CONTACT_EMAIL      = { value = "IMPORTED-BASELINE-VALUE-MANAGED-OUTSIDE-TERRAFORM", sensitive = true, managed = false }
    DATABASE_URL       = { value = "IMPORTED-BASELINE-VALUE-MANAGED-OUTSIDE-TERRAFORM", sensitive = true, managed = false }
    FIXIE_URL          = { value = "IMPORTED-BASELINE-VALUE-MANAGED-OUTSIDE-TERRAFORM", sensitive = true, managed = false }
    TELEGRAM_BOT_TOKEN = { value = "IMPORTED-BASELINE-VALUE-MANAGED-OUTSIDE-TERRAFORM", sensitive = true, managed = false }
    TELEGRAM_CHAT_ID   = { value = "IMPORTED-BASELINE-VALUE-MANAGED-OUTSIDE-TERRAFORM", sensitive = true, managed = false }
    UV_GROUP           = { value = "IMPORTED-BASELINE-VALUE-MANAGED-OUTSIDE-TERRAFORM", sensitive = true, managed = false }
  })
}

module "rag_backfill_variables" {
  source = "../../modules/railway-variables"

  service_id             = data.terraform_remote_state.production.outputs.service_ids["rag-backfill"]
  railway_environment_id = var.railway_environment_id
  variables = merge(module.shared_vars.grafana, module.shared_vars.sentry, {
    APP_ENV                 = { value = "IMPORTED-BASELINE-VALUE-MANAGED-OUTSIDE-TERRAFORM", sensitive = true, managed = false }
    CONTACT_EMAIL           = { value = "IMPORTED-BASELINE-VALUE-MANAGED-OUTSIDE-TERRAFORM", sensitive = true, managed = false }
    DATABASE_URL            = { value = "IMPORTED-BASELINE-VALUE-MANAGED-OUTSIDE-TERRAFORM", sensitive = true, managed = false }
    FIXIE_URL               = { value = "IMPORTED-BASELINE-VALUE-MANAGED-OUTSIDE-TERRAFORM", sensitive = true, managed = false }
    GEMINI_API_KEY          = { value = "IMPORTED-BASELINE-VALUE-MANAGED-OUTSIDE-TERRAFORM", sensitive = true, managed = false }
    GITHUB_PACKAGE_TOKEN    = { value = "IMPORTED-BASELINE-VALUE-MANAGED-OUTSIDE-TERRAFORM", sensitive = true, managed = false }
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
    TELEGRAM_BOT_TOKEN      = { value = "IMPORTED-BASELINE-VALUE-MANAGED-OUTSIDE-TERRAFORM", sensitive = true, managed = false }
    TELEGRAM_CHAT_ID        = { value = "IMPORTED-BASELINE-VALUE-MANAGED-OUTSIDE-TERRAFORM", sensitive = true, managed = false }
    UV_GROUP                = { value = "IMPORTED-BASELINE-VALUE-MANAGED-OUTSIDE-TERRAFORM", sensitive = true, managed = false }
    VECTOR_DB_HOST          = { value = "IMPORTED-BASELINE-VALUE-MANAGED-OUTSIDE-TERRAFORM", sensitive = true, managed = false }
    VECTOR_DB_NAME          = { value = "IMPORTED-BASELINE-VALUE-MANAGED-OUTSIDE-TERRAFORM", sensitive = true, managed = false }
    VECTOR_DB_PASSWORD      = { value = "IMPORTED-BASELINE-VALUE-MANAGED-OUTSIDE-TERRAFORM", sensitive = true, managed = false }
    VECTOR_DB_PORT          = { value = "IMPORTED-BASELINE-VALUE-MANAGED-OUTSIDE-TERRAFORM", sensitive = true, managed = false }
    VECTOR_DB_SCHEMA        = { value = "IMPORTED-BASELINE-VALUE-MANAGED-OUTSIDE-TERRAFORM", sensitive = true, managed = false }
    VECTOR_DB_USER          = { value = "IMPORTED-BASELINE-VALUE-MANAGED-OUTSIDE-TERRAFORM", sensitive = true, managed = false }
  })
}

module "dedup_reconcile_variables" {
  source = "../../modules/railway-variables"

  service_id             = data.terraform_remote_state.production.outputs.service_ids["dedup-reconcile"]
  railway_environment_id = var.railway_environment_id
  variables = merge(module.shared_vars.grafana, module.shared_vars.sentry, {
    APP_ENV            = { value = "IMPORTED-BASELINE-VALUE-MANAGED-OUTSIDE-TERRAFORM", sensitive = true, managed = false }
    CONTACT_EMAIL      = { value = "IMPORTED-BASELINE-VALUE-MANAGED-OUTSIDE-TERRAFORM", sensitive = true, managed = false }
    DATABASE_URL       = { value = "IMPORTED-BASELINE-VALUE-MANAGED-OUTSIDE-TERRAFORM", sensitive = true, managed = false }
    FIXIE_URL          = { value = "IMPORTED-BASELINE-VALUE-MANAGED-OUTSIDE-TERRAFORM", sensitive = true, managed = false }
    TELEGRAM_BOT_TOKEN = { value = "IMPORTED-BASELINE-VALUE-MANAGED-OUTSIDE-TERRAFORM", sensitive = true, managed = false }
    TELEGRAM_CHAT_ID   = { value = "IMPORTED-BASELINE-VALUE-MANAGED-OUTSIDE-TERRAFORM", sensitive = true, managed = false }
    UV_GROUP           = { value = "IMPORTED-BASELINE-VALUE-MANAGED-OUTSIDE-TERRAFORM", sensitive = true, managed = false }
  })
}

# --- GitHub Actions secrets (US2 T023-028, FR-012) ---
# Repo-level secrets/variables are declared only in production's root config
# (see that file's comment) — this instance is environment-scoped only.
module "github_ci_staging" {
  source = "../../modules/github-ci-config"

  repository              = var.github_repository
  github_environment_name = var.github_environment_name

  secrets = {
    DATABASE_URL  = { value = "IMPORTED-BASELINE-VALUE-MANAGED-OUTSIDE-TERRAFORM", managed = false }
    RAILWAY_TOKEN = { value = "IMPORTED-BASELINE-VALUE-MANAGED-OUTSIDE-TERRAFORM", managed = false }
  }
}
