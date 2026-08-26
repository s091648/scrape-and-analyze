output "variable_names" {
  value       = keys(var.variables)
  description = "Names of all variables this instance manages (both baseline-imported and actively-managed), for terraform plan review / auditing which keys are IaC-tracked (FR-010)."
}

output "managed_variable_names" {
  value       = keys(local.managed_vars)
  description = "Subset actively controlled by Terraform (value enforced on apply)."
}
