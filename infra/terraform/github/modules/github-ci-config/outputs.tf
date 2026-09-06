output "managed_secret_names" {
  # keys()/sort() propagate the sensitive taint from the secret *values* onto the
  # name list; nonsensitive() is safe here because these are only secret NAMES
  # (e.g. "CODECOV_TOKEN"), never a value. Without it, `terraform plan` errors on
  # this non-sensitive output. Same reasoning as the nonsensitive() in main.tf.
  value       = sort(nonsensitive(keys(local.secrets_present)))
  description = "Names of the secrets this instance manages in the current environment — never includes values."
}

output "managed_variable_names" {
  value       = sort(keys(local.variables_present))
  description = "Names of the variables this instance manages in the current environment."
}
