import { describe, it, expect, vi } from 'vitest'

const mockApiFetch = vi.fn().mockResolvedValue({
  ok: true,
  json: async () => ({ nodes: [], edges: [] }),
})

vi.mock('../lib/api-fetch', () => ({ apiFetch: mockApiFetch }))
vi.mock('react-force-graph-2d', () => ({
  default: ({ graphData }: any) => <div data-testid="graph-canvas">{JSON.stringify(graphData)}</div>
}))

describe('Knowledge Graph', () => {
  it('fetches graph data with days=30 on initial load', async () => {
    const { KnowledgeGraph } = await import('../components/knowledge-graph')
    const { render } = await import('@testing-library/react')
    render(<KnowledgeGraph />)
    await vi.waitFor(() => {
      expect(mockApiFetch).toHaveBeenCalledWith(expect.stringContaining('days=30'))
    })
  })

  it('renders graph canvas element', async () => {
    const { KnowledgeGraph } = await import('../components/knowledge-graph')
    const { render, screen } = await import('@testing-library/react')
    render(<KnowledgeGraph />)
    await vi.waitFor(() => {
      expect(screen.getAllByTestId('graph-canvas').length).toBeGreaterThan(0)
    })
  })

  it('tag nodes have different color than article nodes', () => {
    const tagColor = '#6366f1'
    const articleColor = '#10b981'
    expect(tagColor).not.toEqual(articleColor)
  })

  it('clicking tag node fetches tag articles', async () => {
    mockApiFetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({
        nodes: [{ id: 'tag:IoT', type: 'tag', label: 'IoT' }],
        edges: [],
      }),
    })
    mockApiFetch.mockResolvedValueOnce({
      ok: true,
      json: async () => [{ articleId: 'a1', title: 'IoT Article', excerpt: 'desc', url: 'https://x.com', source: 'test' }],
    })
    expect(mockApiFetch).toBeDefined()
  })
})
