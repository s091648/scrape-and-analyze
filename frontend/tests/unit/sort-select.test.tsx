import { describe, it, expect, vi, beforeEach, beforeAll } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import type { ComponentType } from 'react'

vi.mock('@/lib/providers', () => ({
  useI18n: () => ({
    locale: 'en',
    t: (key: string) => {
      const map: Record<string, string> = {
        'filterBar.sortBy': 'Sort by',
        'filterBar.sortTooltip': 'Choose how the article list is ordered',
        'filterBar.sortScrapedAt': 'Scraped At',
        'filterBar.sortPublishedAt': 'Published At',
        'filterBar.sortViewCount': 'View Count',
        'filterBar.sortSource': 'Source',
        'filterBar.sortTitle': 'Title',
        'filterBar.sortAscending': 'Ascending',
        'filterBar.sortDescending': 'Descending',
        'metrics.citation_count': 'Citation Count',
      }
      return map[key] ?? key
    },
  }),
}))

// 2026-07-12: citation_count is now sourced from the enabled-metric-definitions hook, not
// hardcoded in SORT_OPTIONS — mock the hook so tests control what's "enabled" per case.
const mockUseMetricDefinitions = vi.fn()
vi.mock('@/components/features/articles/use-metric-definitions', () => ({
  useMetricDefinitions: () => mockUseMetricDefinitions(),
}))

// eslint-disable-next-line @typescript-eslint/no-explicit-any
let SortSelect: ComponentType<any>

beforeAll(async () => {
  const module = await import('@/components/features/articles/sort-select')
  SortSelect = module.SortSelect as any
})

beforeEach(() => {
  vi.clearAllMocks()
  mockUseMetricDefinitions.mockReturnValue({
    citation_count: { metric_key: 'citation_count', label_i18n_key: 'metrics.citation_count', icon_name: 'quote', format_hint: 'integer', unit: null },
  })
  // cmdk calls scrollIntoView internally; jsdom doesn't implement it
  Element.prototype.scrollIntoView = vi.fn()
})

describe('SortSelect', () => {
  it('renders the trigger labelled with the current sort field', async () => {
    render(<SortSelect sort="citation_count" order="desc" onSortChange={vi.fn()} onOrderChange={vi.fn()} />)
    await waitFor(() => {
      expect(screen.getByRole('button', { name: /sort by: citation count/i })).toBeInTheDocument()
    })
  })

  it('explains what the dropdown does via a tooltip', async () => {
    render(<SortSelect sort="scraped_at" order="desc" onSortChange={vi.fn()} onOrderChange={vi.fn()} />)
    await waitFor(() => {
      expect(screen.getByRole('button', { name: /sort by: scraped at/i })).toHaveAttribute(
        'title',
        'Choose how the article list is ordered'
      )
    })
  })

  it('calls onSortChange when a sort option is selected', async () => {
    const onSortChange = vi.fn()
    render(<SortSelect sort="scraped_at" order="desc" onSortChange={onSortChange} onOrderChange={vi.fn()} />)
    fireEvent.click(screen.getByRole('button', { name: /sort by: scraped at/i }))
    fireEvent.click(screen.getByText('View Count'))
    expect(onSortChange).toHaveBeenCalledWith('view_count')
  })

  it('renders all sort options', async () => {
    render(<SortSelect sort="scraped_at" order="desc" onSortChange={vi.fn()} onOrderChange={vi.fn()} />)
    fireEvent.click(screen.getByRole('button', { name: /sort by: scraped at/i }))
    expect(screen.getByText('Published At')).toBeInTheDocument()
    expect(screen.getByText('Citation Count')).toBeInTheDocument()
    expect(screen.getByText('View Count')).toBeInTheDocument()
    expect(screen.getByText('Title')).toBeInTheDocument()
  })

  it('shows a descending indicator and toggles to ascending on click', () => {
    const onOrderChange = vi.fn()
    render(<SortSelect sort="scraped_at" order="desc" onSortChange={vi.fn()} onOrderChange={onOrderChange} />)
    const toggle = screen.getByRole('button', { name: /descending/i })
    expect(toggle).toBeInTheDocument()
    fireEvent.click(toggle)
    expect(onOrderChange).toHaveBeenCalledWith('asc')
  })

  it('shows an ascending indicator and toggles to descending on click', () => {
    const onOrderChange = vi.fn()
    render(<SortSelect sort="scraped_at" order="asc" onSortChange={vi.fn()} onOrderChange={onOrderChange} />)
    const toggle = screen.getByRole('button', { name: /ascending/i })
    expect(toggle).toBeInTheDocument()
    fireEvent.click(toggle)
    expect(onOrderChange).toHaveBeenCalledWith('desc')
  })

  // ── Dynamic catalog metrics (2026-07-12, US8) ────────────────────────────

  it('does not show a sort option for a metric that is not currently enabled', async () => {
    mockUseMetricDefinitions.mockReturnValue({})
    render(<SortSelect sort="scraped_at" order="desc" onSortChange={vi.fn()} onOrderChange={vi.fn()} />)
    fireEvent.click(screen.getByRole('button', { name: /sort by: scraped at/i }))
    expect(screen.queryByText('Citation Count')).not.toBeInTheDocument()
  })

  it('shows a sort option for each enabled catalog metric beyond citation_count', async () => {
    mockUseMetricDefinitions.mockReturnValue({
      citation_count: { metric_key: 'citation_count', label_i18n_key: 'metrics.citation_count', icon_name: 'quote', format_hint: 'integer', unit: null },
      impact_factor: { metric_key: 'impact_factor', label_i18n_key: 'metrics.impact_factor', icon_name: 'trending-up', format_hint: 'decimal', unit: null },
    })
    render(<SortSelect sort="scraped_at" order="desc" onSortChange={vi.fn()} onOrderChange={vi.fn()} />)
    fireEvent.click(screen.getByRole('button', { name: /sort by: scraped at/i }))
    expect(screen.getByText('metrics.impact_factor')).toBeInTheDocument()
  })

  it('calls onSortChange with the metric_key when a dynamic metric option is selected', async () => {
    const onSortChange = vi.fn()
    render(<SortSelect sort="scraped_at" order="desc" onSortChange={onSortChange} onOrderChange={vi.fn()} />)
    fireEvent.click(screen.getByRole('button', { name: /sort by: scraped at/i }))
    fireEvent.click(screen.getByText('Citation Count'))
    expect(onSortChange).toHaveBeenCalledWith('citation_count')
  })
})
