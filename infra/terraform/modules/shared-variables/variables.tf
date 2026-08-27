# One input per shared secret, grouped below (outputs.tf) into named maps —
# this module holds no resources; it exists purely so a value that's genuinely
# identical across several services in the same environment is declared once
# and merge()'d into each consumer, instead of repeated per-service (CDK-style
# central "constants" object; see specs/025-iac-provisioning follow-up
# discussion). Each environment (environments/{staging,production}/main.tf)
# instantiates this module once with its own TF_VAR_*-sourced values — never a
# literal (FR-004a) — so the *grouping* is shared, but each environment still
# supplies (and can diverge on) its own actual value.

variable "grafana_api_key" {
  type        = string
  description = "Grafana Cloud API key — identical across every service that uses it today (confirmed via scripts/pull_railway_variables.py before this migration)."
  sensitive   = true
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
  type        = string
  description = "Sentry DSN — only consumed by services that report errors to Sentry (not every service in the grafana group above)."
  sensitive   = true
}
