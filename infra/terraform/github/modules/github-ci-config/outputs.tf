output "managed_secret_names" {
  value       = sort(keys(local.secrets_present))
  description = "Names of the secrets this instance manages in the current environment — never includes values."
}

output "managed_variable_names" {
  value       = sort(keys(local.variables_present))
  description = "Names of the variables this instance manages in the current environment."
}
