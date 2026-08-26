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
