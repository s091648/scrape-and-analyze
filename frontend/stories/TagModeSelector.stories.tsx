import type { Meta, StoryObj } from '@storybook/nextjs-vite'
import React, { useState } from 'react'
import { TagModeSelector, type TagMode } from '../components/features/tags/tag-mode-selector'

const meta: Meta<typeof TagModeSelector> = {
  title: 'Features/Tags/TagModeSelector',
  component: TagModeSelector,
  decorators: [
    (Story) => (
      <div className="p-6">
        <Story />
      </div>
    ),
  ],
  argTypes: {
    value: {
      control: 'select',
      options: ['unsupervised', 'semi_supervised', 'supervised'],
    },
    onChange: { action: 'onChange' },
  },
}
export default meta
type Story = StoryObj<typeof TagModeSelector>

export const Unsupervised: Story = {
  args: {
    value: 'unsupervised',
  },
}

export const SemiSupervised: Story = {
  args: {
    value: 'semi_supervised',
  },
}

export const Supervised: Story = {
  args: {
    value: 'supervised',
  },
}

export const Disabled: Story = {
  args: {
    value: 'unsupervised',
    disabled: true,
  },
}

export const Interactive: Story = {
  render: () => {
    const [mode, setMode] = useState<TagMode>('unsupervised')
    return (
      <div className="space-y-2">
        <TagModeSelector value={mode} onChange={setMode} />
        <p className="text-sm text-muted-foreground">Selected: {mode}</p>
      </div>
    )
  },
}
