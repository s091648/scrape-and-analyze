locals {
  is_env_scoped = var.github_environment_name != null

  # Drop null entries (a key set in one environment's tfvars but not the other's).
  secrets_present   = { for k, v in var.secrets : k => v if v != null }
  variables_present = { for k, v in var.variables : k => v if v != null }

  # Exactly one of each {repo, env}-scoped pair below is ever non-empty. Kept as
  # `for` comprehensions over *_present (not a `? {} :` ternary) so a sensitive
  # taint on var.secrets is carried consistently to whichever side is active.
  repo_secrets = { for k, v in local.secrets_present : k => v if !local.is_env_scoped }
  env_secrets  = { for k, v in local.secrets_present : k => v if local.is_env_scoped }
  repo_vars    = { for k, v in local.variables_present : k => v if !local.is_env_scoped }
  env_vars     = { for k, v in local.variables_present : k => v if local.is_env_scoped }
}

# `for_each` cannot iterate a map Terraform has marked sensitive as a whole (any
# `sensitive = true` value taints the whole map — "the sensitive value could be
# exposed as a resource instance key"). Iterate a nonsensitive() copy — `each.key`
# is only ever a secret NAME (e.g. "CODECOV_TOKEN"), never derived from a secret —
# but re-index into the ORIGINAL local.*_secrets for `value` so it keeps its real
# sensitivity marking. Same pattern as modules/railway-variables/main.tf.
# (Confirmed necessary against github ~> 6.0 on the R36 import — 2026-08-31.)
resource "github_actions_secret" "repo" {
  for_each    = nonsensitive(local.repo_secrets)
  repository  = var.repository
  secret_name = each.key
  value       = local.repo_secrets[each.key]
}

resource "github_actions_environment_secret" "env" {
  for_each    = nonsensitive(local.env_secrets)
  repository  = var.repository
  environment = var.github_environment_name
  secret_name = each.key
  value       = local.env_secrets[each.key]
}

resource "github_actions_variable" "repo" {
  for_each      = local.repo_vars
  repository    = var.repository
  variable_name = each.key
  value         = each.value
}

resource "github_actions_environment_variable" "env" {
  for_each      = local.env_vars
  repository    = var.repository
  environment   = var.github_environment_name
  variable_name = each.key
  value         = each.value
}
