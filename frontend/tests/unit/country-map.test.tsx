import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, fireEvent, waitFor, act } from '@testing-library/react'
import type { PrometheusResponse } from '@/lib/api/grafana'

vi.mock('@/components/ui/tooltip', () => ({
  Tooltip: ({ children }: any) => <>{children}</>,
  TooltipTrigger: ({ children }: any) => <>{children}</>,
  TooltipContent: ({ children }: any) => <div data-testid="tooltip-content">{children}</div>,
}))

vi.mock('react-simple-maps', () => ({
  ComposableMap: ({ children }: any) => <div data-testid="composable-map">{children}</div>,
  ZoomableGroup: ({ children, center, zoom, onMoveEnd }: any) => (
    <div data-testid="zoomable-group" data-center={JSON.stringify(center)} data-zoom={zoom}>
      <button data-testid="trigger-move-end" onClick={() => onMoveEnd({ coordinates: [5, 10], zoom: 3 })} />
      {children}
    </div>
  ),
  Geographies: ({ geography, children }: any) => (
    <>
      {children({
        geographies: (geography?.features ?? []).map((f: any, i: number) => ({
          rsmKey: `geo-${i}`,
          id: f.id,
          properties: f.properties,
        })),
      })}
    </>
  ),
  Geography: ({ geography, onMouseEnter, onMouseMove, onMouseLeave, onClick, style }: any) => (
    <div
      data-testid={`geo-${geography.id}`}
      data-fill={style?.default?.fill}
      data-stroke={style?.default?.stroke}
      onMouseEnter={() => onMouseEnter?.({ clientX: 10, clientY: 20 })}
      onMouseMove={() => onMouseMove?.({ clientX: 15, clientY: 25 })}
      onMouseLeave={() => onMouseLeave?.()}
      onClick={() => onClick?.()}
    />
  ),
}))

vi.mock('d3-geo', () => ({
  geoCentroid: (f: any) => f.centroid ?? [0, 0],
}))

vi.mock('topojson-client', () => ({
  feature: (topology: any) => topology.__fc,
}))

const FAKE_TOPOLOGY = {
  objects: { countries: {} },
  __fc: {
    type: 'FeatureCollection',
    features: [
      { id: '840', properties: { name: 'United States of America' }, centroid: [-95, 39] },
      { id: '124', properties: { name: 'Canada' }, centroid: [-106, 56] },
    ],
  },
}

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

beforeEach(() => {
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ json: () => Promise.resolve(FAKE_TOPOLOGY) }))
})

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('extractCountryTotals', () => {
  it('returns an empty object for null/undefined input', async () => {
    const { extractCountryTotals } = await import('@/components/features/monitoring/country-map')
    expect(extractCountryTotals(null)).toEqual({})
    expect(extractCountryTotals(undefined)).toEqual({})
  })

  it('returns an empty object for an error response', async () => {
    const { extractCountryTotals } = await import('@/components/features/monitoring/country-map')
    expect(extractCountryTotals({ status: 'error', error: 'boom' } as any)).toEqual({})
  })

  it('returns an empty object when data is missing', async () => {
    const { extractCountryTotals } = await import('@/components/features/monitoring/country-map')
    expect(extractCountryTotals({ status: 'success' } as PrometheusResponse)).toEqual({})
  })

  it('sums values per country across the whole time range', async () => {
    const { extractCountryTotals } = await import('@/components/features/monitoring/country-map')
    const res: PrometheusResponse = {
      status: 'success',
      data: {
        resultType: 'matrix',
        result: [
          { metric: { geo_country: 'US' }, values: [[1, '3'], [2, '4']] },
          { metric: { geo_country: 'CA' }, values: [[1, '1']] },
        ],
      },
    }
    expect(extractCountryTotals(res)).toEqual({ US: 7, CA: 1 })
  })

  it('skips series with no geo_country label', async () => {
    const { extractCountryTotals } = await import('@/components/features/monitoring/country-map')
    const res: PrometheusResponse = {
      status: 'success',
      data: { resultType: 'matrix', result: [{ metric: {}, values: [[1, '5']] }] },
    }
    expect(extractCountryTotals(res)).toEqual({})
  })
})

