import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import type { PrometheusResponse } from '@/lib/api/grafana'
import { CountryTable } from '@/components/features/monitoring/country-table'

function makePrometheusResponse(rows: Array<{ code: string; count: number }>): PrometheusResponse {
  return {
    status: 'success',
    data: {
      resultType: 'matrix',
      result: rows.map(r => ({
        metric: { geo_country: r.code },
        values: [[1700000000, String(r.count)]],
      })),
    },
  }
}

describe('CountryTable', () => {
  it('shows "No data" when there are no rows', () => {
    render(<CountryTable title="Requests by country" data={null} />)
    expect(screen.getByText('No data')).toBeDefined()
  })

  it('renders rows sorted by request count descending', () => {
    render(
      <CountryTable
        title="Requests by country"
        data={makePrometheusResponse([
          { code: 'CA', count: 5 },
          { code: 'US', count: 20 },
        ])}
      />
    )
    const rows = screen.getAllByRole('row').filter(r => r.querySelector('td'))
    expect(rows[0].textContent).toContain('United States of America')
    expect(rows[1].textContent).toContain('Canada')
  })

  it('falls back to the raw code when no display name is known', () => {
    render(<CountryTable title="Requests by country" data={makePrometheusResponse([{ code: 'ZZ', count: 3 }])} />)
    expect(screen.getByText('ZZ')).toBeDefined()
  })

  it('formats the count and computes each row\'s share of the total', () => {
    render(
      <CountryTable
        title="Requests by country"
        data={makePrometheusResponse([
          { code: 'US', count: 30 },
          { code: 'CA', count: 10 },
        ])}
      />
    )
    expect(screen.getByText('30')).toBeDefined()
    expect(screen.getByText('75.0%')).toBeDefined()
    expect(screen.getByText('25.0%')).toBeDefined()
  })

  it('calls onSelectCountry when a row is clicked, and clears selection on a repeat click', () => {
    const onSelectCountry = vi.fn()
    render(
      <CountryTable
        title="Requests by country"
        data={makePrometheusResponse([{ code: 'US', count: 10 }])}
        onSelectCountry={onSelectCountry}
      />
    )
    const row = screen.getByText('United States of America').closest('tr')!
    fireEvent.click(row)
    expect(onSelectCountry).toHaveBeenCalledWith('US')
  })

  it('clicking the already-selected row deselects it', () => {
    const onSelectCountry = vi.fn()
    render(
      <CountryTable
        title="Requests by country"
        data={makePrometheusResponse([{ code: 'US', count: 10 }])}
        selectedCode="US"
        onSelectCountry={onSelectCountry}
      />
    )
    const row = screen.getByText('United States of America').closest('tr')!
    fireEvent.click(row)
    expect(onSelectCountry).toHaveBeenCalledWith(null)
  })
})
