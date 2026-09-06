import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import type { PrometheusResponse } from '@/lib/api/grafana'
import { CountryTable } from '@/components/features/monitoring/country-table'

function makePrometheusResponse(rows: Array<{ code: string; count: number; role?: string }>): PrometheusResponse {
  return {
    status: 'success',
    data: {
      resultType: 'matrix',
      result: rows.map(r => ({
        metric: { geo_country: r.code, ...(r.role ? { user_role: r.role } : {}) },
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

  it('buckets a series with no user_role label as "unknown" in the role-mix bar', () => {
    // The chart this table's data comes from always sets user_role (backend/middleware/logging.py
    // never omits it), so this is a defensive fallback rather than a real-world case — but
    // extractCountryRoleTotals must not silently drop the count if it ever happens.
    render(<CountryTable title="Requests by country" data={makePrometheusResponse([{ code: 'US', count: 10 }])} />)
    const row = screen.getByText('United States of America').closest('tr')!
    const bar = row.querySelector('[title*="unknown"]')
    expect(bar).not.toBeNull()
    expect(bar!.getAttribute('title')).toContain('unknown: 10 (100%)')
  })

  it('renders a role-mix bar with the per-role breakdown in its title when role data is present', () => {
    render(
      <CountryTable
        title="Requests by country"
        data={makePrometheusResponse([
          { code: 'US', count: 8, role: 'guest' },
          { code: 'US', count: 2, role: 'admin' },
        ])}
      />
    )
    const row = screen.getByText('United States of America').closest('tr')!
    const bar = row.querySelector('[title*="guest"]')
    expect(bar).not.toBeNull()
    expect(bar!.getAttribute('title')).toContain('admin: 2 (20%)')
    expect(bar!.getAttribute('title')).toContain('guest: 8 (80%)')
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
