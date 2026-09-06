import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import TagsPageContent from '@/app/tags/tags-page-content'

const { mockFetchTagGroups } = vi.hoisted(() => ({ mockFetchTagGroups: vi.fn() }))
vi.mock('@/lib/api/tags', () => ({
  fetchTagGroups: mockFetchTagGroups,
  fetchTagGroup: vi.fn(),
  fetchPendingSuggestions: vi.fn().mockResolvedValue([]),
  createTagGroup: vi.fn(),
  moveTag: vi.fn(),
  batchMoveTags: vi.fn(),
  approveSuggestionsBatch: vi.fn(),
  reorderTagGroups: vi.fn(),
  mergeTagGroups: vi.fn(),
}))

vi.mock('next-auth/react', () => ({
  useSession: () => ({ data: { accessToken: 'test-token', user: { role: 'user' } }, status: 'authenticated' }),
}))

vi.mock('@/lib/providers', () => ({
  useTopic: () => ({ selectedTopic: { id: 'topic-1', tag_mode: 'unsupervised' }, refresh: vi.fn() }),
  useI18n: () => ({ t: (k: string) => k, locale: 'en' }),
}))

// Full drag-and-drop machinery is E2E territory — a passthrough keeps the seed-guard test
// focused on data flow, same pattern as weekly-report-widget.test.tsx.
vi.mock('@dnd-kit/core', () => ({
  DndContext: ({ children }: any) => children,
  DragOverlay: ({ children }: any) => children,
  MouseSensor: vi.fn(),
  TouchSensor: vi.fn(),
  useSensor: vi.fn(),
  useSensors: vi.fn(() => []),
}))

vi.mock('@/components/features/tags/tag-group-card', () => ({
  TagGroupCard: ({ group }: any) => <div data-testid="tag-group-card">{group.display_name}</div>,
}))
vi.mock('@/components/features/tags/pending-suggestions', () => ({ PendingSuggestions: () => null }))
vi.mock('@/components/features/tags/pending-changes-panel', () => ({ PendingChangesPanel: () => null }))
vi.mock('@/components/features/tags/merge-group-dialog', () => ({ MergeGroupDialog: () => null }))

const seededGroup = {
  id: 'seeded-group-1', name: 'seeded_group', display_name: 'Seeded Group',
  description: null, color_hex: '#6366f1', topic_id: 'topic-1',
  tags: [], similar_groups: [],
}

const clientFetchedGroup = {
  ...seededGroup, id: 'client-group-1', name: 'client_group', display_name: 'Client Fetched Group',
}

beforeEach(() => {
  vi.clearAllMocks()
  mockFetchTagGroups.mockResolvedValue([clientFetchedGroup])
})

describe('TagsPageContent — SSR seed guard (021-ssr-public-pages)', () => {
  it('does NOT call fetchTagGroups on mount when seeded with initialGroups', async () => {
    render(<TagsPageContent initialGroups={[seededGroup]} />)

    expect(await screen.findByText('Seeded Group')).toBeInTheDocument()
    await new Promise(r => setTimeout(r, 50))
    expect(mockFetchTagGroups).not.toHaveBeenCalled()
  })

  it('DOES call fetchTagGroups on mount when not seeded (undefined initialGroups)', async () => {
    render(<TagsPageContent />)

    await waitFor(() => expect(mockFetchTagGroups).toHaveBeenCalledTimes(1))
    expect(await screen.findByText('Client Fetched Group')).toBeInTheDocument()
  })

  it('treats an empty seeded array as real seeded data (still skips the mount fetch)', async () => {
    render(<TagsPageContent initialGroups={[]} />)
    await new Promise(r => setTimeout(r, 50))
    expect(mockFetchTagGroups).not.toHaveBeenCalled()
  })
})
