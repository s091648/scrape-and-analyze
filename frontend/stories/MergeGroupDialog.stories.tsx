import type { Meta, StoryObj } from '@storybook/nextjs-vite'
import React from 'react'
import { MergeGroupDialog } from '../components/features/tags/merge-group-dialog'
import type { TagGroupOut } from '../lib/api/tags'

const groupA: TagGroupOut = {
  id: 'group-1',
  name: 'machine_learning',
  display_name: 'Machine Learning',
  description: 'Core ML methodologies.',
  color_hex: '#6366f1',
  topic_id: 'topic-1',
  tags: [
    { id: 'tag-1', name: 'Transformer', article_count: 48 },
    { id: 'tag-2', name: 'Diffusion Model', article_count: 31 },
    { id: 'tag-3', name: 'Fine-tuning', article_count: 22 },
  ],
  similar_groups: [],
}

const groupB: TagGroupOut = {
  id: 'group-2',
  name: 'deep_learning',
  display_name: 'Deep Learning',
  description: 'Neural network architectures and training.',
  color_hex: '#8b5cf6',
  topic_id: 'topic-1',
  tags: [
    { id: 'tag-4', name: 'Neural Network', article_count: 55 },
    { id: 'tag-2', name: 'Diffusion Model', article_count: 31 },
    { id: 'tag-5', name: 'Backpropagation', article_count: 18 },
  ],
  similar_groups: [],
}

const meta: Meta<typeof MergeGroupDialog> = {
  title: 'Features/Tags/MergeGroupDialog',
  component: MergeGroupDialog,
  decorators: [
    (Story) => (
      <div className="relative min-h-screen bg-background">
        <Story />
      </div>
    ),
  ],
  args: {
    groupA,
    groupB,
    token: 'mock-token',
    onMerged: () => {},
    onClose: () => {},
  },
  parameters: {
    layout: 'fullscreen',
  },
}
export default meta
type Story = StoryObj<typeof MergeGroupDialog>

export const Default: Story = {}

export const NoColors: Story = {
  args: {
    groupA: { ...groupA, color_hex: null },
    groupB: { ...groupB, color_hex: null },
  },
}

export const LargeGroups: Story = {
  args: {
    groupA: {
      ...groupA,
      tags: Array.from({ length: 12 }, (_, i) => ({
        id: `a-tag-${i}`,
        name: `Alpha Tag ${i + 1}`,
        article_count: 50 - i * 3,
      })),
    },
    groupB: {
      ...groupB,
      tags: Array.from({ length: 10 }, (_, i) => ({
        id: `b-tag-${i}`,
        name: `Beta Tag ${i + 1}`,
        article_count: 40 - i * 3,
      })),
    },
  },
}
