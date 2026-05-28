import type { Meta, StoryObj } from '@storybook/nextjs-vite'
import React from 'react'
import { PendingChangesPanel } from '../components/features/tags/pending-changes-panel'

const meta: Meta<typeof PendingChangesPanel> = {
  title: 'Features/Tags/PendingChangesPanel',
  component: PendingChangesPanel,
  decorators: [
    (Story) => (
      <div className="relative min-h-64 bg-background">
        <Story />
      </div>
    ),
  ],
  parameters: {
    layout: 'fullscreen',
  },
  args: {
    count: 3,
    confirming: false,
    onConfirm: () => {},
    onDiscard: () => {},
  },
}
export default meta
type Story = StoryObj<typeof PendingChangesPanel>

export const Default: Story = {}

export const SingleChange: Story = {
  args: { count: 1 },
}

export const ManyChanges: Story = {
  args: { count: 12 },
}

export const Confirming: Story = {
  args: { confirming: true },
}
