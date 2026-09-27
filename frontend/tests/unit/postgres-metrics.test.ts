import { describe, it, expect } from 'vitest'
import { pgSelector, PG_APP_DATABASE_MATCHER } from '@/lib/postgres-metrics'

describe('pgSelector', () => {
  it('is an empty (valid) selector with no env and no matchers', () => {
    expect(pgSelector()).toBe('{}')
  })

  it('adds the env label when an environment is selected', () => {
    expect(pgSelector('production')).toBe('{env="production"}')
  })

  it('appends extra matchers after the env label', () => {
    expect(pgSelector('staging', PG_APP_DATABASE_MATCHER)).toBe(
      '{env="staging", datname!~"template0|template1|postgres"}',
    )
  })

  it('omits the env label for the "all environments" filter but keeps matchers', () => {
    expect(pgSelector(undefined, 'state="active"')).toBe('{state="active"}')
  })
})
