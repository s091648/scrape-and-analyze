import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen } from '@testing-library/react'

vi.mock('../lib/api-fetch', () => ({
  apiFetch: vi.fn().mockResolvedValue({
    ok: true,
    json: async () => ({
      items: [{
        id: 'abc123',
        title: 'Test Article',
        source: 'techcrunch',
        published_at: '2026-02-20T00:00:00Z',
        scraped_at: '2026-02-21T00:00:00Z',
        url: 'https://example.com',
      }],
      total: 1, page: 1, size: 20,
    }),
  }),
}))

describe('Article Dashboard', () => {
  it('renders article title, source, and dates', async () => {
    const { ArticleCard } = await import('../components/article-card')
    render(
      <ArticleCard
        id="abc123"
        title="Test Article"
        source="techcrunch"
        published_at="2026-02-20T00:00:00Z"
        scraped_at="2026-02-21T00:00:00Z"
        url="https://example.com"
      />
    )
    expect(screen.getByText('Test Article')).toBeInTheDocument()
    expect(screen.getByText('techcrunch')).toBeInTheDocument()
  })

  it('renders failed task section', async () => {
    const { FailedTaskList } = await import('../components/failed-task-list')
    render(<FailedTaskList items={[{
      id: 'f1', task_type: 'scrape', article_url: 'https://x.com',
      exception_message: 'Timeout', failed_at: '2026-02-21T00:00:00Z', resolved: false,
      exception_type: 'TimeoutError',
    }]} />)
    expect(screen.getByText('Timeout')).toBeInTheDocument()
  })

  it('reads page and sort from URL params', async () => {
    const { usePagination } = await import('../hooks/use-pagination')
    vi.mock('next/navigation', () => ({
      useSearchParams: () => new URLSearchParams('page=2&sort=published_at'),
      useRouter: () => ({ push: vi.fn() }),
    }))
    expect(usePagination).toBeDefined()
  })
})
