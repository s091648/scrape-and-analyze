import { describe, it, expect, vi, beforeEach, afterEach, beforeAll } from 'vitest'
import { render, screen, fireEvent, waitFor, act } from '@testing-library/react'
import { fetchArticleFilterOriginalSources } from '@/lib/api/articles'
import { fetchTagGroups } from '@/lib/api/tags'
import type { TagGroupOut } from '@/lib/api/tags'
import type { ComponentType } from 'react'

vi.mock('@/lib/api/articles', () => ({
  fetchArticleFilterOriginalSources: vi.fn(),
}))

vi.mock('@/lib/api/tags', () => ({
  fetchTagGroups: vi.fn(),
}))

vi.mock('@/lib/api/source-categories', () => ({
  fetchSourceCategories: vi.fn().mockResolvedValue({ aggregator: [], scraper: [] }),
}))

let mockSessionStatus = 'unauthenticated'
vi.mock('next-auth/react', () => ({
  useSession: () => ({ status: mockSessionStatus }),
}))

vi.mock('@/lib/providers', () => ({
  useI18n: () => ({
    locale: 'en',
    t: (key: string) => {
      const map: Record<string, string> = {
        'filterBar.filters': 'Filters',
        'filterBar.source': 'Source',
        'filterBar.tag': 'Tag',
        'filterBar.published': 'Published',
        'filterBar.scraped': 'Scraped',
        'filterBar.search': 'Search',
        'filterBar.any': 'Any',
        'filterBar.after': 'After',
        'filterBar.before': 'Before',
        'filterBar.range': 'Range',
        'filterBar.recent': 'Recent',
        'filterBar.from': 'From',
        'filterBar.to': 'To',
        'filterBar.days': 'days',
        'filterBar.clear': 'Clear',
        'filterBar.apply': 'Apply',
        'filterBar.noTagsFound': 'No tags found',
        'filterBar.favoritesOnly': 'Favorites Only',
      }
      return map[key] ?? key
    },
  }),
  useTopic: () => ({ selectedTopicId: 'topic-1' }),
}))

const mockTagGroups: TagGroupOut[] = [
  {
    id: 'g1', name: 'research', display_name: 'Research Methods',
    description: null, color_hex: null, topic_id: 'topic-1',
    tags: [{ id: 't1', name: 'AI', article_count: 5 }],
    similar_groups: [],
  },
]

const defaultProps = {
  aggregators: [],
  originalSources: [],
  tags: [],
  tagGroups: [],
  publishedAfter: '',
  publishedBefore: '',
  scrapedAfter: '',
  scrapedBefore: '',
  activeFilterCount: 0,
  onApply: vi.fn(),
}

function setupApiMock(sourceOptions = ['arxiv', 'ACM Digital Library'], tagGroups = mockTagGroups) {
  vi.mocked(fetchArticleFilterOriginalSources).mockResolvedValue(sourceOptions)
  vi.mocked(fetchTagGroups).mockResolvedValue(tagGroups)
}

// eslint-disable-next-line @typescript-eslint/no-explicit-any
let FilterBar: ComponentType<any>

beforeAll(async () => {
  const module = await import('@/components/features/articles/filter-bar')
  FilterBar = module.FilterBar as any
})

describe('FilterBar', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockSessionStatus = 'unauthenticated'
    setupApiMock()
  })

  it('"Filters" toggle button is always rendered', async () => {
    render(<FilterBar {...defaultProps} />)
    await waitFor(() => {
      expect(screen.getByRole('button', { name: /filters/i })).toBeInTheDocument()
    })
  })

  it('clicking "Filters" reveals Source and Tag popover triggers', async () => {
    render(<FilterBar {...defaultProps} />)
    fireEvent.click(screen.getByRole('button', { name: /filters/i }))
    expect(screen.getByRole('button', { name: /source/i })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /tag/i })).toBeInTheDocument()
  })

  it('"Clear" button is hidden when activeFilterCount is 0', async () => {
    render(<FilterBar {...defaultProps} />)
    fireEvent.click(screen.getByRole('button', { name: /filters/i }))
    expect(screen.queryByRole('button', { name: /clear/i })).not.toBeInTheDocument()
  })

  it('"Clear" button is visible when activeFilterCount > 0', async () => {
    render(<FilterBar {...defaultProps} activeFilterCount={2} />)
    fireEvent.click(screen.getByRole('button', { name: /filters/i }))
    expect(screen.getByRole('button', { name: /clear/i })).toBeInTheDocument()
  })

  it('has no separate "Apply" button — filters apply themselves', async () => {
    render(<FilterBar {...defaultProps} />)
    fireEvent.click(screen.getByRole('button', { name: /filters/i }))
    expect(screen.queryByRole('button', { name: /^apply$/i })).not.toBeInTheDocument()
  })

  it('"Clear" resets filters and calls onApply with empty values', async () => {
    const onApply = vi.fn()
    render(<FilterBar {...defaultProps} originalSources={['arxiv']} onApply={onApply} activeFilterCount={1} />)
    fireEvent.click(screen.getByRole('button', { name: /filters/i }))
    fireEvent.click(screen.getByRole('button', { name: /clear/i }))
    expect(onApply).toHaveBeenCalledWith({
      aggregator: [], original_source: [], tag: [], tag_group: [], published_after: '', published_before: '', scraped_after: '', scraped_before: '',
    })
  })

  it('fetches original source options and tag groups on mount', async () => {
    render(<FilterBar {...defaultProps} />)
    await waitFor(() => {
      expect(fetchArticleFilterOriginalSources).toHaveBeenCalledWith('topic-1', 'en')
      expect(fetchTagGroups).toHaveBeenCalledWith('topic-1')
    })
  })

  it('renders sort slot content passed as children next to the Filters button', async () => {
    render(<FilterBar {...defaultProps}><button>Sort slot</button></FilterBar>)
    expect(screen.getByRole('button', { name: 'Sort slot' })).toBeInTheDocument()
  })
})

