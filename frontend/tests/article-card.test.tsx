import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'

const fixture = {
  id: 'abc',
  title: 'Test Article',
  source: 'rss',
  url: 'https://example.com',
  content: 'Article body text.',
  published_at: '2026-01-01T00:00:00Z',
  scraped_at: '2026-01-02T00:00:00Z',
}

const detailFixture = {
  ...fixture,
  tags: [],
  tag_groups: [{ group_name: 'tech', display_name: 'Technology', color: '#6366f1', tags: ['AI', 'IoT'] }],
  pain_points: 'Key pain points here.',
  insights: 'Key insights here.',
  innovations: null,
  model_used: 'claude-test',
}

vi.mock('../lib/api-fetch', () => ({
  apiFetch: vi.fn().mockResolvedValue({
    json: async () => detailFixture,
  }),
}))

describe('ArticleCard', () => {
  beforeEach(() => vi.clearAllMocks())

  it('renders title and source', async () => {
    const { ArticleCard } = await import('../components/article-card')
    render(<ArticleCard {...fixture} />)
    expect(screen.getByText('Test Article')).toBeInTheDocument()
    expect(screen.getByText('rss')).toBeInTheDocument()
  })

  it('renders formatted published date', async () => {
    const { ArticleCard } = await import('../components/article-card')
    render(<ArticleCard {...fixture} />)
    expect(screen.getByText(/jan 1, 2026/i)).toBeInTheDocument()
  })

  it('clicking card opens dialog', async () => {
    const { ArticleCard } = await import('../components/article-card')
    render(<ArticleCard {...fixture} />)
    fireEvent.click(screen.getByText('Test Article'))
    await waitFor(() => {
      expect(screen.getByRole('dialog')).toBeInTheDocument()
    })
  })

  it('dialog shows pain_points after loading', async () => {
    const { apiFetch } = await import('../lib/api-fetch')
    vi.mocked(apiFetch).mockResolvedValue({ json: async () => detailFixture } as any)
    const { ArticleCard } = await import('../components/article-card')
    render(<ArticleCard {...fixture} />)
    fireEvent.click(screen.getByText('Test Article'))
    await waitFor(() => {
      expect(screen.getByText('Key pain points here.')).toBeInTheDocument()
    })
  })

  it('dialog shows insights after loading', async () => {
    const { apiFetch } = await import('../lib/api-fetch')
    vi.mocked(apiFetch).mockResolvedValue({ json: async () => detailFixture } as any)
    const { ArticleCard } = await import('../components/article-card')
    render(<ArticleCard {...fixture} />)
    fireEvent.click(screen.getByText('Test Article'))
    await waitFor(() => {
      expect(screen.getByText('Key insights here.')).toBeInTheDocument()
    })
  })

  it('dialog shows tag badges', async () => {
    const { apiFetch } = await import('../lib/api-fetch')
    vi.mocked(apiFetch).mockResolvedValue({ json: async () => detailFixture } as any)
    const { ArticleCard } = await import('../components/article-card')
    render(<ArticleCard {...fixture} />)
    fireEvent.click(screen.getByText('Test Article'))
    await waitFor(() => {
      expect(screen.getByText('AI')).toBeInTheDocument()
      expect(screen.getByText('IoT')).toBeInTheDocument()
    })
  })
})
