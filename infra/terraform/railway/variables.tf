# Every input this config takes. This file is the SCHEMA; the actual values live
# in git-ignored secrets/{shared,staging,production}.tfvars (mirrored key-for-key
# by the tracked *.tfvars.example files), layered at apply time:
#
#   terraform -chdir=infra/terraform <cmd> \
#     -var-file=secrets/shared.tfvars -var-file=secrets/<env>.tfvars
#
# `-var-file` is applied left-to-right, later wins — so a key in <env>.tfvars
# overrides the same key in shared.tfvars. A variable left unset (default = null)
# is simply omitted from that environment's Railway/GitHub resources (see
# modules/railway-variables' null-skip behaviour) — that's how a key present in
# one environment but not the other stays a clean per-environment difference.
#
# secret vars carry `sensitive = true`; their values MUST arrive via
# TF_VAR_*/-var-file, never a literal in a tracked file (FR-004a).

# ---------------------------------------------------------------------------
# Bootstrap credentials (FR-013) + environment identity
#
# NOTE: This root now only manages GitHub Actions secrets/variables (github-ci.tf).
# The Railway service variables are pushed by scripts/push_railway_variables.py
# from the same secrets/*.tfvars files — so many `variable` blocks below are
# declared ONLY so `-var-file` doesn't warn about the keys the script needs;
# Terraform itself doesn't consume them.
# ---------------------------------------------------------------------------

variable "github_token" {
  type        = string
  sensitive   = true
  description = "GitHub PAT scoped to manage this repo's Actions secrets/variables. From TF_VAR_github_token / secrets.TF_GITHUB_TOKEN."
}

variable "github_owner" {
  type        = string
  description = "GitHub org/user that owns the repository (e.g. s091648)."
}

variable "github_repository" {
  type        = string
  description = "Repository name without owner (e.g. scrape-and-analyze)."
}

variable "app_env" {
  type        = string
  description = "This environment's name — \"staging\" or \"production\". Set in secrets/<env>.tfvars. Asserted against terraform.workspace by locals.tf's check block, and also applied as the APP_ENV Railway variable on every service that declares it."

  validation {
    condition     = contains(["staging", "production"], var.app_env)
    error_message = "app_env must be \"staging\" or \"production\"."
  }
}

variable "railway_environment_id" {
  type        = string
  description = "This environment's Railway environment ID (a UUID). Set in secrets/<env>.tfvars."
}

variable "railway_project_id" {
  type        = string
  default     = ""
  description = "Railway project ID. Not consumed by Terraform — scripts/push_railway_variables.py reads it from secrets/shared.tfvars. Declared here so -var-file doesn't warn. Non-secret UUID."
}

# ---------------------------------------------------------------------------
# Railway service IDs — stable UUIDs, service objects are NOT Terraform-managed
# (revision 2). Same in both environments (a service is project-scoped;
# railway_variable targets it per environment_id). Set in secrets/shared.tfvars.
# ---------------------------------------------------------------------------

variable "service_id_dashboard_backend" { type = string }
variable "service_id_dashboard_frontend" { type = string }
variable "service_id_storybook" { type = string }
variable "service_id_scrape_and_analyze" { type = string }
variable "service_id_chatbot_plugin" { type = string }
variable "service_id_fastembed" { type = string }
variable "service_id_weekly_report" { type = string }
variable "service_id_refresh_metrics" { type = string }
variable "service_id_rag_backfill" { type = string }
variable "service_id_dedup_reconcile" { type = string }

# ===========================================================================
# SHARED variable groups — values identical across every consuming service
# within an environment (shaped into local.shared groups by shared.tf). Most
# are also identical across staging/production and belong in shared.tfvars; a
# few (database_url, cache_redis_url, app_env) may differ per environment — put
# those in secrets/<env>.tfvars instead. The var declaration here doesn't care
# which file supplies the value.
# ===========================================================================

# --- observability: Grafana Cloud ---
variable "grafana_api_key" {
  type      = string
  sensitive = true
}
variable "grafana_loki_url" { type = string }
variable "grafana_loki_user" { type = string }
variable "grafana_otlp_endpoint" { type = string }
variable "grafana_otlp_user" { type = string }

# --- error tracking: Sentry ---
variable "sentry_dsn" {
  type      = string
  sensitive = true
}

