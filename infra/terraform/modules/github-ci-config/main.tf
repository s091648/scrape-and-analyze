locals {
  is_env_scoped = var.github_environment_name != null

  managed_secrets   = { for k, v in var.secrets : k => v if v.managed }
  baseline_secrets  = { for k, v in var.secrets : k => v if !v.managed }
  managed_vars      = { for k, v in var.variables : k => v if v.managed }
  baseline_vars     = { for k, v in var.variables : k => v if !v.managed }

  # Empty unless this instance is the matching scope, so exactly one of each
  # {repo,env}-scoped resource pair below ever has entries.
  repo_managed_secrets   = local.is_env_scoped ? {} : local.managed_secrets
  repo_baseline_secrets  = local.is_env_scoped ? {} : local.baseline_secrets
  env_managed_secrets    = local.is_env_scoped ? local.managed_secrets : {}
  env_baseline_secrets   = local.is_env_scoped ? local.baseline_secrets : {}

  repo_managed_vars  = local.is_env_scoped ? {} : local.managed_vars
  repo_baseline_vars = local.is_env_scoped ? {} : local.baseline_vars
  env_managed_vars   = local.is_env_scoped ? local.managed_vars : {}
  env_baseline_vars  = local.is_env_scoped ? local.baseline_vars : {}
}

# --- Repo-level secrets ---
resource "github_actions_secret" "managed" {
  for_each    = local.repo_managed_secrets
  repository  = var.repository
  secret_name = each.key
  value       = each.value.value
}

resource "github_actions_secret" "baseline" {
  for_each    = local.repo_baseline_secrets
  repository  = var.repository
  secret_name = each.key
  value       = each.value.value

  lifecycle {
    ignore_changes = [value]
  }
}

# --- Environment-scoped secrets ---
resource "github_actions_environment_secret" "managed" {
  for_each    = local.env_managed_secrets
  repository  = var.repository
  environment = var.github_environment_name
  secret_name = each.key
  value       = each.value.value
}

resource "github_actions_environment_secret" "baseline" {
  for_each    = local.env_baseline_secrets
  repository  = var.repository
  environment = var.github_environment_name
  secret_name = each.key
  value       = each.value.value

  lifecycle {
    ignore_changes = [value]
  }
}

# --- Repo-level variables ---
resource "github_actions_variable" "managed" {
  for_each      = local.repo_managed_vars
  repository    = var.repository
  variable_name = each.key
  value         = each.value.value
}

resource "github_actions_variable" "baseline" {
  for_each      = local.repo_baseline_vars
  repository    = var.repository
  variable_name = each.key
  value         = each.value.value

  lifecycle {
    ignore_changes = [value]
  }
}

# --- Environment-scoped variables ---
resource "github_actions_environment_variable" "managed" {
  for_each      = local.env_managed_vars
  repository    = var.repository
  environment   = var.github_environment_name
  variable_name = each.key
  value         = each.value.value
}

resource "github_actions_environment_variable" "baseline" {
  for_each      = local.env_baseline_vars
  repository    = var.repository
  environment   = var.github_environment_name
  variable_name = each.key
  value         = each.value.value

  lifecycle {
    ignore_changes = [value]
  }
}
