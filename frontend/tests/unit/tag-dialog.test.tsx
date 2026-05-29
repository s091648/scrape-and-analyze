import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import type { TagOut } from '@/lib/api/tags'

vi.mock('@/lib/api/articles', () => ({
  fetchArticles: vi.fn().mockResolvedValue({ items: [], total: 0 }),
}))

vi.mock('@/lib/api/tags', () => ({
  renameTag: vi.fn(),
  deleteTag: vi.fn(),
}))

vi.mock('@/lib/providers', () => ({
  useI18n: () => ({
    locale: 'en',
    t: (key: string, params?: Record<string, any>) => {
      const map: Record<string, string> = {
        'tags.renameTag': 'Rename tag',
        'tags.deleteTag': 'Delete tag',
        'tags.articleCount': `${params?.count ?? 0} articles`,
        'tags.deleteTagConfirm': `Delete "${params?.name ?? ''}"?`,
        'tags.deleteTagDesc': 'This cannot be undone.',
        'tags.noArticles': 'No articles',
        'admin.cancel': 'Cancel',
        'admin.delete': 'Delete',
        'admin.save': 'Save',
        'home.pageOf': `Page ${params?.page ?? 1} of ${params?.total ?? 1}`,
      }
      return map[key] ?? key
    },
  }),
}))

const tag: TagOut = { id: 't1', name: 'Transformer', article_count: 10 }

