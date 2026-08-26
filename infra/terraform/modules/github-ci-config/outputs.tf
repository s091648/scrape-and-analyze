output "managed_secret_names" {
  value       = keys(var.secrets)
  description = "Names of all secrets this instance manages (both baseline-imported and actively-managed), for terraform plan review — never includes values."
}

output "managed_variable_names" {
  value       = keys(var.variables)
  description = "Names of all variables this instance manages."
}
