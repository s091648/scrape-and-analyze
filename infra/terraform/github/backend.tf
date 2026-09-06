# HCP Terraform remote backend. `workspaces { tags = [...] }` — NOT a hard-coded
# `name` — so a single root config can target either workspace:
#
#   TF_WORKSPACE=staging     terraform plan ...   -> workspace "staging"
#   TF_WORKSPACE=production   terraform apply ...  -> workspace "production"
#
# With `tags` (unlike `name`), `terraform.workspace` also reflects the real
# selected workspace name, which locals.tf's `check` block asserts against
# var.app_env so a mismatched TF_WORKSPACE / -var-file pair fails loudly instead
# of applying one environment's values into the other's state.
#
# Both workspaces live in the "scrape-analyzer" HCP project (local execution
# mode — secret values are injected as TF_VAR_* at apply time, FR-004a).
terraform {
  cloud {
    organization = "scrape-analyzer"

    workspaces {
      tags = ["scrape-analyzer"]
    }
  }
}
