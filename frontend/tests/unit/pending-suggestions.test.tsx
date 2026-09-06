import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import type { SuggestionOut } from '@/lib/api/tags'

vi.mock('@/lib/api/tags', () => ({
  approveSuggestion: vi.fn(),
  approveSuggestionsBatch: vi.fn(),
  rejectSuggestion: vi.fn(),
}))

vi.mock('@/lib/providers', () => ({
  useI18n: () => ({
    locale: 'en',
    t: (key: string, params?: Record<string, any>) => {
      const map: Record<string, string> = {
        'tags.pendingMergeSuggestions': `${params?.count ?? 0} pending suggestions`,
        'tags.merge': 'Merge',
        'tags.keepBoth': 'Keep Both',
        'tags.mergeAll': 'Merge All',
        'tags.similar': `Similar ${params?.pct ?? 0}%`,
        'tags.confirmMergeAll': `Merge all ${params?.count ?? 0}?`,
      }
      return map[key] ?? key
    },
  }),
}))

const suggestions: SuggestionOut[] = [
  {
    id: 's1',
    new_tag_id: 't1',
    new_tag_name: 'ai',
    existing_tag_id: 't2',
    existing_tag_name: 'AI',
    group_name: 'research',
    similarity_score: 0.92,
    article_id: null,
  },
  {
    id: 's2',
    new_tag_id: 't3',
    new_tag_name: 'ml',
    existing_tag_id: 't4',
    existing_tag_name: 'ML',
    group_name: 'research',
    similarity_score: 0.85,
    article_id: null,
  },
]

describe('PendingSuggestions', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    // default: confirm() returns true
    vi.stubGlobal('confirm', () => true)
  })

  it('renders nothing when suggestions list is empty', async () => {
    const { PendingSuggestions } = await import('@/components/features/tags/pending-suggestions')
    const { container } = render(
      <PendingSuggestions suggestions={[]} token="tok" onResolved={vi.fn()} onBatchResolved={vi.fn()} />
    )
    expect(container.innerHTML).toBe('')
  })

  it('renders suggestion count and items', async () => {
    const { PendingSuggestions } = await import('@/components/features/tags/pending-suggestions')
    const { container } = render(
      <PendingSuggestions suggestions={suggestions} token="tok" onResolved={vi.fn()} onBatchResolved={vi.fn()} />
    )
    expect(screen.getByText('2 pending suggestions')).toBeInTheDocument()
    // The component uses &ldquo; and &rdquo; which render as curly quotes
    expect(container.innerHTML).toContain('ai')
    expect(container.innerHTML).toContain('AI')
  })

  it('calls approveSuggestion and onResolved when Merge clicked', async () => {
    const { approveSuggestion } = await import('@/lib/api/tags')
    const mockedApprove = vi.mocked(approveSuggestion)
    mockedApprove.mockResolvedValue(undefined)
    const onResolved = vi.fn()
    const { PendingSuggestions } = await import('@/components/features/tags/pending-suggestions')
    render(
      <PendingSuggestions suggestions={suggestions} token="tok" onResolved={onResolved} onBatchResolved={vi.fn()} />
    )
    const mergeButtons = screen.getAllByText('Merge')
    fireEvent.click(mergeButtons[0])
    await waitFor(() => {
      expect(mockedApprove).toHaveBeenCalledWith('s1', 'tok')
      expect(onResolved).toHaveBeenCalledWith('s1')
    })
  })

  it('calls rejectSuggestion and onResolved when Keep Both clicked', async () => {
    const { rejectSuggestion } = await import('@/lib/api/tags')
    const mockedReject = vi.mocked(rejectSuggestion)
    mockedReject.mockResolvedValue(undefined)
    const onResolved = vi.fn()
    const { PendingSuggestions } = await import('@/components/features/tags/pending-suggestions')
    render(
      <PendingSuggestions suggestions={suggestions} token="tok" onResolved={onResolved} onBatchResolved={vi.fn()} />
    )
    const keepButtons = screen.getAllByText('Keep Both')
    fireEvent.click(keepButtons[0])
    await waitFor(() => {
      expect(mockedReject).toHaveBeenCalledWith('s1', 'tok')
      expect(onResolved).toHaveBeenCalledWith('s1')
    })
  })

  it('calls approveSuggestionsBatch once and reports succeeded ids via onBatchResolved (not per-id onResolved)', async () => {
    const { approveSuggestionsBatch } = await import('@/lib/api/tags')
    const mockedBatch = vi.mocked(approveSuggestionsBatch)
    mockedBatch.mockResolvedValue({ succeeded: ['s1', 's2'], failed: [] })
    const onResolved = vi.fn()
    const onBatchResolved = vi.fn()
    const { PendingSuggestions } = await import('@/components/features/tags/pending-suggestions')
    render(
      <PendingSuggestions
        suggestions={suggestions} token="tok" onResolved={onResolved} onBatchResolved={onBatchResolved}
      />
    )
    fireEvent.click(screen.getByText('Merge All'))
    await waitFor(() => {
      expect(mockedBatch).toHaveBeenCalledTimes(1)
      expect(mockedBatch).toHaveBeenCalledWith(['s1', 's2'], 'tok')
      expect(onBatchResolved).toHaveBeenCalledTimes(1)
      expect(onBatchResolved).toHaveBeenCalledWith(['s1', 's2'])
      expect(onResolved).not.toHaveBeenCalled()
    })
  })

  it('only reports suggestions the batch actually succeeded on, leaving failures for retry', async () => {
    const { approveSuggestionsBatch } = await import('@/lib/api/tags')
    const mockedBatch = vi.mocked(approveSuggestionsBatch)
    mockedBatch.mockResolvedValue({
      succeeded: ['s1'],
      failed: [{ suggestion_id: 's2', error: 'Suggestion not found' }],
    })
    const onBatchResolved = vi.fn()
    const { PendingSuggestions } = await import('@/components/features/tags/pending-suggestions')
    render(
      <PendingSuggestions
        suggestions={suggestions} token="tok" onResolved={vi.fn()} onBatchResolved={onBatchResolved}
      />
    )
    fireEvent.click(screen.getByText('Merge All'))
    await waitFor(() => {
      expect(onBatchResolved).toHaveBeenCalledTimes(1)
      expect(onBatchResolved).toHaveBeenCalledWith(['s1'])
    })
  })

  it('toggles collapse on header click', async () => {
    const { PendingSuggestions } = await import('@/components/features/tags/pending-suggestions')
    render(
      <PendingSuggestions suggestions={suggestions} token="tok" onResolved={vi.fn()} onBatchResolved={vi.fn()} />
    )
    const header = screen.getByText('2 pending suggestions').closest('button')!
    // Initially expanded — items visible
    expect(screen.getAllByText('Merge').length).toBeGreaterThan(0)
    fireEvent.click(header)
    // After collapse — items should be hidden
    expect(screen.queryByText('Merge')).not.toBeInTheDocument()
  })
})
