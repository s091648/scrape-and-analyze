/**
 * PromQL helpers for the Postgres metrics the `alloy` service ships to Grafana Cloud
 * Prometheus (alloy/config.alloy — embedded postgres_exporter). Every series carries an
 * `env` label (APP_ENV: staging | production) added by Alloy's remote_write.
 */

/** Postgres's own databases, excluded from per-database sums — only the app database
 * (Railway's `railway`) is interesting. */
export const PG_APP_DATABASE_MATCHER = 'datname!~"template0|template1|postgres"'

/**
 * Label selector, e.g. `{env="production", datname!~"..."}`. `env` undefined (the "all
 * environments" filter) omits the env matcher; an empty selector `{}` is valid PromQL.
 */
export function pgSelector(env?: string, ...matchers: string[]): string {
  const parts = [env ? `env="${env}"` : '', ...matchers].filter(Boolean)
  return `{${parts.join(', ')}}`
}
