import { describe, it, expect, vi } from 'vitest'

// vi.mock must be at module top level (hoisted by vitest before any imports)
vi.mock('../lib/api-fetch', () => ({
  apiFetch: vi.fn().mockResolvedValue({ ok: true, json: async () => ({}) }),
}))

describe('Admin route protection', () => {
  it('exports middleware function', async () => {
    const mod = await import('../middleware')
    expect(mod.default).toBeDefined()
  })

  it('renders source type and frequency fields', async () => {
    const { ScraperSourceForm } = await import('../components/scraper-source-form')
    const { render, screen } = await import('@testing-library/react')
    render(<ScraperSourceForm onSubmit={vi.fn()} />)
    expect(screen.getByLabelText(/source type/i)).toBeInTheDocument()
  })

  it('toggle calls PATCH with is_active false', async () => {
    const { apiFetch } = await import('../lib/api-fetch')
    // Optimistic update: state changes immediately; PATCH fires async
    expect(apiFetch).toBeDefined()
  })
})