# --- rag_dense (chatbot_plugin, dashboard_backend, rag_backfill, scrape_and_analyze) ---
variable "rag_dense_api_key_env" { type = string }
variable "rag_dense_dimension" { type = string }
variable "rag_dense_model" { type = string }
variable "rag_dense_provider" { type = string }
variable "rag_dense_rpd" { type = string }
variable "rag_dense_rpm" { type = string }
variable "rag_dense_tpm" { type = string }
variable "rag_gemini_api_key" {
  type      = string
  sensitive = true
}

# --- rag_dense_endpoint_url (dashboard_backend, rag_backfill, scrape_and_analyze — NOT chatbot_plugin) ---
variable "rag_dense_endpoint_url" { type = string }

# --- rag_sparse (chatbot_plugin, dashboard_backend, rag_backfill, scrape_and_analyze) ---
variable "rag_sparse_dimension" { type = string }
variable "rag_sparse_model" { type = string }
variable "rag_sparse_provider" { type = string }

# --- rag_sparse_limits (dashboard_backend, rag_backfill, scrape_and_analyze — NOT chatbot_plugin) ---
variable "rag_sparse_rpd" { type = string }
variable "rag_sparse_rpm" { type = string }
variable "rag_sparse_tpm" { type = string }

# --- vector_db (chatbot_plugin, rag_backfill, scrape_and_analyze) ---
variable "vector_db_host" { type = string }
variable "vector_db_name" { type = string }
variable "vector_db_password" {
  type      = string
  sensitive = true
}
variable "vector_db_port" { type = string }
variable "vector_db_schema" { type = string }
variable "vector_db_user" { type = string }

# --- rag_chunking (rag_backfill, scrape_and_analyze) ---
variable "rag_chunk_overlap" { type = string }
variable "rag_chunk_size" { type = string }
variable "rag_embed_batch_size" { type = string }

# --- notifications (dedup_reconcile, rag_backfill, refresh_metrics, scrape_and_analyze, weekly_report) ---
variable "telegram_bot_token" {
  type      = string
  sensitive = true
}
variable "telegram_chat_id" { type = string }
variable "fixie_url" {
  type      = string
  sensitive = true
}

# --- single-key shared groups ---
variable "database_url" {
  type      = string
  sensitive = true
}
variable "cache_redis_url" {
  type      = string
  sensitive = true
}
variable "gemini_api_key" {
  type      = string
  sensitive = true
}
variable "openrouter_api_key" {
  type      = string
  sensitive = true
}
variable "github_package_token" {
  type      = string
  sensitive = true
}

# ===========================================================================
# PER-SERVICE values — consumed by a single service (or a few, with the same
# value). `default = null` ⇒ optional / environment-specific: set only in the
# tfvars file(s) where the service actually has that key.
# ===========================================================================

# --- dashboard_backend ---
variable "chat_service_api_key" {
  type      = string
  sensitive = true
  default   = null
}
variable "chat_service_url" {
  type    = string
  default = null
}
# The frontend's public, browser-facing URL WITH scheme (e.g.
# "https://$${{dashboard-frontend.RAILWAY_PUBLIC_DOMAIN}}"). One source value,
# delivered as FRONTEND_ORIGIN (dashboard_backend CORS allow_origins +
# weekly_report notification links) and as NEXTAUTH_URL (dashboard_frontend).
# Must carry the scheme — CORS matches the exact Origin header, and NextAuth
# needs an absolute URL.
variable "frontend_public_url" {
  type    = string
  default = null
}
variable "grafana_prometheus_url" {
  type    = string
  default = null
}
variable "grafana_prometheus_user" {
  type    = string
  default = null
}
variable "grafana_tempo_url" {
  type    = string
  default = null
}
variable "grafana_tempo_user" {
  type    = string
  default = null
}
variable "maxmind_license_key" {
  type      = string
  sensitive = true
  default   = null
}
variable "nextauth_secret" {
  type      = string
  sensitive = true
  default   = null
}
variable "redis_url" {
  type      = string
  sensitive = true
  default   = null
}
variable "search_index_redis_url" {
  type      = string
  sensitive = true
  default   = null
}
variable "swagger_try_it_out_enabled" {
  type    = string
  default = null
}

