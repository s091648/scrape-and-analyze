import { describe, it, expect, vi, beforeEach, beforeAll } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { fetchArticleFilterSources } from '@/lib/api/articles'
import { fetchTagGroups } from '@/lib/api/tags'
import type { TagGroupOut } from '@/lib/api/tags'
import type { ComponentType } from 'react'

vi.mock('@/lib/api/articles', () => ({
  fetchArticleFilterSources: vi.fn(),
}))

vi.mock('@/lib/api/tags', () => ({
  fetchTagGroups: vi.fn(),
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
  sources: [],
  tags: [],
  tagGroups: [],
  publishedAfter: '',
  publishedBefore: '',
  scrapedAfter: '',
  scrapedBefore: '',
  activeFilterCount: 0,
  onApply: vi.fn(),
}

function setupApiMock(sourceOptions = ['rss', 'blog'], tagGroups = mockTagGroups) {
  vi.mocked(fetchArticleFilterSources).mockResolvedValue(sourceOptions)
  vi.mocked(fetchTagGroups).mockResolvedValue(tagGroups)
}

let FilterBar: ComponentType<typeof defaultProps & { activeFilterCount?: number; onApply?: ReturnType<typeof vi.fn> }>

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
    render(<FilterBar {...defaultProps} sources={['rss']} onApply={onApply} activeFilterCount={1} />)
    fireEvent.click(screen.getByRole('button', { name: /filters/i }))
    fireEvent.click(screen.getByRole('button', { name: /apply/i }))
    expect(onApply).toHaveBeenCalledWith(expect.objectContaining({ source: ['rss'] }))
  })

  it('"Clear" resets filters and calls onApply with empty values', async () => {
    const onApply = vi.fn()
    render(<FilterBar {...defaultProps} sources={['rss']} onApply={onApply} activeFilterCount={1} />)
    fireEvent.click(screen.getByRole('button', { name: /filters/i }))
    fireEvent.click(screen.getByRole('button', { name: /clear/i }))
    expect(onApply).toHaveBeenCalledWith({
      source: [], tag: [], tag_group: [], published_after: '', published_before: '', scraped_after: '', scraped_before: '',
    })
  })

  it('fetches source options and tag groups on mount', async () => {
    render(<FilterBar {...defaultProps} />)
    await waitFor(() => {
      expect(fetchArticleFilterSources).toHaveBeenCalled()
      expect(fetchTagGroups).toHaveBeenCalledWith('topic-1')
    })
  })
})
