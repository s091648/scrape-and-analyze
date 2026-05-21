import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import type { TagGroupOut } from '@/lib/api/tags'

const groups: TagGroupOut[] = [
  {
    id: 'g1', name: 'research', display_name: 'Research Methods',
    description: null, color_hex: '#6366f1', topic_id: 't1',
    tags: [
      { id: 'tag1', name: 'Transformer', article_count: 10 },
      { id: 'tag2', name: 'Diffusion', article_count: 5 },
    ],
  },
  {
    id: 'g2', name: 'applications', display_name: 'Applications',
    description: null, color_hex: null, topic_id: 't1',
    tags: [
      { id: 'tag3', name: 'Computer Vision', article_count: 8 },
    ],
  },
]

describe('GroupedTagSelect', () => {
  it('renders a trigger button with label', async () => {
    const { GroupedTagSelect } = await import('@/components/features/articles/grouped-tag-select')
    render(<GroupedTagSelect label="Tag" groups={groups} selected={[]} onChange={() => {}} />)
    expect(screen.getByRole('button', { name: /tag/i })).toBeInTheDocument()
  })

  it('shows selected count badge when tags are selected', async () => {
    const { GroupedTagSelect } = await import('@/components/features/articles/grouped-tag-select')
    render(<GroupedTagSelect label="Tag" groups={groups} selected={['Transformer']} onChange={() => {}} />)
    expect(screen.getByText('1')).toBeInTheDocument()
  })

  it('clicking group header selects all tags in that group', async () => {
    const onChange = vi.fn()
    const { GroupedTagSelect } = await import('@/components/features/articles/grouped-tag-select')
    render(<GroupedTagSelect label="Tag" groups={groups} selected={[]} onChange={onChange} />)
    // Open popover
    fireEvent.click(screen.getByRole('button', { name: /tag/i }))
    // Click group header
    fireEvent.click(screen.getByText('Research Methods'))
    expect(onChange).toHaveBeenCalledWith(['Transformer', 'Diffusion'])
  })

  it('clicking group header when all selected deselects all', async () => {
    const onChange = vi.fn()
    const { GroupedTagSelect } = await import('@/components/features/articles/grouped-tag-select')
    render(<GroupedTagSelect label="Tag" groups={groups} selected={['Transformer', 'Diffusion']} onChange={onChange} />)
    fireEvent.click(screen.getByRole('button', { name: /tag/i }))
    fireEvent.click(screen.getByText('Research Methods'))
    expect(onChange).toHaveBeenCalledWith([])
  })

  it('search filters to matching tag names and shows their group', async () => {
    const { GroupedTagSelect } = await import('@/components/features/articles/grouped-tag-select')
    render(<GroupedTagSelect label="Tag" groups={groups} selected={[]} onChange={() => {}} />)
    fireEvent.click(screen.getByRole('button', { name: /tag/i }))
    fireEvent.change(screen.getByPlaceholderText(/search/i), { target: { value: 'Transformer' } })
    // Tag match is visible
    expect(screen.getByText('Transformer')).toBeInTheDocument()
    // Its parent group is visible even though "Research Methods" doesn't match
    expect(screen.getByText('Research Methods')).toBeInTheDocument()
    // Non-matching group is hidden
    expect(screen.queryByText('Applications')).not.toBeInTheDocument()
  })

  it('shows empty text when search has no matches', async () => {
    const { GroupedTagSelect } = await import('@/components/features/articles/grouped-tag-select')
    render(<GroupedTagSelect label="Tag" groups={groups} selected={[]} onChange={() => {}} emptyText="No tags found" />)
    fireEvent.click(screen.getByRole('button', { name: /tag/i }))
    fireEvent.change(screen.getByPlaceholderText(/search/i), { target: { value: 'xyznonexistent' } })
    expect(screen.getByText('No tags found')).toBeInTheDocument()
  })
})