# --- dashboard_frontend ---
variable "backend_url" {
  type    = string
  default = null
}
variable "google_client_id" {
  type      = string
  sensitive = true
  default   = null
}
variable "google_client_secret" {
  type      = string
  sensitive = true
  default   = null
}
variable "grafana_sa_token" {
  type      = string
  sensitive = true
  default   = null
}
variable "grafana_url" {
  type    = string
  default = null
}
# NEXTAUTH_URL is supplied from var.frontend_public_url (declared above).

# --- scrape_and_analyze (some are staging-only search config) ---
variable "search_autocomplete_max_query_len" {
  type    = string
  default = null
}
variable "search_min_doc_freq" {
  type    = string
  default = null
}

# --- chatbot_plugin ---
variable "chatbot_max_tokens" {
  type    = string
  default = null
}

# --- weekly_report (R2 object storage + Resend email + HuggingFace) ---
variable "hf_token" {
  type      = string
  sensitive = true
  default   = null
}
variable "r2_access_key_id" {
  type      = string
  sensitive = true
  default   = null
}
variable "r2_account_id" {
  type    = string
  default = null
}
variable "r2_bucket_name" {
  type    = string
  default = null
}
variable "r2_public_url" {
  type    = string
  default = null
}
variable "r2_secret_access_key" {
  type      = string
  sensitive = true
  default   = null
}
variable "resend_api_key" {
  type      = string
  sensitive = true
  default   = null
}
variable "resend_from_email" {
  type    = string
  default = null
}

# --- CONTACT_EMAIL (scrape_and_analyze, weekly_report, refresh_metrics, rag_backfill, dedup_reconcile) ---
# Single var — if a service genuinely needs a different address, split into
# contact_email_<service> the same way uv_group_* is split below.
variable "contact_email" {
  type    = string
  default = null
}

# --- UV_GROUP — genuinely differs per service (selects that service's uv
# dependency group / start command). scrape_and_analyze is the base image and
# has no override. ---
variable "uv_group_weekly_report" {
  type    = string
  default = null
}
variable "uv_group_refresh_metrics" {
  type    = string
  default = null
}
variable "uv_group_rag_backfill" {
  type    = string
  default = null
}
variable "uv_group_dedup_reconcile" {
  type    = string
  default = null
}

# --- RAG_SPARSE_ENDPOINT_URL — same value across the four consuming services
# (dashboard_backend, scrape_and_analyze, chatbot_plugin, rag_backfill), the
# fastembed sidecar's internal URL. Declared once as a shared single-key group
# in shared.tf. ---
variable "rag_sparse_endpoint_url" {
  type    = string
  default = null
}

# ===========================================================================
# GitHub Actions secrets/variables (FR-012) — consumed by github-ci.tf.
# Repo-level secrets that ci.yml/release.yml read; the RAILWAY_SERVICE_ID_*
# GitHub *variables* are derived from the service_id_* vars above, not declared
# here. DATABASE_URL / RAILWAY_TOKEN are environment-scoped GitHub secrets.
# ===========================================================================

variable "gh_claude_api_key" {
  type      = string
  sensitive = true
  default   = null
}
variable "gh_codecov_token" {
  type      = string
  sensitive = true
  default   = null
}
variable "gh_gemini_api_key" {
  type      = string
  sensitive = true
  default   = null
}
variable "gh_gist_id" {
  type      = string
  sensitive = true
  default   = null
}
variable "gh_gist_secret" {
  type      = string
  sensitive = true
  default   = null
}
variable "gh_nextauth_secret" {
  type      = string
  sensitive = true
  default   = null
}
variable "gh_npm_token" {
  type      = string
  sensitive = true
  default   = null
}
variable "gh_openrouter_api_key" {
  type      = string
  sensitive = true
  default   = null
}
variable "gh_release_pat" {
  type      = string
  sensitive = true
  default   = null
}

# repo-level GitHub Actions (non-secret) variables
variable "gh_var_backend_url" {
  type    = string
  default = null
}
variable "gh_var_storybook_url" {
  type    = string
  default = null
}

# environment-scoped GitHub Actions secrets (per scraper / <env>)
variable "gh_env_database_url" {
  type      = string
  sensitive = true
  default   = null
}
variable "gh_env_railway_token" {
  type      = string
  sensitive = true
  default   = null
}

# environment-scoped GitHub Actions (non-secret) variable — the public frontend
# URL lighthouse.yml audits for that environment (staging on PRs, production on a
# manual dispatch).
variable "gh_env_frontend_url" {
  type    = string
  default = null
}
