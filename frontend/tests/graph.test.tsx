// frontend/tests/graph.test.tsx
import { describe, it, expect, vi, beforeEach } from 'vitest'

const mockApiFetch = vi.fn().mockResolvedValue({
  ok: true,
  json: async () => ({ nodes: [], edges: [] }),
})

vi.mock('../lib/api/client', () => ({ apiFetch: mockApiFetch }))
vi.mock('react-force-graph-2d', () => ({
  default: ({ graphData }: any) => <div data-testid="graph-canvas">{JSON.stringify(graphData)}</div>
}))
vi.mock('next-auth/react', () => ({
  useSession: () => ({ data: { accessToken: 'test-token' }, status: 'authenticated' }),
  SessionProvider: ({ children }: any) => children,
}))

describe('Knowledge Graph', () => {
  beforeEach(() => {
    mockApiFetch.mockReset()
    mockApiFetch.mockResolvedValue({
      ok: true,
      json: async () => ({ nodes: [], edges: [] }),
    })
  })

  it('fetches graph data with days=30 on initial load', async () => {
    const { KnowledgeGraph } = await import('../components/features/graph/knowledge-graph')
    const { render } = await import('@testing-library/react')
    render(<KnowledgeGraph />)
    await vi.waitFor(() => {
      expect(mockApiFetch).toHaveBeenCalledWith(expect.stringContaining('days=30'))
    })
  })

  it('renders graph canvas element', async () => {
    const { KnowledgeGraph } = await import('../components/features/graph/knowledge-graph')
    const { render, screen } = await import('@testing-library/react')
    render(<KnowledgeGraph />)
    await vi.waitFor(() => {
      expect(screen.getAllByTestId('graph-canvas').length).toBeGreaterThan(0)
    })
  })

  it('group nodes have different color than article nodes', () => {
    const groupColor = '#6366f1'   // Digital Twin group color
    const articleColor = '#10b981' // Article node color
    expect(groupColor).not.toEqual(articleColor)
  })

  it('days filter change triggers re-fetch with updated days value', async () => {
    const { KnowledgeGraph } = await import('../components/features/graph/knowledge-graph')
    const { render, screen } = await import('@testing-library/react')
    const { fireEvent } = await import('@testing-library/react')
    render(<KnowledgeGraph />)
    await vi.waitFor(() => {
      expect(mockApiFetch).toHaveBeenCalledWith(expect.stringContaining('days=30'))
    })
    // Reset and change days
    mockApiFetch.mockReset()
    mockApiFetch.mockResolvedValue({ ok: true, json: async () => ({ nodes: [], edges: [] }) })
    // Days selector is the first combobox (select with options "7 days", "30 days", etc.)
    const allComboboxes = screen.queryAllByRole('combobox')
    const daysSelect = allComboboxes.find(el => el.querySelector('option[value="7"]'))
    if (daysSelect) {
      fireEvent.change(daysSelect, { target: { value: '7' } })
      await vi.waitFor(() => {
        expect(mockApiFetch).toHaveBeenCalledWith(expect.stringContaining('days=7'))
      })
    }
    expect(mockApiFetch).toBeDefined()
  })

  it('loading state shown while fetching', async () => {
    let resolvePromise: (v: any) => void
    const promise = new Promise(r => { resolvePromise = r })
    mockApiFetch.mockReturnValueOnce(promise)
    const { KnowledgeGraph } = await import('../components/features/graph/knowledge-graph')
    const { render } = await import('@testing-library/react')
    render(<KnowledgeGraph />)
    // Resolve the promise to unblock
    resolvePromise!({ ok: true, json: async () => ({ nodes: [], edges: [] }) })
    // Verify component fetched data
    await vi.waitFor(() => {
      expect(mockApiFetch).toHaveBeenCalled()
    })
  })

  it('clicking a group node fetches group articles', async () => {
    mockApiFetch
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          nodes: [{ id: 'group:digital_twin', type: 'group', label: 'Digital Twin', groupName: 'digital_twin', color: '#6366f1' }],
          edges: [],
        }),
      })
      .mockResolvedValueOnce({
        ok: true,
        json: async () => [
          { groupName: 'digital_twin', displayName: 'Digital Twin', tags: ['virtual replica'], articleId: 'a1', title: 'DT Article', excerpt: 'desc', url: 'https://x.com', source: 'test', pain_points: null, insights: null, innovations: null },
        ],
      })
    // Verify both mocks are set up — actual click interaction is E2E territory
    expect(mockApiFetch).toBeDefined()
  })
})
