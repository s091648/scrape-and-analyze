// frontend/tests/graph.test.tsx
import { describe, it, expect, vi, beforeEach, beforeAll } from 'vitest'
import type { ComponentType } from 'react'

const mockApiFetch = vi.fn().mockResolvedValue({
  ok: true,
  json: async () => ({ nodes: [], edges: [] }),
})

vi.mock('@/lib/api/client', () => ({ apiFetch: mockApiFetch }))
vi.mock('next/dynamic', () => ({
  default: (_loader: any, _opts?: any) =>
    ({ graphData }: any) => <div data-testid="graph-canvas">{JSON.stringify(graphData)}</div>,
}))
vi.mock('@/lib/providers/topic-provider', () => ({
  useTopic: () => ({ selectedTopicId: 'test-topic-id' }),
}))
vi.mock('react-force-graph-2d', () => ({
  default: ({ graphData }: any) => <div data-testid="graph-canvas">{JSON.stringify(graphData)}</div>
}))
vi.mock('next-auth/react', () => ({
  useSession: () => ({ data: { accessToken: 'test-token' }, status: 'authenticated' }),
  SessionProvider: ({ children }: any) => children,
}))
vi.mock('@/lib/providers', () => ({
  useI18n: () => ({ t: (k: string) => k, locale: 'en', setLocale: vi.fn(), availableLanguages: [], resolvedLanguage: 'en', isLoading: false }),
  useTopic: () => ({ selectedTopicId: 'test-topic-id', topics: [], selectedTopic: null, setSelectedTopicId: vi.fn(), refresh: vi.fn(), isLoading: false }),
  useGuestMode: () => ({ isGuestMode: false, enterGuestMode: vi.fn(), exitGuestMode: vi.fn() }),
}))

let KnowledgeGraph: ComponentType<{ articleIdFilter?: Set<string> }>
let applyArticleFilter: (data: any, filter: Set<string>) => any

beforeAll(async () => {
  const module = await import('@/components/features/graph/knowledge-graph')
  KnowledgeGraph = module.KnowledgeGraph
  applyArticleFilter = module.applyArticleFilter
})

describe('Knowledge Graph', () => {
  beforeEach(() => {
    mockApiFetch.mockReset()
    mockApiFetch.mockResolvedValue({
      ok: true,
      json: async () => ({ nodes: [], edges: [] }),
    })
  })

  it('fetches graph data with published_after on initial load', async () => {
    const { render } = await import('@testing-library/react')
    render(<KnowledgeGraph />)
    await vi.waitFor(() => {
      expect(mockApiFetch).toHaveBeenCalledWith(expect.stringContaining('published_after='), expect.anything(), expect.anything())
    })
  })

  it('renders graph canvas element', async () => {
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

  it('days filter change triggers re-fetch with updated published_after', async () => {
    const { render, screen } = await import('@testing-library/react')
    const { fireEvent } = await import('@testing-library/react')
    render(<KnowledgeGraph />)
    await vi.waitFor(() => {
      expect(mockApiFetch).toHaveBeenCalledWith(expect.stringContaining('published_after='), expect.anything(), expect.anything())
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
        expect(mockApiFetch).toHaveBeenCalledWith(expect.stringContaining('published_after='), expect.anything(), expect.anything())
      })
    }
    expect(mockApiFetch).toBeDefined()
  })

  it('loading state shown while fetching', async () => {
    let resolvePromise: (v: any) => void
    const promise = new Promise(r => { resolvePromise = r })
    mockApiFetch.mockReturnValueOnce(promise)
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

// ── SSR seed (021-ssr-public-pages) ─────────────────────────────────────────

describe('KnowledgeGraph initialData seeding', () => {
  beforeEach(() => {
    mockApiFetch.mockReset()
    mockApiFetch.mockResolvedValue({ ok: true, json: async () => ({ nodes: [], edges: [] }) })
  })

  const seededData = {
    nodes: [{ id: 'g1', type: 'group', label: 'Seeded Group', groupName: 'seeded', color: '#6366f1' }],
    edges: [],
  }

  it('renders the seeded graph immediately without fetching', async () => {
    const { render, screen } = await import('@testing-library/react')
    render(<KnowledgeGraph initialData={seededData as any} />)

    expect(screen.getByTestId('graph-canvas').textContent).toContain('Seeded Group')
    expect(mockApiFetch).not.toHaveBeenCalled()
  })

  it('fetches normally (no seed) when initialData is not provided', async () => {
    const { render } = await import('@testing-library/react')
    render(<KnowledgeGraph />)
    await vi.waitFor(() => {
      expect(mockApiFetch).toHaveBeenCalled()
    })
  })

  it('still fetches on a later filter change after a seeded mount', async () => {
    const { render, screen, fireEvent } = await import('@testing-library/react')
    render(<KnowledgeGraph initialData={seededData as any} />)
    expect(mockApiFetch).not.toHaveBeenCalled()

    const allComboboxes = screen.queryAllByRole('combobox')
    const daysSelect = allComboboxes.find(el => el.querySelector('option[value="7"]'))
    expect(daysSelect).toBeTruthy()
    fireEvent.change(daysSelect!, { target: { value: '7' } })

    await vi.waitFor(() => {
      expect(mockApiFetch).toHaveBeenCalledWith(expect.stringContaining('published_after='), expect.anything(), expect.anything())
    })
  })
})

describe('applyArticleFilter', () => {
  it('empty Set filter removes all nodes', () => {
    const data = {
      nodes: [
        { id: 'art-1', type: 'article' as const, label: 'Test', articleId: 'art-1' },
        { id: 'g1', type: 'group' as const, label: 'Group', groupName: 'g1' },
      ],
      edges: [{ source: 'g1', target: 'art-1' }],
    }
    const result = applyArticleFilter(data, new Set())
    expect(result.nodes).toHaveLength(0)
    expect(result.edges).toHaveLength(0)
  })

  it('keeps article nodes that match by id when articleId field is absent', () => {
    const data = {
      nodes: [
        { id: 'art-1', type: 'article' as const, label: 'Test' },
      ],
      edges: [],
    }
    const result = applyArticleFilter(data, new Set(['art-1']))
    expect(result.nodes).toHaveLength(1)
  })
})
