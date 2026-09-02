/**
 * Railway IaC — v2 de-`preserve()`d values (025 Revision 6, task T6-08a/b).
 *
 * NON-SECRET, non-environment-specific env-var values, lifted out of Railway's
 * live config and committed here so `.railway/railway.ts` — not Railway's
 * dashboard / the Revision-4 `secrets/railway-*.tfvars` + push_railway_variables.py
 * — is their source of truth. `railway config plan` MUST stay clean on both
 * environments after every group moved here (a diff = the literal disagrees with
 * live; reconcile before committing).
 *
 * What stays OUT of this file:
 *   - secrets (API keys, tokens, passwords)  → `process.env.X` (task T6-08c)
 *   - `${{Redis.*}}` / `${{Postgres.*}}` / cross-service domain refs
 *                                            → `Redis.env.*` etc. (task T6-08b)
 *   - values that differ per environment     → a `ctx`-branch in railway.ts
 */

// RAG dense-embedding tuning — provider is Gemini; the API key itself
// (RAG_GEMINI_API_KEY) stays preserve() until T6-08c.
export const RAG_DENSE_ENV = {
  RAG_DENSE_API_KEY_ENV: "RAG_GEMINI_API_KEY", // the *name* of the key var, not a secret
  RAG_DENSE_DIMENSION: "768",
  RAG_DENSE_MODEL: "gemini-embedding-001",
  RAG_DENSE_PROVIDER: "gemini",
  RAG_DENSE_RPD: "1000",
  RAG_DENSE_RPM: "100",
  RAG_DENSE_TPM: "30000",
} as const;

// RAG sparse-embedding tuning — served by the in-project `fastembed` service.
// RAG_SPARSE_ENDPOINT_URL is a cross-service ref → T6-08b.
export const RAG_SPARSE_ENV = {
  RAG_SPARSE_DIMENSION: "30522",
  RAG_SPARSE_MODEL: "prithivida/Splade_PP_en_v1",
  RAG_SPARSE_PROVIDER: "endpoint",
} as const;

// RAG chunking / batching.
export const RAG_CHUNKING_ENV = {
  RAG_CHUNK_OVERLAP: "150",
  RAG_CHUNK_SIZE: "1500",
  RAG_EMBED_BATCH_SIZE: "70",
} as const;

// Grafana Cloud ingest endpoints + instance/tenant IDs — NOT the credentials
// (GRAFANA_API_KEY / GRAFANA_SA_TOKEN stay process.env → T6-08c). Same values in
// both environments.
export const GRAFANA_ENV = {
  GRAFANA_LOKI_URL: "https://logs-prod-030.grafana.net/loki/api/v1",
  GRAFANA_LOKI_USER: "1516028",
  GRAFANA_OTLP_ENDPOINT: "https://otlp-gateway-prod-ap-northeast-0.grafana.net/otlp",
  GRAFANA_OTLP_USER: "1558239",
} as const;

// Extra Grafana endpoints only dashboard-backend reads (Prometheus + Tempo).
export const GRAFANA_BACKEND_ENV = {
  GRAFANA_PROMETHEUS_URL:
    "https://prometheus-prod-49-prod-ap-northeast-0.grafana.net/api/prom",
  GRAFANA_PROMETHEUS_USER: "3040706",
  GRAFANA_TEMPO_URL: "https://tempo-prod-20-prod-ap-northeast-0.grafana.net/tempo",
  GRAFANA_TEMPO_USER: "1510333",
} as const;

// The public Grafana dashboard URL the frontend links to (GRAFANA_SA_TOKEN, the
// paired service-account token, stays process.env → T6-08c).
export const GRAFANA_URL = "https://s091648.grafana.net/";

// Non-secret single-value config shared across services.
export const CONTACT_EMAIL = "s091648@gmail.com";
export const VECTOR_DB_SCHEMA = "vectors";
