import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import type { PrometheusResponse } from '@/lib/api/grafana'

const queryMetricsBatch = vi.fn()
const fetchQueryTexts = vi.fn()

vi.mock('@/lib/api/grafana', () => ({
  queryMetricsBatch: (...args: unknown[]) => queryMetricsBatch(...args),
  fetchQueryTexts: (...args: unknown[]) => fetchQueryTexts(...args),
}))

vi.mock('@/lib/providers', () => ({
  useI18n: () => ({
    t: (k: string, p?: Record<string, string>) => (p?.id ? `${k}:${p.id}` : k),
  }),
}))

vi.mock('@/components/ui/tooltip', () => ({
  Tooltip: ({ children }: any) => <>{children}</>,
  TooltipTrigger: ({ children }: any) => <>{children}</>,
  TooltipContent: ({ children }: any) => <span>{children}</span>,
}))

import { DatabaseTables } from '@/components/features/monitoring/database-tables'

function vec(series: { metric: Record<string, string>; value: number }[]): PrometheusResponse {
  return {
    status: 'success',
    data: {
      resultType: 'matrix',
      result: series.map(s => ({ metric: s.metric, values: [[1700000000, String(s.value)]] })),
    },
  }
}

const TIME = vec([
  { metric: { queryid: 'q-fast' }, value: 2 },
  { metric: { queryid: 'q-slow' }, value: 30 },
  { metric: { queryid: 'q-nocalls' }, value: 1 },
])
const CALLS = vec([
  { metric: { queryid: 'q-fast' }, value: 1000 },
  { metric: { queryid: 'q-slow' }, value: 3000 },
])
const ROWS = vec([{ metric: { queryid: 'q-slow' }, value: 12345 }])
const UNUSED = vec([
  { metric: { schemaname: 'core', relname: 'articles', indexrelname: 'ix_small' }, value: 4096 },
  { metric: { schemaname: 'vectors', relname: 'chunks', indexrelname: 'ix_huge' }, value: 2 * 1024 ** 3 },
  { metric: { schemaname: 'core', relname: 'tags', indexrelname: 'ix_mid' }, value: 5 * 1024 ** 2 },
])

const props = {
  startSec: 1000, endSec: 2000, env: 'staging', rangeVec: '24h', rangeLabel: '24h', enabled: true,
}

function rowTexts(container: HTMLElement): string[][] {
  return Array.from(container.querySelectorAll('tbody tr')).map(tr =>
    Array.from(tr.querySelectorAll('td')).map(td => td.textContent ?? ''),
  )
}

beforeEach(() => {
  queryMetricsBatch.mockReset()
  fetchQueryTexts.mockReset()
})

