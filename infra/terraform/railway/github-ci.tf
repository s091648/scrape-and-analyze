# GitHub Actions secrets/variables that ci.yml / release.yml read (FR-012).
#
# Three instances of modules/github-ci-config:
#   - github_ci_repo         : repo-level (not tied to an environment)
#   - github_ci_staging      : scoped to the "scraper / staging" GitHub Environment
#   - github_ci_production   : scoped to "scraper / production"
#
# Repo-level entries are declared ONLY in github_ci_repo (a repo secret is
# singular — declaring it per environment would make both workspaces fight over
# the same object). So github_ci_repo's `secrets`/`variables` are applied
# whichever environment this run targets; keep their values in secrets/shared.tfvars.
#
# NOT managed here (FR-013 bootstrap credentials): TF_API_TOKEN, TF_GITHUB_TOKEN.

module "github_ci_repo" {
  source     = "./modules/github-ci-config"
  repository = var.github_repository

  secrets = {
    CLAUDE_API_KEY     = var.gh_claude_api_key
    CODECOV_TOKEN      = var.gh_codecov_token
    GEMINI_API_KEY     = var.gh_gemini_api_key
    GIST_ID            = var.gh_gist_id
    GIST_SECRET        = var.gh_gist_secret
    NEXTAUTH_SECRET    = var.gh_nextauth_secret
    NPM_TOKEN          = var.gh_npm_token
    OPENROUTER_API_KEY = var.gh_openrouter_api_key
    RELEASE_PAT        = var.gh_release_pat
  }

  variables = {
    BACKEND_URL   = var.gh_var_backend_url
    STORYBOOK_URL = var.gh_var_storybook_url

    RAILWAY_SERVICE_ID_DASHBOARD_BACKEND  = var.service_id_dashboard_backend
    RAILWAY_SERVICE_ID_DASHBOARD_FRONTEND = var.service_id_dashboard_frontend
    RAILWAY_SERVICE_ID_STORYBOOK          = var.service_id_storybook
    RAILWAY_SERVICE_ID_SCRAPE_AND_ANALYZE = var.service_id_scrape_and_analyze
    RAILWAY_SERVICE_ID_CHATBOT_PLUGIN     = var.service_id_chatbot_plugin
    RAILWAY_SERVICE_ID_FASTEMBED          = var.service_id_fastembed
    RAILWAY_SERVICE_ID_WEEKLY_REPORT      = var.service_id_weekly_report
    RAILWAY_SERVICE_ID_REFRESH_METRICS    = var.service_id_refresh_metrics
    RAILWAY_SERVICE_ID_RAG_BACKFILL       = var.service_id_rag_backfill
    RAILWAY_SERVICE_ID_DEDUP_RECONCILE    = var.service_id_dedup_reconcile
  }
}

module "github_ci_env" {
  source                  = "./modules/github-ci-config"
  repository              = var.github_repository
  github_environment_name = "scraper / ${var.app_env}"

  secrets = {
    DATABASE_URL  = var.gh_env_database_url
    RAILWAY_TOKEN = var.gh_env_railway_token
  }

  # FRONTEND_URL is per-environment (lighthouse.yml audits staging on PRs, and can
  # target production on a manual workflow_dispatch — see .github/workflows/lighthouse.yml).
  variables = {
    FRONTEND_URL = var.gh_env_frontend_url
  }
}
