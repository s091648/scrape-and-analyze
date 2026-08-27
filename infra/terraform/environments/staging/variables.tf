variable "railway_project_id" {
  type        = string
  description = "The Railway project ID shared by all environments."
}

variable "railway_environment_id" {
  type        = string
  description = "This environment's Railway environment ID."
}

variable "railway_token" {
  type        = string
  description = "Account/workspace-level Railway token (FR-004a: from TF_VAR_railway_token, never literal)."
  sensitive   = true
}

variable "github_token" {
  type        = string
  description = "GitHub PAT scoped to manage repo secrets/variables — the FR-013 bootstrap credential (FR-004a: from TF_VAR_github_token, never literal)."
  sensitive   = true
}

variable "github_owner" {
  type        = string
  description = "GitHub org/user that owns the repository."
}

variable "github_repository" {
  type        = string
  description = "GitHub repository name (without owner)."
}

variable "github_environment_name" {
  type        = string
  description = "The GitHub Environment name ci.yml/release.yml use in their environment: key (e.g. \"scraper / staging\")."
}

# --- Shared variable groups (modules/shared-variables) — specs/025-iac-provisioning
# shared-variable migration, pilot: observability. From TF_VAR_*, never literal
# (FR-004a); confirmed identical across every consumer via
# scripts/pull_railway_variables.py before this migration.
variable "grafana_api_key" {
  type      = string
  sensitive = true
}

variable "grafana_loki_url" {
  type      = string
  sensitive = true
}

variable "grafana_loki_user" {
  type      = string
  sensitive = true
}

variable "grafana_otlp_endpoint" {
  type      = string
  sensitive = true
}

variable "grafana_otlp_user" {
  type      = string
  sensitive = true
}

variable "sentry_dsn" {
  type      = string
  sensitive = true
}