describe('FilterBar — Favorites Only', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    setupApiMock()
  })

  it('is hidden for unauthenticated users', async () => {
    mockSessionStatus = 'unauthenticated'
    render(<FilterBar {...defaultProps} />)
    fireEvent.click(screen.getByRole('button', { name: /filters/i }))
    expect(screen.queryByRole('button', { name: /favorites only/i })).not.toBeInTheDocument()
  })

  it('appears inside the filter panel (not the always-visible top row) for authenticated users', async () => {
    mockSessionStatus = 'authenticated'
    render(<FilterBar {...defaultProps} />)
    expect(screen.queryByRole('button', { name: /favorites only/i })).not.toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: /filters/i }))
    expect(screen.getByRole('button', { name: /favorites only/i })).toBeInTheDocument()
  })

  it('calls onFavoritesToggle with the flipped value when clicked', async () => {
    mockSessionStatus = 'authenticated'
    const onFavoritesToggle = vi.fn()
    render(<FilterBar {...defaultProps} favoritesOnly={false} onFavoritesToggle={onFavoritesToggle} />)
    fireEvent.click(screen.getByRole('button', { name: /filters/i }))
    fireEvent.click(screen.getByRole('button', { name: /favorites only/i }))
    expect(onFavoritesToggle).toHaveBeenCalledWith(true)
  })
})

// Uses the date-range filter (not the source/tag multi-selects) so these tests don't also need
// to flush the async fetchArticleFilterOriginalSources/fetchTagGroups mount-time fetches — the
// debounce behavior under test is identical regardless of which draft field changes.
describe('FilterBar — debounced auto-apply', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockSessionStatus = 'unauthenticated'
    setupApiMock()
    vi.useFakeTimers()
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  // Radix's PopoverContent renders into a portal appended to document.body, not inside the
  // component's own render container — so this deliberately queries the whole document.
  function openAfterDateInput() {
    fireEvent.click(screen.getByRole('button', { name: /filters/i }))
    fireEvent.click(screen.getByRole('button', { name: /published/i }))
    fireEvent.click(screen.getByRole('button', { name: /^after$/i }))
    return document.querySelector('input[type="date"]') as HTMLInputElement
  }

  it('does not call onApply immediately on a filter change', () => {
    const onApply = vi.fn()
    render(<FilterBar {...defaultProps} onApply={onApply} />)
    const dateInput = openAfterDateInput()
    fireEvent.change(dateInput, { target: { value: '2026-01-01' } })
    expect(onApply).not.toHaveBeenCalled()
  })

  it('calls onApply once the debounce delay elapses', () => {
    const onApply = vi.fn()
    render(<FilterBar {...defaultProps} onApply={onApply} />)
    const dateInput = openAfterDateInput()
    fireEvent.change(dateInput, { target: { value: '2026-01-01' } })
    act(() => { vi.advanceTimersByTime(500) })
    expect(onApply).toHaveBeenCalledWith(expect.objectContaining({ published_after: '2026-01-01' }))
  })

  it('collapses rapid successive edits (e.g. setting both ends of a range) into a single call for the final value', () => {
    const onApply = vi.fn()
    render(<FilterBar {...defaultProps} onApply={onApply} />)
    const dateInput = openAfterDateInput()

    fireEvent.change(dateInput, { target: { value: '2026-01-01' } })
    act(() => { vi.advanceTimersByTime(200) })
    fireEvent.change(dateInput, { target: { value: '2026-01-02' } })
    act(() => { vi.advanceTimersByTime(499) })
    expect(onApply).not.toHaveBeenCalled()

    act(() => { vi.advanceTimersByTime(1) })
    expect(onApply).toHaveBeenCalledTimes(1)
    expect(onApply).toHaveBeenCalledWith(expect.objectContaining({ published_after: '2026-01-02' }))
  })

  it('does not re-apply once the parent has echoed the applied value back down as props', () => {
    const onApply = vi.fn()
    const { rerender } = render(<FilterBar {...defaultProps} onApply={onApply} />)
    const dateInput = openAfterDateInput()
    fireEvent.change(dateInput, { target: { value: '2026-01-01' } })
    act(() => { vi.advanceTimersByTime(500) })
    expect(onApply).toHaveBeenCalledTimes(1)

    // Simulate the URL/props round-trip: parent re-renders FilterBar with the now-applied value.
    rerender(<FilterBar {...defaultProps} publishedAfter="2026-01-01" onApply={onApply} />)
    act(() => { vi.advanceTimersByTime(500) })
    expect(onApply).toHaveBeenCalledTimes(1)
  })
})
