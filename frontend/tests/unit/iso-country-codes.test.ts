import { describe, it, expect } from 'vitest'
import { ISO_ALPHA2_TO_NUMERIC, ISO_NUMERIC_TO_ALPHA2, ISO_ALPHA2_TO_NAME } from '@/lib/iso-country-codes'

describe('ISO_ALPHA2_TO_NUMERIC', () => {
  it('maps known alpha-2 codes to their ISO 3166-1 numeric id', () => {
    expect(ISO_ALPHA2_TO_NUMERIC.US).toBe('840')
    expect(ISO_ALPHA2_TO_NUMERIC.CA).toBe('124')
    expect(ISO_ALPHA2_TO_NUMERIC.TW).toBe('158')
  })
})

describe('ISO_NUMERIC_TO_ALPHA2', () => {
  it('is the exact reverse of ISO_ALPHA2_TO_NUMERIC', () => {
    expect(ISO_NUMERIC_TO_ALPHA2['840']).toBe('US')
    expect(ISO_NUMERIC_TO_ALPHA2['124']).toBe('CA')
    expect(Object.keys(ISO_NUMERIC_TO_ALPHA2).length).toBe(Object.keys(ISO_ALPHA2_TO_NUMERIC).length)
  })

  it('round-trips every alpha-2 code through its numeric id', () => {
    for (const [alpha2, numeric] of Object.entries(ISO_ALPHA2_TO_NUMERIC)) {
      expect(ISO_NUMERIC_TO_ALPHA2[numeric]).toBe(alpha2)
    }
  })
})

describe('ISO_ALPHA2_TO_NAME', () => {
  it('has a display name for known alpha-2 codes', () => {
    expect(ISO_ALPHA2_TO_NAME.US).toBe('United States of America')
    expect(ISO_ALPHA2_TO_NAME.TW).toBe('Taiwan')
  })

  it('has a name entry for every code in ISO_ALPHA2_TO_NUMERIC', () => {
    for (const alpha2 of Object.keys(ISO_ALPHA2_TO_NUMERIC)) {
      expect(ISO_ALPHA2_TO_NAME[alpha2]).toBeDefined()
    }
  })
})
