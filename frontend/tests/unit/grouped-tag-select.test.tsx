import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import type { TagGroupOut } from '@/lib/api/tags'

const groups: TagGroupOut[] = [
  {
    id: 'g1', name: 'research', display_name: 'Research Methods',
    description: null, color_hex: '#6366f1', topic_id: 't1',
    similar_groups: [],
    tags: [
      { id: 'tag1', name: 'Transformer', article_count: 10 },
      { id: 'tag2', name: 'Diffusion', article_count: 5 },
    ],
  },
  {
    id: 'g2', name: 'applications', display_name: 'Applications',
    description: null, color_hex: null, topic_id: 't1',
    similar_groups: [],
    tags: [
      { id: 'tag3', name: 'Computer Vision', article_count: 8 },
    ],
  },
]

const defaultProps = {
  label: 'Tag',
  groups,
  selectedTags: [] as string[],
  selectedGroups: [] as string[],
  onTagsChange: () => {},
  onGroupsChange: () => {},
}

describe('GroupedTagSelect', () => {
  it('renders a trigger button with label', async () => {
    const { GroupedTagSelect } = await import('@/components/features/articles/grouped-tag-select')
    render(<GroupedTagSelect {...defaultProps} />)
    expect(screen.getByRole('button', { name: /tag/i })).toBeInTheDocument()
  })

  it('shows badge count for selected tags', async () => {
    const { GroupedTagSelect } = await import('@/components/features/articles/grouped-tag-select')
    render(<GroupedTagSelect {...defaultProps} selectedTags={['Transformer']} />)
    expect(screen.getByText('1')).toBeInTheDocument()
  })

  it('shows badge count summing selected groups and tags', async () => {
    const { GroupedTagSelect } = await import('@/components/features/articles/grouped-tag-select')
    render(<GroupedTagSelect {...defaultProps} selectedGroups={['research']} selectedTags={['Computer Vision']} />)
    expect(screen.getByText('2')).toBeInTheDocument()
  })

  it('clicking group header calls onGroupsChange with that group name', async () => {
    const onGroupsChange = vi.fn()
    const { GroupedTagSelect } = await import('@/components/features/articles/grouped-tag-select')
    render(<GroupedTagSelect {...defaultProps} onGroupsChange={onGroupsChange} />)
    fireEvent.click(screen.getByRole('button', { name: /tag/i }))
    fireEvent.click(screen.getByText('Research Methods'))
    expect(onGroupsChange).toHaveBeenCalledWith(['research'])
  })

  it('clicking group header when already selected removes it', async () => {
    const onGroupsChange = vi.fn()
    const { GroupedTagSelect } = await import('@/components/features/articles/grouped-tag-select')
    render(<GroupedTagSelect {...defaultProps} selectedGroups={['research']} onGroupsChange={onGroupsChange} />)
    fireEvent.click(screen.getByRole('button', { name: /tag/i }))
    fireEvent.click(screen.getByText('Research Methods'))
    expect(onGroupsChange).toHaveBeenCalledWith([])
  })

  it('search filters to matching tag names and shows their group', async () => {
    const { GroupedTagSelect } = await import('@/components/features/articles/grouped-tag-select')
    render(<GroupedTagSelect {...defaultProps} />)
    fireEvent.click(screen.getByRole('button', { name: /tag/i }))
    fireEvent.change(screen.getByPlaceholderText(/search/i), { target: { value: 'Transformer' } })
    expect(screen.getByText('Transformer')).toBeInTheDocument()
    expect(screen.getByText('Research Methods')).toBeInTheDocument()
    expect(screen.queryByText('Applications')).not.toBeInTheDocument()
  })

  it('shows empty text when search has no matches', async () => {
    const { GroupedTagSelect } = await import('@/components/features/articles/grouped-tag-select')
    render(<GroupedTagSelect {...defaultProps} emptyText="No tags found" />)
    fireEvent.click(screen.getByRole('button', { name: /tag/i }))
    fireEvent.change(screen.getByPlaceholderText(/search/i), { target: { value: 'xyznonexistent' } })
    expect(screen.getByText('No tags found')).toBeInTheDocument()
  })
})
