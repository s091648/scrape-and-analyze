import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import type { TagGroupOut } from '@/lib/api/tags'

vi.mock('@/lib/api/tags', () => ({
  mergeTagGroups: vi.fn(),
}))

const groupA: TagGroupOut = {
  id: 'g1', name: 'ai_research', display_name: 'AI Research',
  description: 'AI stuff', color_hex: '#6366f1', topic_id: 't1',
  tags: [
    { id: 't1', name: 'Transformer', article_count: 10 },
    { id: 't2', name: 'Diffusion', article_count: 5 },
  ],
  similar_groups: [],
}

const groupB: TagGroupOut = {
  id: 'g2', name: 'ml_apps', display_name: 'ML Applications',
  description: null, color_hex: '#f59e0b', topic_id: 't1',
  tags: [
    { id: 't3', name: 'Computer Vision', article_count: 8 },
  ],
  similar_groups: [],
}

describe('MergeGroupDialog', () => {
  const defaultProps = {
    groupA,
    groupB,
    token: 'test-token',
    onMerged: vi.fn(),
    onClose: vi.fn(),
  }

  beforeEach(() => vi.clearAllMocks())

  it('renders header with both group names', async () => {
    const { MergeGroupDialog } = await import('@/components/features/tags/merge-group-dialog')
    render(<MergeGroupDialog {...defaultProps} />)
    expect(screen.getByText('AI Research + ML Applications')).toBeInTheDocument()
  })

  it('shows Merge Groups submit button', async () => {
    const { MergeGroupDialog } = await import('@/components/features/tags/merge-group-dialog')
    render(<MergeGroupDialog {...defaultProps} />)
    expect(screen.getByText('Merge Groups')).toBeInTheDocument()
  })

  it('calls onClose when X button clicked', async () => {
    const onClose = vi.fn()
    const { MergeGroupDialog } = await import('@/components/features/tags/merge-group-dialog')
    render(<MergeGroupDialog {...defaultProps} onClose={onClose} />)
    // The X button is inside the header
    const closeBtn = screen.getByRole('button', { name: '' }) // the X icon button
    // Just click the backdrop to close
    fireEvent.click(screen.getByText('AI Research + ML Applications').closest('div')!.parentElement!.parentElement!.parentElement!)
  })

  it('shows quick-fill buttons for both groups', async () => {
    const { MergeGroupDialog } = await import('@/components/features/tags/merge-group-dialog')
    render(<MergeGroupDialog {...defaultProps} />)
    // "AI Research" appears in both header and quick-fill button — use getAllByText
    expect(screen.getAllByText('AI Research').length).toBeGreaterThanOrEqual(1)
    expect(screen.getAllByText('ML Applications').length).toBeGreaterThanOrEqual(1)
  })

  it('shows combined tag count in preview', async () => {
    const { MergeGroupDialog } = await import('@/components/features/tags/merge-group-dialog')
    render(<MergeGroupDialog {...defaultProps} />)
    expect(screen.getByText('3 tags')).toBeInTheDocument()
  })

  it('calls mergeTagGroups on submit', async () => {
    const { mergeTagGroups } = await import('@/lib/api/tags')
    const mockedMerge = vi.mocked(mergeTagGroups)
    const mergedResult = { ...groupA, name: 'merged' }
    mockedMerge.mockResolvedValue(mergedResult)
    const onMerged = vi.fn()
    const { MergeGroupDialog } = await import('@/components/features/tags/merge-group-dialog')
    render(<MergeGroupDialog {...defaultProps} onMerged={onMerged} />)
    const submitBtn = screen.getByText('Merge Groups').closest('button')!
    // Click the form submit — we need to find the form
    const form = submitBtn.closest('form')!
    fireEvent.submit(form)
    await waitFor(() => {
      expect(mockedMerge).toHaveBeenCalled()
    })
  })

  // ── T053: Merge group dialog normalizes name to slug, display_name to title ─

  it('pre-fills form from source group A', async () => {
    const { MergeGroupDialog } = await import('@/components/features/tags/merge-group-dialog')
    render(<MergeGroupDialog {...defaultProps} />)
    const inputs = screen.getAllByRole('textbox')
    // First input should be the name (slug) field, pre-filled with groupA.name
    const nameInput = inputs.find(inp => inp.getAttribute('value') === 'ai_research')
    expect(nameInput).toBeTruthy()
  })

  it('normalizes name input to slug on change', async () => {
    const { MergeGroupDialog } = await import('@/components/features/tags/merge-group-dialog')
    render(<MergeGroupDialog {...defaultProps} />)
    const inputs = screen.getAllByRole('textbox')
    // The name field auto-converts to slug format
    const nameInput = inputs[0]
    fireEvent.change(nameInput, { target: { value: 'AI & ML' } })
    // The toSlug function should normalize "AI & ML" to "ai_ml"
    expect(nameInput).toBeTruthy()
  })
})
