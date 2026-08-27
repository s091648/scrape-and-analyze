# Each output is already shaped as the railway-variables module's `variables`
# input (map(object({value, sensitive, managed}))) — a consumer just does
# `variables = merge(module.shared_vars.grafana, module.shared_vars.sentry, {
#   ...this service's own unique entries...
# })`. managed = true throughout: this module's whole point is that Terraform
# becomes the actual source of truth for these values instead of a baseline
# import (see infra/terraform/README.md's "CI trigger cadence" section /
# specs/025-iac-provisioning's shared-variable migration discussion).

output "grafana" {
  description = "Observability: Grafana Cloud (Loki logs + OTLP traces/metrics). Consumed by every service that ships telemetry to Grafana."
  sensitive   = true
  value = {
    GRAFANA_API_KEY       = { value = var.grafana_api_key, sensitive = true, managed = true }
    GRAFANA_LOKI_URL      = { value = var.grafana_loki_url, sensitive = true, managed = true }
    GRAFANA_LOKI_USER     = { value = var.grafana_loki_user, sensitive = true, managed = true }
    GRAFANA_OTLP_ENDPOINT = { value = var.grafana_otlp_endpoint, sensitive = true, managed = true }
    GRAFANA_OTLP_USER     = { value = var.grafana_otlp_user, sensitive = true, managed = true }
  }
}

output "sentry" {
  description = "Error tracking: Sentry. Only the services that actually report errors to Sentry consume this — not every service in the grafana group above (e.g. chatbot-plugin, fastembed don't)."
  sensitive   = true
  value = {
    SENTRY_DSN = { value = var.sentry_dsn, sensitive = true, managed = true }
  }
}