describe('CountryMap rendering', () => {
  it('shows a skeleton while loading', async () => {
    const { CountryMap } = await import('@/components/features/monitoring/country-map')
    render(<CountryMap title="Requests by country" loading data={null} />)
    expect(screen.queryByTestId('composable-map')).toBeNull()
    // Let the topology fetch settle so no state update leaks past this test.
    await act(async () => { await Promise.resolve(); await Promise.resolve() })
  })

  it('shows a skeleton before the topology fetch resolves', async () => {
    const { CountryMap } = await import('@/components/features/monitoring/country-map')
    render(<CountryMap title="Requests by country" data={null} />)
    expect(screen.queryByTestId('composable-map')).toBeNull()
    await waitFor(() => expect(screen.getByTestId('composable-map')).toBeDefined())
  })

  it('renders the map with a shape per country once the topology loads', async () => {
    const { CountryMap } = await import('@/components/features/monitoring/country-map')
    render(<CountryMap title="Requests by country" data={makePrometheusResponse([{ code: 'US', count: 10 }])} />)

    await waitFor(() => expect(screen.getByTestId('composable-map')).toBeDefined())
    expect(screen.getByTestId('geo-840')).toBeDefined()
    expect(screen.getByTestId('geo-124')).toBeDefined()
  })

  it('renders the tooltip trigger when a tooltip prop is provided', async () => {
    const { CountryMap } = await import('@/components/features/monitoring/country-map')
    render(<CountryMap title="Requests by country" tooltip="Explains the chart" data={null} />)
    await waitFor(() => expect(screen.getByTestId('composable-map')).toBeDefined())
    expect(screen.getByText('Explains the chart')).toBeDefined()
  })

  it('colors a country with data differently from one without', async () => {
    const { CountryMap } = await import('@/components/features/monitoring/country-map')
    render(<CountryMap title="Requests by country" data={makePrometheusResponse([{ code: 'US', count: 10 }])} />)
    await waitFor(() => expect(screen.getByTestId('composable-map')).toBeDefined())

    const us = screen.getByTestId('geo-840')
    const ca = screen.getByTestId('geo-124')
    expect(us.dataset.fill).toContain('hsl(var(--primary)')
    expect(ca.dataset.fill).toBe('var(--muted)')
  })
})

describe('CountryMap hover tooltip', () => {
  it('shows a hover tooltip on mouse enter and clears it on mouse leave', async () => {
    const { CountryMap } = await import('@/components/features/monitoring/country-map')
    render(<CountryMap title="Requests by country" data={makePrometheusResponse([{ code: 'US', count: 10 }])} />)
    await waitFor(() => expect(screen.getByTestId('geo-840')).toBeDefined())

    fireEvent.mouseEnter(screen.getByTestId('geo-840'))
    expect(screen.getByText('United States of America')).toBeDefined()
    expect(screen.getByText('10')).toBeDefined()

    fireEvent.mouseLeave(screen.getByTestId('geo-840'))
    expect(screen.queryByText('United States of America')).toBeNull()
  })

  it('updates the tooltip position on mouse move', async () => {
    const { CountryMap } = await import('@/components/features/monitoring/country-map')
    render(<CountryMap title="Requests by country" data={makePrometheusResponse([{ code: 'US', count: 10 }])} />)
    await waitFor(() => expect(screen.getByTestId('geo-840')).toBeDefined())

    fireEvent.mouseEnter(screen.getByTestId('geo-840'))
    fireEvent.mouseMove(screen.getByTestId('geo-840'))
    expect(screen.getByText('United States of America').closest('div')?.style.left).toBe('27px')
  })

  it('does not show a count badge for a country with zero requests', async () => {
    const { CountryMap } = await import('@/components/features/monitoring/country-map')
    render(<CountryMap title="Requests by country" data={makePrometheusResponse([{ code: 'US', count: 10 }])} />)
    await waitFor(() => expect(screen.getByTestId('geo-124')).toBeDefined())

    fireEvent.mouseEnter(screen.getByTestId('geo-124'))
    expect(screen.getByText('Canada')).toBeDefined()
    expect(screen.queryByText('0')).toBeNull()
  })
})

