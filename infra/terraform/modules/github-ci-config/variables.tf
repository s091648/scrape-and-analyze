variable "repository" {
  type        = string
  description = "Repository name (no owner — the provider block is already scoped to it)."
}

variable "github_environment_name" {
  type        = string
  description = "GitHub Environment name (e.g. \"scraper / staging\"), or null for repo-level secrets/variables not tied to either environment."
  default     = null
}

variable "secrets" {
  type = map(object({
    value   = string
    managed = optional(bool, false)
  }))
  description = <<-EOT
    One entry per GitHub Actions secret. Same managed/baseline split as the
    railway-variables module (contracts/railway-service-module.md):
    - `managed = true`: Terraform enforces `value` on every apply — MUST come from a
      TF_VAR_*-injected root variable, never a literal (FR-004a).
    - `managed = false` (default): baseline-imported — existence/name is tracked and
      reviewable, but the live value is left alone (`lifecycle.ignore_changes`).
  EOT
  default = {}
}

variable "variables" {
  type = map(object({
    value   = string
    managed = optional(bool, false)
  }))
  description = "One entry per GitHub Actions (non-secret) variable. Same managed/baseline split as `secrets` above, but there's nothing sensitive to protect either way since these are non-secret by definition."
  default     = {}
}
