import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { fetchArticleFilterSources, fetchArticleFilterTags } from '../lib/api/articles'

vi.mock('../lib/api/articles', () => ({
  fetchArticleFilterSources: vi.fn(),
  fetchArticleFilterTags: vi.fn(),
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
        'filterBar.from': 'From',
        'filterBar.to': 'To',
        'filterBar.clear': 'Clear',
        'filterBar.apply': 'Apply',
      }
      return map[key] ?? key
    },
  }),
}))

const defaultProps = {
  sources: [],
  tags: [],
  publishedAfter: '',
  publishedBefore: '',
  scrapedAfter: '',
  scrapedBefore: '',
  activeFilterCount: 0,
  onApply: vi.fn(),
}

function setupApiMock(sourceOptions = ['rss', 'blog'], tagOptions = ['AI', 'IoT']) {
  vi.mocked(fetchArticleFilterSources).mockResolvedValue(sourceOptions)
  vi.mocked(fetchArticleFilterTags).mockResolvedValue(tagOptions)
}

describe('FilterBar', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    setupApiMock()
  })

  it('"Filters" toggle button is always rendered', async () => {
    const { FilterBar } = await import('../components/features/articles/filter-bar')
    render(<FilterBar {...defaultProps} />)
    expect(screen.getByRole('button', { name: /filters/i })).toBeInTheDocument()
  })

  it('clicking "Filters" reveals Source and Tag popover triggers', async () => {
    const { FilterBar } = await import('../components/features/articles/filter-bar')
    render(<FilterBar {...defaultProps} />)
    fireEvent.click(screen.getByRole('button', { name: /filters/i }))
    expect(screen.getByRole('button', { name: /source/i })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /tag/i })).toBeInTheDocument()
  })

  it('"Clear" button is hidden when activeFilterCount is 0', async () => {
    const { FilterBar } = await import('../components/features/articles/filter-bar')
    render(<FilterBar {...defaultProps} />)
    fireEvent.click(screen.getByRole('button', { name: /filters/i }))
    expect(screen.queryByRole('button', { name: /clear/i })).not.toBeInTheDocument()
  })

  it('"Clear" button is visible when activeFilterCount > 0', async () => {
    const { FilterBar } = await import('../components/features/articles/filter-bar')
    render(<FilterBar {...defaultProps} activeFilterCount={2} />)
    fireEvent.click(screen.getByRole('button', { name: /filters/i }))
    expect(screen.getByRole('button', { name: /clear/i })).toBeInTheDocument()
  })

  it('clicking Apply calls onApply with current draft state', async () => {
    const onApply = vi.fn()
    const { FilterBar } = await import('../components/features/articles/filter-bar')
    render(<FilterBar {...defaultProps} sources={['rss']} onApply={onApply} activeFilterCount={1} />)
    fireEvent.click(screen.getByRole('button', { name: /filters/i }))
    fireEvent.click(screen.getByRole('button', { name: /apply/i }))
    expect(onApply).toHaveBeenCalledWith(expect.objectContaining({ source: ['rss'] }))
  })

  it('"Clear" resets filters and calls onApply with empty values', async () => {
    const onApply = vi.fn()
    const { FilterBar } = await import('../components/features/articles/filter-bar')
    render(<FilterBar {...defaultProps} sources={['rss']} onApply={onApply} activeFilterCount={1} />)
    fireEvent.click(screen.getByRole('button', { name: /filters/i }))
    fireEvent.click(screen.getByRole('button', { name: /clear/i }))
    expect(onApply).toHaveBeenCalledWith({
      source: [], tag: [], published_after: '', published_before: '', scraped_after: '', scraped_before: '',
    })
  })

  it('fetches source and tag options on mount', async () => {
    const { FilterBar } = await import('../components/features/articles/filter-bar')
    render(<FilterBar {...defaultProps} />)
    await waitFor(() => {
      expect(fetchArticleFilterSources).toHaveBeenCalled()
      expect(fetchArticleFilterTags).toHaveBeenCalled()
    })
  })
})