describe('CountryMap selection', () => {
  it('calls onSelectCountry with the alpha-2 code when a shape is clicked', async () => {
    const { CountryMap } = await import('@/components/features/monitoring/country-map')
    const onSelectCountry = vi.fn()
    render(
      <CountryMap
        title="Requests by country"
        data={makePrometheusResponse([{ code: 'US', count: 10 }])}
        onSelectCountry={onSelectCountry}
      />
    )
    await waitFor(() => expect(screen.getByTestId('geo-840')).toBeDefined())

    fireEvent.click(screen.getByTestId('geo-840'))
    expect(onSelectCountry).toHaveBeenCalledWith('US')
  })

  it('outlines the currently selected country', async () => {
    const { CountryMap } = await import('@/components/features/monitoring/country-map')
    render(
      <CountryMap
        title="Requests by country"
        data={makePrometheusResponse([{ code: 'US', count: 10 }])}
        selectedCode="US"
      />
    )
    await waitFor(() => expect(screen.getByTestId('geo-840')).toBeDefined())

    expect(screen.getByTestId('geo-840').dataset.stroke).toBe('var(--primary)')
    expect(screen.getByTestId('geo-124').dataset.stroke).toBe('var(--border)')
  })

  it('pans and zooms to the selected country once its centroid is known', async () => {
    const { CountryMap } = await import('@/components/features/monitoring/country-map')
    render(
      <CountryMap
        title="Requests by country"
        data={makePrometheusResponse([{ code: 'US', count: 10 }])}
        selectedCode="US"
      />
    )
    await waitFor(() => {
      const group = screen.getByTestId('zoomable-group')
      expect(group.dataset.center).toBe(JSON.stringify([-95, 39]))
      expect(Number(group.dataset.zoom)).toBeGreaterThanOrEqual(4)
    })
  })
})

describe('CountryMap zoom controls', () => {
  it('zooms in and out via the +/- buttons', async () => {
    const { CountryMap } = await import('@/components/features/monitoring/country-map')
    render(<CountryMap title="Requests by country" data={null} />)
    await waitFor(() => expect(screen.getByTestId('zoomable-group')).toBeDefined())

    expect(screen.getByTestId('zoomable-group').dataset.zoom).toBe('1')

    fireEvent.click(screen.getByLabelText('Zoom in'))
    expect(screen.getByTestId('zoomable-group').dataset.zoom).toBe('2')

    fireEvent.click(screen.getByLabelText('Zoom out'))
    expect(screen.getByTestId('zoomable-group').dataset.zoom).toBe('1')
  })

  it('disables the zoom-out button at the minimum zoom level', async () => {
    const { CountryMap } = await import('@/components/features/monitoring/country-map')
    render(<CountryMap title="Requests by country" data={null} />)
    await waitFor(() => expect(screen.getByLabelText('Zoom out')).toBeDefined())
    expect(screen.getByLabelText('Zoom out')).toBeDisabled()
  })

  it('disables the zoom-in button at the maximum zoom level', async () => {
    const { CountryMap } = await import('@/components/features/monitoring/country-map')
    render(<CountryMap title="Requests by country" data={null} />)
    const zoomIn = await screen.findByLabelText('Zoom in')

    for (let i = 0; i < 10; i++) {
      fireEvent.click(zoomIn)
    }

    expect(screen.getByTestId('zoomable-group').dataset.zoom).toBe('8')
    expect(zoomIn).toBeDisabled()
  })

  it('updates center/zoom when the map itself is panned or zoomed', async () => {
    const { CountryMap } = await import('@/components/features/monitoring/country-map')
    render(<CountryMap title="Requests by country" data={null} />)
    await waitFor(() => expect(screen.getByTestId('trigger-move-end')).toBeDefined())

    fireEvent.click(screen.getByTestId('trigger-move-end'))

    const group = screen.getByTestId('zoomable-group')
    expect(group.dataset.center).toBe(JSON.stringify([5, 10]))
    expect(group.dataset.zoom).toBe('3')
  })
})
