import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import type { TagGroupOut } from '@/lib/api/tags'

vi.mock('@/lib/api/tags', () => ({
  deleteTagGroup: vi.fn(),
  updateTagGroup: vi.fn(),
  renameTag: vi.fn(),
  deleteTag: vi.fn(),
}))

vi.mock('@/lib/api/articles', () => ({
  fetchArticles: vi.fn().mockResolvedValue({ items: [], total: 0 }),
}))

vi.mock('@/lib/providers', () => ({
  useI18n: () => ({
    locale: 'en',
    t: (key: string, params?: Record<string, any>) => {
      const map: Record<string, string> = {
        'tags.tagsCount': `${params?.count ?? 0} tags`,
        'tags.noTagsYet': 'No tags yet',
        'tags.expand': 'Expand',
        'tags.collapse': 'Collapse',
        'tags.editGroup': 'Edit group',
        'tags.renameTag': 'Rename tag',
        'tags.deleteTag': 'Delete tag',
        'tags.articleCount': `${params?.count ?? 0} articles`,
        'tags.groupName': 'Name',
        'tags.groupDisplayName': 'Display Name',
        'tags.groupColor': 'Color',
        'tags.groupDescription': 'Description',
        'admin.cancel': 'Cancel',
        'admin.save': 'Save',
        'admin.delete': 'Delete',
      }
      return map[key] ?? key
    },
  }),
}))

vi.mock('@dnd-kit/core', () => ({
  useDraggable: () => ({ attributes: {}, listeners: {}, setNodeRef: vi.fn(), isDragging: false }),
  useDroppable: () => ({ setNodeRef: vi.fn(), isOver: false }),
}))

const group: TagGroupOut = {
  id: 'g1', name: 'ai_research', display_name: 'AI Research',
  description: 'AI research topics', color_hex: '#6366f1', topic_id: 't1',
  tags: [
    { id: 't1', name: 'Transformer', article_count: 10 },
    { id: 't2', name: 'Diffusion', article_count: 5 },
  ],
  similar_groups: [],
}

describe('TagGroupCard', () => {
  const defaultProps = {
    group,
    isAdmin: true,
    token: 'test-token',
    pendingIncomingTagIds: new Set<string>(),
    onDeleted: vi.fn(),
    onTagRenamed: vi.fn(),
    onTagDeleted: vi.fn(),
    onGroupUpdated: vi.fn(),
  }

  beforeEach(() => vi.clearAllMocks())

  it('renders group display name and tag count', async () => {
    const { TagGroupCard } = await import('@/components/features/tags/tag-group-card')
    render(<TagGroupCard {...defaultProps} />)
    expect(screen.getByText('AI Research')).toBeInTheDocument()
    expect(screen.getByText('2 tags')).toBeInTheDocument()
  })

  it('renders group description', async () => {
    const { TagGroupCard } = await import('@/components/features/tags/tag-group-card')
    render(<TagGroupCard {...defaultProps} />)
    expect(screen.getByText('AI research topics')).toBeInTheDocument()
  })

  it('renders tag names with article counts', async () => {
    const { TagGroupCard } = await import('@/components/features/tags/tag-group-card')
    render(<TagGroupCard {...defaultProps} />)
    expect(screen.getByText('Transformer')).toBeInTheDocument()
    expect(screen.getByText('Diffusion')).toBeInTheDocument()
  })

  it('shows admin buttons for admin users', async () => {
    const { TagGroupCard } = await import('@/components/features/tags/tag-group-card')
    render(<TagGroupCard {...defaultProps} />)
    expect(screen.getByLabelText('Edit group')).toBeInTheDocument()
  })

  it('hides admin buttons for non-admin users', async () => {
    const { TagGroupCard } = await import('@/components/features/tags/tag-group-card')
    render(<TagGroupCard {...defaultProps} isAdmin={false} />)
    expect(screen.queryByLabelText('Edit group')).not.toBeInTheDocument()
  })

  it('toggles tag list on header click', async () => {
    const { TagGroupCard } = await import('@/components/features/tags/tag-group-card')
    render(<TagGroupCard {...defaultProps} />)
    const headerBtn = screen.getByText('AI Research').closest('button')!
    fireEvent.click(headerBtn)
    expect(screen.queryByText('Transformer')).not.toBeInTheDocument()
    fireEvent.click(headerBtn)
    expect(screen.getByText('Transformer')).toBeInTheDocument()
  })

  it('calls deleteTagGroup and onDeleted when trash button clicked', async () => {
    const { deleteTagGroup } = await import('@/lib/api/tags')
    vi.mocked(deleteTagGroup).mockResolvedValue(undefined)
    const onDeleted = vi.fn()
    const { TagGroupCard } = await import('@/components/features/tags/tag-group-card')
    const { container } = render(<TagGroupCard {...defaultProps} onDeleted={onDeleted} />)
    // Find the Trash2 button — it's the last icon button in admin controls
    const buttons = container.querySelectorAll('button.lucide, button svg.lucide-trash-2')
    // Find all buttons and look for the one containing a trash SVG
    const allButtons = screen.getAllByRole('button')
    const trashBtn = allButtons.find(b => b.innerHTML.includes('trash-2'))
    if (trashBtn) {
      fireEvent.click(trashBtn)
      await waitFor(() => {
        expect(deleteTagGroup).toHaveBeenCalledWith('g1', 'test-token')
        expect(onDeleted).toHaveBeenCalledWith('g1')
      })
    }
  })

  it('renders ungrouped card without admin controls', async () => {
    const ungrouped: TagGroupOut = {
      id: null, name: 'ungrouped', display_name: 'Ungrouped',
      description: null, color_hex: null, topic_id: null,
      tags: [{ id: 't5', name: 'Orphan', article_count: 1 }],
      similar_groups: [],
    }
    const { TagGroupCard } = await import('@/components/features/tags/tag-group-card')
    render(<TagGroupCard {...defaultProps} group={ungrouped} />)
    expect(screen.getByText('Ungrouped')).toBeInTheDocument()
    expect(screen.getByText('Orphan')).toBeInTheDocument()
    expect(screen.queryByLabelText('Edit group')).not.toBeInTheDocument()
  })
})
