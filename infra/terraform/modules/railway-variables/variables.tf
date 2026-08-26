variable "service_id" {
  type        = string
  description = "The Railway service ID these variables attach to (from the railway-service module's output, or a raw ID)."
}

variable "railway_environment_id" {
  type        = string
  description = "The environment these variables apply to — this IS genuinely per-environment, unlike railway_service (research.md §9)."
}

variable "variables" {
  type = map(object({
    value     = string
    sensitive = optional(bool, false)
    managed   = optional(bool, false)
  }))
  description = <<-EOT
    One entry per environment variable.
    - `managed = true`: Terraform is the source of truth for `value` — `sensitive = true` entries MUST receive
      their `value` from a TF_VAR_*-injected root variable, never a literal (FR-004a).
    - `managed = false` (default): a "baseline" entry — the variable's existence/name is declared and imported
      (so it shows up in `terraform plan` review, satisfying FR-002's "one place to see what a service uses"),
      but its live value is intentionally left untouched (`lifecycle.ignore_changes`) rather than forced to
      match a placeholder. Used for the bulk initial migration of ~150+ pre-existing variables whose real
      values were never typed into this session (see research.md's PoC security note) — promote an entry to
      `managed = true` (and supply its real value via TF_VAR_*) only when you actually want Terraform to start
      controlling that specific value going forward.
  EOT
  default = {}
}
