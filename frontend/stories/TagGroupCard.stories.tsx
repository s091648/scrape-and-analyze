import type { Meta, StoryObj } from '@storybook/nextjs-vite'
import React from 'react'
import { DndContext } from '@dnd-kit/core'
import { TagGroupCard } from '../components/features/tags/tag-group-card'
import type { TagGroupOut } from '../lib/api/tags'

const mockGroup: TagGroupOut = {
  id: 'group-1',
  name: 'machine_learning',
  display_name: 'Machine Learning',
  description: 'Core ML methodologies and architectures.',
  color_hex: '#6366f1',
  topic_id: 'topic-1',
  tags: [
    { id: 'tag-1', name: 'Transformer', article_count: 48 },
    { id: 'tag-2', name: 'Diffusion Model', article_count: 31 },
    { id: 'tag-3', name: 'Reinforcement Learning', article_count: 27 },
    { id: 'tag-4', name: 'Fine-tuning', article_count: 22 },
    { id: 'tag-5', name: 'Quantization', article_count: 15 },
    { id: 'tag-6', name: 'LoRA', article_count: 12 },
  ],
  similar_groups: [{ id: 'group-2', similarity_score: 0.94 }],
}

const meta: Meta<typeof TagGroupCard> = {
  title: 'Features/Tags/TagGroupCard',
  component: TagGroupCard,
  decorators: [
    (Story) => (
      <DndContext>
        <div className="max-w-xl p-4">
          <Story />
        </div>
      </DndContext>
    ),
  ],
  args: {
    group: mockGroup,
    isAdmin: true,
    token: 'mock-token',
    pendingIncomingTagIds: new Set(),
    isMergeMode: false,
    isMergeSource: false,
    onDeleted: () => {},
    onTagRenamed: () => {},
    onTagDeleted: () => {},
    onGroupUpdated: () => {},
    onMergeRequested: () => {},
    onMergeTargetSelected: () => {},
  },
}
export default meta
type Story = StoryObj<typeof TagGroupCard>

export const Default: Story = {}

export const ReadOnly: Story = {
  args: {
    isAdmin: false,
    token: undefined,
  },
}

export const MergeMode: Story = {
  name: 'Merge Mode (target overlay)',
  args: {
    isMergeMode: true,
  },
}

export const MergeSource: Story = {
  name: 'Merge Source (ring highlight)',
  args: {
    isMergeSource: true,
  },
}

export const WithPendingTags: Story = {
  args: {
    pendingIncomingTagIds: new Set(['tag-2', 'tag-4']),
  },
}

export const NoColor: Story = {
  args: {
    group: { ...mockGroup, color_hex: null, description: null },
  },
}

export const ManyTags: Story = {
  args: {
    group: {
      ...mockGroup,
      tags: Array.from({ length: 20 }, (_, i) => ({
        id: `tag-${i}`,
        name: `Tag ${i + 1}`,
        article_count: Math.max(1, 50 - i * 2),
      })),
    },
  },
}
