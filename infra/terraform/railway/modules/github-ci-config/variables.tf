variable "repository" {
  type        = string
  description = "Repository name (no owner — the provider block is already scoped to it)."
}

variable "github_environment_name" {
  type        = string
  default     = null
  description = "GitHub Environment name (e.g. \"scraper / staging\"). When set, secrets/variables are created environment-scoped; when null, repo-level."
}

variable "secrets" {
  type        = map(string)
  default     = {}
  description = <<-EOT
    One entry per GitHub Actions secret, keyed by secret name. Every entry is
    Terraform-managed — the value is enforced on every apply (no baseline
    half-state). Values MUST come from a TF_VAR_*-injected root variable, never a
    literal (FR-004a). A `null` value skips that key (lets a secret exist in one
    environment's tfvars but not the other's without Terraform trying to create it).
  EOT
}

variable "variables" {
  type        = map(string)
  default     = {}
  description = "One entry per GitHub Actions (non-secret) variable, keyed by name. Same null-skip semantics as `secrets`; nothing sensitive to protect."
}
