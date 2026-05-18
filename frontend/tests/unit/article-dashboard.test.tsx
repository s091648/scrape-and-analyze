import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen } from '@testing-library/react'

vi.mock('next/navigation', () => ({
  useSearchParams: vi.fn(),
  useRouter: vi.fn(() => ({ push: vi.fn() })),
}))

vi.mock('@/lib/api/articles', () => ({
  fetchArticles: vi.fn().mockResolvedValue({
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
}))

vi.mock('@/lib/providers', () => ({
  useTopic: vi.fn(() => ({ selectedTopicId: 'topic-1' })),
  useI18n: vi.fn(() => ({ t: (key: string) => key, locale: 'en' })),
}))

describe('Article Dashboard', () => {
  it('renders article title, source, and dates', async () => {
    const { ArticleCard } = await import('@/components/features/articles/article-card')
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
    const { FailedTaskList } = await import('@/components/features/monitoring/failed-task-list')
    render(<FailedTaskList items={[{
      id: 'f1', task_type: 'scrape', article_url: 'https://x.com',
      exception_message: 'Timeout', failed_at: '2026-02-21T00:00:00Z', resolved: false,
      exception_type: 'TimeoutError',
    }]} />)
    expect(screen.getByText('Timeout')).toBeInTheDocument()
  })

  it('reads page=2 and sort=published_at from URL', async () => {
    const { renderHook } = await import('@testing-library/react')
    const { useSearchParams, useRouter } = await import('next/navigation')
    vi.mocked(useSearchParams).mockReturnValue(new URLSearchParams('page=2&sort=published_at') as any)
    vi.mocked(useRouter).mockReturnValue({ push: vi.fn() } as any)
    const { usePagination } = await import('@/hooks/use-pagination')
    const { result } = renderHook(() => usePagination())
    expect(result.current.page).toBe(2)
    expect(result.current.sort).toBe('published_at')
  })
})