describe('DatabaseTables', () => {
  it('renders top queries by total time and unused indexes by size', async () => {
    queryMetricsBatch.mockResolvedValue([TIME, CALLS, ROWS, UNUSED])
    fetchQueryTexts.mockResolvedValue({
      available: true,
      items: [{ queryid: 'q-slow', query: 'SELECT * FROM core.articles' }],
    })

    const { container } = render(<DatabaseTables {...props} />)

    await waitFor(() => expect(screen.getByText('SELECT * FROM core.articles')).toBeDefined())
    // Texts are looked up for every top query, slowest first.
    expect(fetchQueryTexts).toHaveBeenCalledWith(['q-slow', 'q-fast', 'q-nocalls'])

    const rows = rowTexts(container)
    // Top queries: text, calls, total, mean, rows.
    expect(rows[0]).toEqual(['SELECT * FROM core.articles', (3000).toLocaleString(), '30.0 s', '10.0 ms', (12345).toLocaleString()])
    expect(rows[1]).toEqual(['admin.dbQueryTextMissing:q-fast', (1000).toLocaleString(), '2.0 s', '2.0 ms', '0'])
    // No calls series for this queryid → 0 calls, no mean.
    expect(rows[2]).toEqual(['admin.dbQueryTextMissing:q-nocalls', '0', '1.0 s', '—', '0'])
    // Unused indexes, largest first, formatted GB / MB / kB.
    expect(rows[3]).toEqual(['ix_huge', 'vectors.chunks', '2.0 GB'])
    expect(rows[4]).toEqual(['ix_mid', 'core.tags', '5.0 MB'])
    expect(rows[5]).toEqual(['ix_small', 'core.articles', '4 kB'])
  })

  it('scopes every query to the environment and evaluates at the window end', async () => {
    queryMetricsBatch.mockResolvedValue([vec([]), vec([]), vec([]), vec([])])
    fetchQueryTexts.mockResolvedValue({ available: true, items: [] })

    render(<DatabaseTables {...props} />)

    await waitFor(() => expect(queryMetricsBatch).toHaveBeenCalledTimes(1))
    const items = queryMetricsBatch.mock.calls[0][0] as { query: string; start: number; end: number }[]
    expect(items).toHaveLength(4)
    for (const item of items) {
      expect(item.query).toContain('env="staging"')
      expect(item.query).toContain('[24h]')
      expect(item.start).toBe(2000)
      expect(item.end).toBe(2000)
    }
  })

  it('says the query text is unavailable when the lookup endpoint is', async () => {
    queryMetricsBatch.mockResolvedValue([vec([{ metric: { queryid: 'q1' }, value: 1 }]), vec([]), vec([]), vec([])])
    fetchQueryTexts.mockResolvedValue({ available: false, items: [] })

    render(<DatabaseTables {...props} />)

    await waitFor(() => expect(screen.getByText('admin.dbQueryTextUnavailable:q1')).toBeDefined())
  })

  it('shows the empty placeholders when nothing comes back', async () => {
    queryMetricsBatch.mockResolvedValue([vec([]), vec([]), vec([]), vec([])])
    fetchQueryTexts.mockResolvedValue({ available: true, items: [] })

    render(<DatabaseTables {...props} />)

    await waitFor(() => expect(screen.getByText('admin.dbNoData')).toBeDefined())
    expect(screen.getByText('admin.dbNoUnusedIndexes')).toBeDefined()
  })

  it('treats non-success or data-less responses as empty', async () => {
    // No `error` key (that one fails the whole load — see the next test), just a non-success status.
    const errorStatus: PrometheusResponse = { status: 'error' }
    const noData: PrometheusResponse = { status: 'success' }
    const noValues: PrometheusResponse = {
      status: 'success', data: { resultType: 'matrix', result: [{ metric: { queryid: 'q' }, values: [] }] },
    }
    queryMetricsBatch.mockResolvedValue([noValues, errorStatus, noData, noData])
    fetchQueryTexts.mockResolvedValue({ available: true, items: [] })

    render(<DatabaseTables {...props} />)

    await waitFor(() => expect(screen.getByText('admin.dbNoData')).toBeDefined())
    expect(fetchQueryTexts).toHaveBeenCalledWith([])
  })

  it('shows the load-failed message when any batch entry errored', async () => {
    queryMetricsBatch.mockResolvedValue([vec([]), { error: 'not_configured' }, vec([]), vec([])])

    render(<DatabaseTables {...props} />)

    await waitFor(() => expect(screen.getAllByText('admin.dbTableLoadFailed')).toHaveLength(2))
    expect(fetchQueryTexts).not.toHaveBeenCalled()
  })

  it('shows the load-failed message when the batch request throws', async () => {
    queryMetricsBatch.mockRejectedValue(new Error('network'))

    render(<DatabaseTables {...props} />)

    await waitFor(() => expect(screen.getAllByText('admin.dbTableLoadFailed')).toHaveLength(2))
  })

  it('does not fetch while disabled', () => {
    render(<DatabaseTables {...props} enabled={false} />)

    expect(queryMetricsBatch).not.toHaveBeenCalled()
  })

  it('fetches once per window/environment, not on every re-render', async () => {
    queryMetricsBatch.mockResolvedValue([vec([]), vec([]), vec([]), vec([])])
    fetchQueryTexts.mockResolvedValue({ available: true, items: [] })

    const { rerender } = render(<DatabaseTables {...props} />)
    await waitFor(() => expect(screen.getByText('admin.dbNoData')).toBeDefined())

    rerender(<DatabaseTables {...props} rangeLabel="changed label" />)
    rerender(<DatabaseTables {...props} enabled={false} />)
    rerender(<DatabaseTables {...props} />)
    expect(queryMetricsBatch).toHaveBeenCalledTimes(1)

    rerender(<DatabaseTables {...props} endSec={3000} />)
    await waitFor(() => expect(queryMetricsBatch).toHaveBeenCalledTimes(2))
  })

  it('refetches after a load was cancelled mid-flight instead of spinning forever', async () => {
    let resolveFirst: (v: PrometheusResponse[]) => void = () => {}
    queryMetricsBatch
      .mockImplementationOnce(() => new Promise(r => { resolveFirst = r }))
      .mockResolvedValue([vec([{ metric: { queryid: 'q1' }, value: 1 }]), vec([]), vec([]), vec([])])
    fetchQueryTexts.mockResolvedValue({ available: true, items: [{ queryid: 'q1', query: 'SELECT 1' }] })

    const { rerender } = render(<DatabaseTables {...props} />)
    // Leave the tab before the first batch returns, then come back.
    rerender(<DatabaseTables {...props} enabled={false} />)
    rerender(<DatabaseTables {...props} />)

    await waitFor(() => expect(screen.getByText('SELECT 1')).toBeDefined())
    expect(queryMetricsBatch).toHaveBeenCalledTimes(2)

    // The stale first response landing late must not overwrite anything.
    resolveFirst([vec([]), vec([]), vec([]), vec([])])
    await Promise.resolve()
    expect(screen.getByText('SELECT 1')).toBeDefined()
    expect(fetchQueryTexts).toHaveBeenCalledTimes(1)
  })

  it('ignores a text lookup that lands after the load was cancelled', async () => {
    let resolveTexts: (v: unknown) => void = () => {}
    queryMetricsBatch.mockResolvedValue([vec([{ metric: { queryid: 'q1' }, value: 1 }]), vec([]), vec([]), vec([])])
    fetchQueryTexts
      .mockImplementationOnce(() => new Promise(r => { resolveTexts = r }))
      .mockResolvedValue({ available: true, items: [{ queryid: 'q1', query: 'SELECT fresh' }] })

    const { rerender } = render(<DatabaseTables {...props} />)
    await waitFor(() => expect(fetchQueryTexts).toHaveBeenCalledTimes(1))
    rerender(<DatabaseTables {...props} endSec={3000} />)
    await waitFor(() => expect(screen.getByText('SELECT fresh')).toBeDefined())

    resolveTexts({ available: true, items: [{ queryid: 'q1', query: 'SELECT stale' }] })
    await Promise.resolve()
    expect(screen.queryByText('SELECT stale')).toBeNull()
  })
})
