# The github token is an FR-013 bootstrap credential — supplied only as
# TF_VAR_github_token at apply time (from infra/terraform/github/.env locally,
# from GitHub Actions secret TF_GITHUB_TOKEN in CI), never written into a .tf or
# a tracked .tfvars.example.
provider "github" {
  owner = var.github_owner
  token = var.github_token
}
