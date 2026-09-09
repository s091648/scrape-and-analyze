# Guard: the only thing standing between a fat-fingered `TF_WORKSPACE` /
# `-var-file` mismatch and applying one environment's values into the other's
# state. `terraform.workspace` reflects the real HCP workspace name (because
# backend.tf uses `workspaces { tags = [...] }`, not a hard-coded `name`);
# `var.app_env` comes from secrets/<env>.tfvars. The Makefile and the reusable
# terraform.yml workflow always set both from a single ENV= / environment input,
# so in normal use they can't disagree — this catches the abnormal case.
check "workspace_matches_env" {
  assert {
    condition     = terraform.workspace == var.app_env
    error_message = "TF_WORKSPACE=\"${terraform.workspace}\" but app_env=\"${var.app_env}\" — refusing to apply one environment's values into the other's workspace. Set TF_WORKSPACE and -var-file=secrets/<env>.tfvars to the same environment (or use `make terraform-* ENV=<env>`)."
  }
}
