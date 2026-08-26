locals {
  managed_vars  = { for k, v in var.variables : k => v if v.managed }
  baseline_vars = { for k, v in var.variables : k => v if !v.managed }
}

# Actively Terraform-managed — value is enforced on every apply.
resource "railway_variable" "managed" {
  for_each = local.managed_vars

  name           = each.key
  value          = each.value.value
  service_id     = var.service_id
  environment_id = var.railway_environment_id
}

# Baseline-imported only — existence/name is tracked and reviewable, but the
# live value is deliberately left alone (see variables.tf's `managed` doc).
resource "railway_variable" "baseline" {
  for_each = local.baseline_vars

  name           = each.key
  value          = each.value.value
  service_id     = var.service_id
  environment_id = var.railway_environment_id

  lifecycle {
    ignore_changes = [value]
  }
}
