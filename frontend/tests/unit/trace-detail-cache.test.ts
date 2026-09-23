import { describe, it, expect, vi, beforeEach } from 'vitest'

const mockQueryTraceById = vi.fn()
vi.mock('@/lib/api/grafana', () => ({
  queryTraceById: (...args: any[]) => mockQueryTraceById(...args),
}))

beforeEach(async () => {
  vi.clearAllMocks()
  const { __resetTraceDetailCacheForTests } = await import('@/lib/api/trace-detail-cache')
  __resetTraceDetailCacheForTests()
})

describe('fetchTraceDetail', () => {
  it('calls queryTraceById once for a fresh trace ID', async () => {
    mockQueryTraceById.mockResolvedValue({ batches: [] })
    const { fetchTraceDetail } = await import('@/lib/api/trace-detail-cache')

    const result = await fetchTraceDetail('trace-a')

    expect(result).toEqual({ batches: [] })
    expect(mockQueryTraceById).toHaveBeenCalledTimes(1)
    expect(mockQueryTraceById).toHaveBeenCalledWith('trace-a')
  })

  it('serves a second call for the same trace ID from cache instead of refetching', async () => {
    mockQueryTraceById.mockResolvedValue({ batches: [] })
    const { fetchTraceDetail } = await import('@/lib/api/trace-detail-cache')

    await fetchTraceDetail('trace-b')
    await fetchTraceDetail('trace-b')

    expect(mockQueryTraceById).toHaveBeenCalledTimes(1)
  })

  it('dedupes two concurrent calls for the same in-flight trace ID into one request', async () => {
    let resolveFetch: (value: unknown) => void
    mockQueryTraceById.mockReturnValue(new Promise(resolve => { resolveFetch = resolve }))
    const { fetchTraceDetail } = await import('@/lib/api/trace-detail-cache')

    // TracesTable's toggleExpand and LogsTable's handleOpenTrace calling fetchTraceDetail for
    // the same trace at nearly the same moment — the exact scenario that motivated this
    // module — must not fire two separate requests.
    const p1 = fetchTraceDetail('trace-c')
    const p2 = fetchTraceDetail('trace-c')
    resolveFetch!({ batches: ['x'] })

    const [r1, r2] = await Promise.all([p1, p2])
    expect(r1).toEqual({ batches: ['x'] })
    expect(r2).toEqual({ batches: ['x'] })
    expect(mockQueryTraceById).toHaveBeenCalledTimes(1)
  })

  it('fetches independently for different trace IDs', async () => {
    mockQueryTraceById.mockResolvedValue({ batches: [] })
    const { fetchTraceDetail } = await import('@/lib/api/trace-detail-cache')

    await fetchTraceDetail('trace-d')
    await fetchTraceDetail('trace-e')

    expect(mockQueryTraceById).toHaveBeenCalledTimes(2)
  })

  it('retries on the next call after a failed fetch instead of caching the failure', async () => {
    mockQueryTraceById.mockRejectedValueOnce(new Error('network down'))
    mockQueryTraceById.mockResolvedValueOnce({ batches: [] })
    const { fetchTraceDetail } = await import('@/lib/api/trace-detail-cache')

    await expect(fetchTraceDetail('trace-f')).rejects.toThrow('network down')
    const result = await fetchTraceDetail('trace-f')

    expect(result).toEqual({ batches: [] })
    expect(mockQueryTraceById).toHaveBeenCalledTimes(2)
  })

  it('__resetTraceDetailCacheForTests clears cached entries so a later call refetches', async () => {
    mockQueryTraceById.mockResolvedValue({ batches: [] })
    const { fetchTraceDetail, __resetTraceDetailCacheForTests } = await import('@/lib/api/trace-detail-cache')

    await fetchTraceDetail('trace-g')
    __resetTraceDetailCacheForTests()
    await fetchTraceDetail('trace-g')

    expect(mockQueryTraceById).toHaveBeenCalledTimes(2)
  })
})
