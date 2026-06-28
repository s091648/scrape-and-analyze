import { describe, it, expect, vi, beforeEach, beforeAll } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
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

  it('clicking Apply calls onApply with current draft state', async () => {
    const onApply = vi.fn()
    render(<FilterBar {...defaultProps} originalSources={['arxiv']} onApply={onApply} activeFilterCount={1} />)
    fireEvent.click(screen.getByRole('button', { name: /filters/i }))
    fireEvent.click(screen.getByRole('button', { name: /apply/i }))
    expect(onApply).toHaveBeenCalledWith(expect.objectContaining({ original_source: ['arxiv'] }))
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
})

describe('FilterBar — sort dropdown', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    setupApiMock()
  })

  it('renders sort dropdown with current value', async () => {
    render(<FilterBar {...defaultProps} sort="citation_count" onSortChange={vi.fn()} />)
    await waitFor(() => {
      const select = screen.getByRole('combobox')
      expect(select).toHaveValue('citation_count')
    })
  })

  it('calls onSortChange when sort selection changes', async () => {
    const onSortChange = vi.fn()
    render(<FilterBar {...defaultProps} sort="scraped_at" onSortChange={onSortChange} />)
    await waitFor(() => {
      const select = screen.getByRole('combobox')
      fireEvent.change(select, { target: { value: 'view_count' } })
      expect(onSortChange).toHaveBeenCalledWith('view_count')
    })
  })

  it('renders all sort options', async () => {
    render(<FilterBar {...defaultProps} sort="scraped_at" onSortChange={vi.fn()} />)
    await waitFor(() => {
      const select = screen.getByRole('combobox')
      const options = Array.from(select.querySelectorAll('option')).map(o => (o as HTMLOptionElement).value)
      expect(options).toContain('scraped_at')
      expect(options).toContain('citation_count')
      expect(options).toContain('view_count')
      expect(options).toContain('published_at')
    })
  })
})
