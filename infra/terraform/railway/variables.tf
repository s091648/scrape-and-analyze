# Every input this Terraform root takes. It manages ONLY the GitHub Actions
# secrets/variables ci.yml / release.yml read (github-ci.tf). Values live in
# git-ignored secrets/github-{shared,<env>}.tfvars (mirrored key-for-key by the
# tracked *.tfvars.example files), layered at apply time:
#
#   terraform -chdir=infra/terraform/railway <cmd> \
#     -var-file=secrets/github-shared.tfvars -var-file=secrets/github-<env>.tfvars
#
# `-var-file` is applied left-to-right, later wins. Secret vars carry
# `sensitive = true`; their values MUST arrive via -var-file, never a literal in
# a tracked file (FR-004a). The Railway service env vars are a separate concern
# (secrets/railway-*.tfvars → scripts/tfvars_to_env.py → `railway config`).

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
  description = "This environment's name — \"staging\" or \"production\". Set in secrets/github-<env>.tfvars. Asserted against terraform.workspace by locals.tf's check block; also selects the \"scraper / <env>\" GitHub Environment for the env-scoped secrets/variable."

  validation {
    condition     = contains(["staging", "production"], var.app_env)
    error_message = "app_env must be \"staging\" or \"production\"."
  }
}

# --- Railway service IDs (stable UUIDs, same in both environments) — consumed by
#     github-ci.tf for the RAILWAY_SERVICE_ID_* repo variables. Set in
#     secrets/github-shared.tfvars. ---
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
# GitHub Actions secrets/variables (FR-012) — consumed by github-ci.tf.
# Repo-level secrets ci.yml/release.yml read; the RAILWAY_SERVICE_ID_* GitHub
# *variables* come from service_id_* above. gh_env_* are scoped to the
# "scraper / <env>" GitHub Environment.
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

# environment-scoped GitHub Actions secrets (per "scraper / <env>")
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
# URL lighthouse.yml audits for that environment.
variable "gh_env_frontend_url" {
  type    = string
  default = null
}
