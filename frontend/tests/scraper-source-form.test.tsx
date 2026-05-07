import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'

describe('ScraperSourceForm', () => {
  beforeEach(() => vi.clearAllMocks())

  it('renders Source Type and Frequency fields', async () => {
    const { ScraperSourceForm } = await import('../components/features/scraper/scraper-source-form')
    render(<ScraperSourceForm onSubmit={vi.fn()} />)
    expect(screen.getByLabelText(/source type/i)).toBeInTheDocument()
    expect(screen.getByLabelText(/frequency/i)).toBeInTheDocument()
  })

  it('default source_type is rss', async () => {
    const { ScraperSourceForm } = await import('../components/features/scraper/scraper-source-form')
    render(<ScraperSourceForm onSubmit={vi.fn()} />)
    const select = screen.getByLabelText(/source type/i) as HTMLSelectElement
    expect(select.value).toBe('rss')
  })

  it('changing to blog reveals CSS selector fields', async () => {
    const { ScraperSourceForm } = await import('../components/features/scraper/scraper-source-form')
    render(<ScraperSourceForm onSubmit={vi.fn()} />)
    fireEvent.change(screen.getByLabelText(/source type/i), { target: { value: 'blog' } })
    expect(screen.getByLabelText(/article link/i)).toBeInTheDocument()
    expect(screen.getByLabelText(/title/i)).toBeInTheDocument()
    expect(screen.getByLabelText(/content/i)).toBeInTheDocument()
  })

  it('changing back to rss hides selector fields', async () => {
    const { ScraperSourceForm } = await import('../components/features/scraper/scraper-source-form')
    render(<ScraperSourceForm onSubmit={vi.fn()} />)
    fireEvent.change(screen.getByLabelText(/source type/i), { target: { value: 'blog' } })
    fireEvent.change(screen.getByLabelText(/source type/i), { target: { value: 'rss' } })
    expect(screen.queryByLabelText(/article link/i)).not.toBeInTheDocument()
  })

  it('submit with RSS data calls onSubmit with correct shape', async () => {
    const onSubmit = vi.fn()
    const { ScraperSourceForm } = await import('../components/features/scraper/scraper-source-form')
    render(<ScraperSourceForm onSubmit={onSubmit} />)
    fireEvent.change(screen.getByLabelText(/name/i), { target: { value: 'HN' } })
    fireEvent.change(screen.getByLabelText(/url/i), { target: { value: 'https://hn.com/rss' } })
    fireEvent.submit(screen.getByRole('button', { name: /add source/i }).closest('form')!)
    expect(onSubmit).toHaveBeenCalledWith(
      expect.objectContaining({ source_type: 'rss', name: 'HN', url: 'https://hn.com/rss' })
    )
  })

  it('submit with blog data includes selector_config', async () => {
    const onSubmit = vi.fn()
    const { ScraperSourceForm } = await import('../components/features/scraper/scraper-source-form')
    render(<ScraperSourceForm onSubmit={onSubmit} />)
    fireEvent.change(screen.getByLabelText(/source type/i), { target: { value: 'blog' } })
    fireEvent.change(screen.getByLabelText(/article link/i), { target: { value: 'a.post' } })
    fireEvent.submit(screen.getByRole('button', { name: /add source/i }).closest('form')!)
    const called = onSubmit.mock.calls[0][0]
    expect(called.source_type).toBe('blog')
    expect(called.selector_config).toBeDefined()
    expect(called.selector_config.article_link).toBe('a.post')
  })
})