describe('TagDialog', () => {
  const defaultProps = {
    tag,
    topicId: 'topic-1',
    isAdmin: true,
    token: 'test-token',
    open: true,
    onOpenChange: vi.fn(),
    onRenamed: vi.fn(),
    onDeleted: vi.fn(),
  }

  beforeEach(() => vi.clearAllMocks())

  it('renders tag name as title', async () => {
    const { TagDialog } = await import('@/components/features/tags/tag-dialog')
    render(<TagDialog {...defaultProps} />)
    expect(screen.getByText('Transformer')).toBeInTheDocument()
  })

  it('shows article count', async () => {
    const { TagDialog } = await import('@/components/features/tags/tag-dialog')
    render(<TagDialog {...defaultProps} />)
    expect(screen.getByText('10 articles')).toBeInTheDocument()
  })

  it('shows rename and delete buttons for admin', async () => {
    const { TagDialog } = await import('@/components/features/tags/tag-dialog')
    render(<TagDialog {...defaultProps} />)
    expect(screen.getByLabelText('Rename tag')).toBeInTheDocument()
    expect(screen.getByLabelText('Delete tag')).toBeInTheDocument()
  })

  it('hides admin buttons for non-admin', async () => {
    const { TagDialog } = await import('@/components/features/tags/tag-dialog')
    render(<TagDialog {...defaultProps} isAdmin={false} />)
    expect(screen.queryByLabelText('Rename tag')).not.toBeInTheDocument()
    expect(screen.queryByLabelText('Delete tag')).not.toBeInTheDocument()
  })

  it('enters edit mode when rename button clicked', async () => {
    const { TagDialog } = await import('@/components/features/tags/tag-dialog')
    render(<TagDialog {...defaultProps} />)
    fireEvent.click(screen.getByLabelText('Rename tag'))
    // Should show an input with the tag name
    const input = screen.getByDisplayValue('Transformer')
    expect(input).toBeInTheDocument()
  })

  it('shows delete confirmation when delete button clicked', async () => {
    const { TagDialog } = await import('@/components/features/tags/tag-dialog')
    render(<TagDialog {...defaultProps} />)
    fireEvent.click(screen.getByLabelText('Delete tag'))
    expect(screen.getByText(/Delete "Transformer"\?/)).toBeInTheDocument()
  })

  it('calls deleteTag and onDeleted when delete confirmed', async () => {
    const { deleteTag } = await import('@/lib/api/tags')
    vi.mocked(deleteTag).mockResolvedValue(undefined)
    const onDeleted = vi.fn()
    const { TagDialog } = await import('@/components/features/tags/tag-dialog')
    render(<TagDialog {...defaultProps} onDeleted={onDeleted} />)
    fireEvent.click(screen.getByLabelText('Delete tag'))
    fireEvent.click(screen.getByText('Delete'))
    await waitFor(() => {
      expect(deleteTag).toHaveBeenCalledWith('t1', 'test-token')
      expect(onDeleted).toHaveBeenCalledWith('t1')
    })
  })

  it('calls renameTag when rename is submitted', async () => {
    const { renameTag } = await import('@/lib/api/tags')
    vi.mocked(renameTag).mockResolvedValue({ id: 't1', name: 'Diffusion', article_count: 10 })
    const onRenamed = vi.fn()
    const { TagDialog } = await import('@/components/features/tags/tag-dialog')
    render(<TagDialog {...defaultProps} onRenamed={onRenamed} />)
    fireEvent.click(screen.getByLabelText('Rename tag'))
    const input = screen.getByDisplayValue('Transformer')
    fireEvent.change(input, { target: { value: 'Diffusion' } })
    fireEvent.keyDown(input, { key: 'Enter' })
    await waitFor(() => {
      expect(renameTag).toHaveBeenCalledWith('t1', 'Diffusion', 'test-token')
      expect(onRenamed).toHaveBeenCalledWith('t1', 'Diffusion')
    })
  })

  // ── T030: Tag dialog rename calls API and shows updated name ────────────────

  it('shows updated name after successful rename', async () => {
    const { renameTag } = await import('@/lib/api/tags')
    vi.mocked(renameTag).mockResolvedValue({ id: 't1', name: 'Diffusion', article_count: 10 })
    const onRenamed = vi.fn()
    const { TagDialog } = await import('@/components/features/tags/tag-dialog')
    render(<TagDialog {...defaultProps} onRenamed={onRenamed} />)
    fireEvent.click(screen.getByLabelText('Rename tag'))
    const input = screen.getByDisplayValue('Transformer')
    fireEvent.change(input, { target: { value: 'Diffusion' } })
    fireEvent.keyDown(input, { key: 'Enter' })
    await waitFor(() => {
      expect(onRenamed).toHaveBeenCalledWith('t1', 'Diffusion')
    })
  })

  // ── T031: Tag dialog error handling on delete failure ────────────────────────

  it('handles deleteTag API failure gracefully', async () => {
    const { deleteTag } = await import('@/lib/api/tags')
    vi.mocked(deleteTag).mockRejectedValue(new Error('Network error'))
    const onDeleted = vi.fn()
    const { TagDialog } = await import('@/components/features/tags/tag-dialog')
    render(<TagDialog {...defaultProps} onDeleted={onDeleted} />)
    fireEvent.click(screen.getByLabelText('Delete tag'))
    fireEvent.click(screen.getByText('Delete'))
    await waitFor(() => {
      expect(deleteTag).toHaveBeenCalledWith('t1', 'test-token')
    })
    // onDeleted should NOT be called on failure
    expect(onDeleted).not.toHaveBeenCalled()
  })

  // ── T067: Tag dialog error handling on rename failure ───────────────────────

  it('handles renameTag API failure gracefully', async () => {
    const { renameTag } = await import('@/lib/api/tags')
    vi.mocked(renameTag).mockRejectedValue(new Error('Server error'))
    const onRenamed = vi.fn()
    const { TagDialog } = await import('@/components/features/tags/tag-dialog')
    render(<TagDialog {...defaultProps} onRenamed={onRenamed} />)
    fireEvent.click(screen.getByLabelText('Rename tag'))
    const input = screen.getByDisplayValue('Transformer')
    fireEvent.change(input, { target: { value: 'Diffusion' } })
    fireEvent.keyDown(input, { key: 'Enter' })
    await waitFor(() => {
      expect(renameTag).toHaveBeenCalledWith('t1', 'Diffusion', 'test-token')
    })
    // onRenamed should NOT be called on failure
    expect(onRenamed).not.toHaveBeenCalled()
  })
})
