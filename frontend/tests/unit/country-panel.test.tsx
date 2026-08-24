import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'

vi.mock('@/components/features/monitoring/country-map', () => ({
  CountryMap: ({ title, selectedCode, onSelectCountry }: any) => (
    <div data-testid="country-map" data-selected={selectedCode ?? ''}>
      {title}
      <button data-testid="map-select-us" onClick={() => onSelectCountry('US')} />
    </div>
  ),
}))

vi.mock('@/components/features/monitoring/country-table', () => ({
  CountryTable: ({ title, selectedCode, onSelectCountry }: any) => (
    <div data-testid="country-table" data-selected={selectedCode ?? ''}>
      {title}
      <button data-testid="table-select-ca" onClick={() => onSelectCountry('CA')} />
    </div>
  ),
}))

describe('CountryPanel', () => {
  it('renders both the map and the table with their own titles', async () => {
    const { CountryPanel } = await import('@/components/features/monitoring/country-panel')
    render(<CountryPanel mapTitle="Map title" tableTitle="Table title" data={null} />)

    expect(screen.getByTestId('country-map').textContent).toContain('Map title')
    expect(screen.getByTestId('country-table').textContent).toContain('Table title')
  })

  it('shares selection state: selecting on the map updates the table', async () => {
    const { CountryPanel } = await import('@/components/features/monitoring/country-panel')
    render(<CountryPanel mapTitle="Map title" tableTitle="Table title" data={null} />)

    fireEvent.click(screen.getByTestId('map-select-us'))

    expect(screen.getByTestId('country-map').dataset.selected).toBe('US')
    expect(screen.getByTestId('country-table').dataset.selected).toBe('US')
  })

  it('shares selection state: selecting on the table updates the map', async () => {
    const { CountryPanel } = await import('@/components/features/monitoring/country-panel')
    render(<CountryPanel mapTitle="Map title" tableTitle="Table title" data={null} />)

    fireEvent.click(screen.getByTestId('table-select-ca'))

    expect(screen.getByTestId('country-map').dataset.selected).toBe('CA')
    expect(screen.getByTestId('country-table').dataset.selected).toBe('CA')
  })
})
