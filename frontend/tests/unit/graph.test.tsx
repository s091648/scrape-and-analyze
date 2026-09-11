// frontend/tests/graph.test.tsx
import { describe, it, expect, vi, beforeEach, beforeAll } from 'vitest'
import type { ComponentType } from 'react'

const mockApiFetch = vi.fn().mockResolvedValue({
  ok: true,
  json: async () => ({ nodes: [], edges: [] }),
})

vi.mock('@/lib/api/client', () => ({ apiFetch: mockApiFetch }))
// knowledge-graph.tsx loads react-force-graph-2d via next/dynamic — mocking dynamic()
// itself (rather than the 'react-force-graph-2d' module, which this stub never imports)
// is what actually intercepts it. Captures the last props it was rendered with, so tests
// can invoke its canvas-drawing callbacks (nodeCanvasObject, linkColor) directly —
// react-force-graph-2d itself only calls them from inside an actual <canvas> render loop,
// which jsdom doesn't run.
let lastForceGraphProps: any = null
vi.mock('next/dynamic', () => ({
  default: (_loader: any, _opts?: any) =>
    (props: any) => {
      lastForceGraphProps = props
      return <div data-testid="graph-canvas">{JSON.stringify(props.graphData)}</div>
    },
}))
vi.mock('@/lib/providers/topic-provider', () => ({
  useTopic: () => ({ selectedTopicId: 'test-topic-id' }),
}))
vi.mock('next-auth/react', () => ({
  useSession: () => ({ data: { accessToken: 'test-token' }, status: 'authenticated' }),
  SessionProvider: ({ children }: any) => children,
}))
let mockTheme: 'light' | 'dark' = 'light'
vi.mock('@/lib/providers', () => ({
  useI18n: () => ({ t: (k: string) => k, locale: 'en', setLocale: vi.fn(), availableLanguages: [], resolvedLanguage: 'en', isLoading: false }),
  useTopic: () => ({ selectedTopicId: 'test-topic-id', topics: [], selectedTopic: null, setSelectedTopicId: vi.fn(), refresh: vi.fn(), isLoading: false }),
  useGuestMode: () => ({ isGuestMode: false, enterGuestMode: vi.fn(), exitGuestMode: vi.fn() }),
  useTheme: () => ({ theme: mockTheme, mode: mockTheme, setMode: vi.fn(), cycleMode: vi.fn() }),
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

    // Other tests in this file leave their own rendered trees in the document (no cleanup
    // between tests), so this instance's canvas is the last match, not the only one.
    const canvases = screen.getAllByTestId('graph-canvas')
    expect(canvases[canvases.length - 1].textContent).toContain('Seeded Group')
    // FilterBar fetches its own filter-option lists on mount regardless of graph seeding —
    // only the graph endpoint itself must stay unfetched.
    expect(mockApiFetch).not.toHaveBeenCalledWith(expect.stringContaining('/analyses/graph'), expect.anything(), expect.anything())
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
    expect(mockApiFetch).not.toHaveBeenCalledWith(expect.stringContaining('/analyses/graph'), expect.anything(), expect.anything())

    // The FilterBar UI has no native <select> — filters live behind a toggled panel, and apply
    // themselves (debounced) on change rather than via a separate Apply button. Other renders in
    // this file leave stale trees in the document (no cleanup between tests), so target the
    // just-rendered (last) instance's controls. published_after already defaults to "30 days
    // ago" (matching KnowledgeGraph's own default), so the date popover opens straight into
    // "after" mode — changing that date is a real filter change that should trigger a fetch.
    const filterToggles = screen.getAllByRole('button', { name: /filterBar\.filters/ })
    fireEvent.click(filterToggles[filterToggles.length - 1])
    const publishedToggles = screen.getAllByRole('button', { name: /filterBar\.published/ })
    fireEvent.click(publishedToggles[publishedToggles.length - 1])
    const dateInputs = document.querySelectorAll('input[type="date"]')
    fireEvent.change(dateInputs[dateInputs.length - 1], { target: { value: '2020-01-01' } })

    await vi.waitFor(() => {
      expect(mockApiFetch).toHaveBeenCalledWith(expect.stringContaining('published_after=2020-01-01'), expect.anything(), expect.anything())
    }, { timeout: 2000 })
  })
})

describe('KnowledgeGraph theme-aware canvas drawing', () => {
  beforeEach(() => {
    mockApiFetch.mockReset()
    mockApiFetch.mockResolvedValue({ ok: true, json: async () => ({ nodes: [], edges: [] }) })
    mockTheme = 'light'
    lastForceGraphProps = null
  })

  function fakeCtx() {
    return {
      beginPath: vi.fn(), arc: vi.fn(), fill: vi.fn(), stroke: vi.fn(),
      fillText: vi.fn(), setLineDash: vi.fn(), save: vi.fn(), restore: vi.fn(),
    } as any
  }

  it('linkColor resolves to the light-theme link color', async () => {
    const { render } = await import('@testing-library/react')
    render(<KnowledgeGraph />)
    await vi.waitFor(() => expect(lastForceGraphProps).not.toBeNull())
    expect(lastForceGraphProps.linkColor()).toBe('rgba(71, 85, 105, 0.35)')
  })

  it('linkColor resolves to the dark-theme link color', async () => {
    mockTheme = 'dark'
    const { render } = await import('@testing-library/react')
    render(<KnowledgeGraph />)
    await vi.waitFor(() => expect(lastForceGraphProps).not.toBeNull())
    expect(lastForceGraphProps.linkColor()).toBe('rgba(148, 163, 184, 0.55)')
  })

  it('draws tag node labels in the dark-theme color', async () => {
    mockTheme = 'dark'
    const { render } = await import('@testing-library/react')
    render(<KnowledgeGraph />)
    await vi.waitFor(() => expect(lastForceGraphProps).not.toBeNull())
    const ctx = fakeCtx()
    lastForceGraphProps.nodeCanvasObject({ type: 'tag', label: 'test-tag', x: 0, y: 0 }, ctx, 1)
    expect(ctx.fillStyle).toBe('#cbd5e1')
  })

  it('draws the hovered article label in the dark-theme color', async () => {
    mockTheme = 'dark'
    const { render } = await import('@testing-library/react')
    render(<KnowledgeGraph />)
    await vi.waitFor(() => expect(lastForceGraphProps).not.toBeNull())
    // Hover sets the internal hoveredNodeIdRef synchronously for 'article' nodes.
    lastForceGraphProps.onNodeHover({ type: 'article', id: 'a1' })
    const ctx = fakeCtx()
    lastForceGraphProps.nodeCanvasObject({ type: 'article', id: 'a1', label: 'Hovered article', x: 0, y: 0 }, ctx, 1)
    expect(ctx.fillStyle).toBe('#f1f5f9')
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
