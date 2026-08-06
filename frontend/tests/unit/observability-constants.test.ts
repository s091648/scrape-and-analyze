import { describe, it, expect } from 'vitest'
import {
  lokiStreamSelector,
  traceQLServiceMatch,
  promqlIncrease,
  promqlEnvMatcher,
  SERVICE_NAME,
  LokiLabel,
  LokiAppValue,
  TraceQLResource,
  MetricLabelKey,
} from '@/lib/observability-constants'

describe('lokiStreamSelector', () => {
  it('returns base selector with just app label', () => {
    expect(lokiStreamSelector()).toBe(`{${LokiLabel.APP}="${LokiAppValue.SCRAPER}"}`)
  })

  it('appends extra labels when provided', () => {
    const result = lokiStreamSelector({ env: 'production', level: 'error' })
    expect(result).toContain(`${LokiLabel.APP}="${LokiAppValue.SCRAPER}"`)
    expect(result).toContain('env="production"')
    expect(result).toContain('level="error"')
  })

  it('includes single extra label', () => {
    const result = lokiStreamSelector({ env: 'staging' })
    expect(result).toBe(`{${LokiLabel.APP}="${LokiAppValue.SCRAPER}", env="staging"}`)
  })
})

describe('traceQLServiceMatch', () => {
  it('returns match without env filter clause when env is undefined', () => {
    const result = traceQLServiceMatch()
    expect(result).toContain(`${TraceQLResource.SERVICE_NAME} = "${SERVICE_NAME}"`)
    // select() always includes the env attribute, but the filter (= "...") is absent
    expect(result).not.toContain(`${TraceQLResource.DEPLOYMENT_ENVIRONMENT} = "`)
    expect(result).toContain(`select(${TraceQLResource.DEPLOYMENT_ENVIRONMENT})`)
  })

  it('includes env filter clause when env is provided', () => {
    const result = traceQLServiceMatch('production')
    expect(result).toContain(`${TraceQLResource.SERVICE_NAME} = "${SERVICE_NAME}"`)
    expect(result).toContain(`${TraceQLResource.DEPLOYMENT_ENVIRONMENT} = "production"`)
  })

  it('includes env clause for staging env', () => {
    const result = traceQLServiceMatch('staging')
    expect(result).toContain(`${TraceQLResource.DEPLOYMENT_ENVIRONMENT} = "staging"`)
  })

  it('uses the provided serviceName override instead of SERVICE_NAME', () => {
    const result = traceQLServiceMatch(undefined, 'scrape-analyzer-backend')
    expect(result).toContain(`${TraceQLResource.SERVICE_NAME} = "scrape-analyzer-backend"`)
    expect(result).not.toContain(`${TraceQLResource.SERVICE_NAME} = "${SERVICE_NAME}"`)
  })
})

describe('promqlIncrease', () => {
  it('returns increase expression without by clause', () => {
    const result = promqlIncrease('scraper_runs_total', '24h')
    expect(result).toBe('increase(scraper_runs_total[24h])')
  })

  it('appends by clause when byLabel is provided', () => {
    const result = promqlIncrease('scraper_articles_found_total', '1h', 'source')
    expect(result).toBe('increase(scraper_articles_found_total[1h]) by (source)')
  })

  it('works with different metrics and ranges', () => {
    const result = promqlIncrease('scraper_errors_total', '7d', 'deployment_environment')
    expect(result).toBe('increase(scraper_errors_total[7d]) by (deployment_environment)')
  })
})

describe('promqlEnvMatcher', () => {
  it('returns empty string when env is undefined', () => {
    expect(promqlEnvMatcher()).toBe('')
  })

  it('returns empty string when env is empty string', () => {
    expect(promqlEnvMatcher('')).toBe('')
  })

  it('returns label matcher when env is provided', () => {
    const result = promqlEnvMatcher('production')
    expect(result).toBe(`{${MetricLabelKey.DEPLOYMENT_ENVIRONMENT}="production"}`)
  })

  it('works with local env', () => {
    const result = promqlEnvMatcher('local')
    expect(result).toBe(`{${MetricLabelKey.DEPLOYMENT_ENVIRONMENT}="local"}`)
  })
})
