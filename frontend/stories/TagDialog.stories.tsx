import type { Meta, StoryObj } from '@storybook/nextjs-vite'
import React, { useState } from 'react'
import { TagDialog } from '../components/features/tags/tag-dialog'
import { Button } from '../components/ui/button'
import type { TagOut } from '../lib/api/tags'

const mockTag: TagOut = {
  id: 'tag-1',
  name: 'Transformer',
  article_count: 48,
}

function TagDialogWrapper(props: React.ComponentProps<typeof TagDialog>) {
  const [open, setOpen] = useState(false)
  return (
    <>
      <Button onClick={() => setOpen(true)}>Open Tag Dialog</Button>
      <TagDialog {...props} open={open} onOpenChange={setOpen} />
    </>
  )
}

const meta: Meta<typeof TagDialog> = {
  title: 'Features/Tags/TagDialog',
  component: TagDialog,
  render: (args) => <TagDialogWrapper {...args} />,
  decorators: [
    (Story) => (
      <div className="p-8">
        <Story />
      </div>
    ),
  ],
  args: {
    tag: mockTag,
    topicId: 'topic-1',
    isAdmin: true,
    token: 'mock-token',
    open: false,
    onOpenChange: () => {},
    onRenamed: () => {},
    onDeleted: () => {},
  },
}
export default meta
type Story = StoryObj<typeof TagDialog>

export const Default: Story = {}

export const ReadOnly: Story = {
  args: {
    isAdmin: false,
    token: undefined,
  },
}

export const LowArticleCount: Story = {
  args: {
    tag: { id: 'tag-2', name: 'Sparse Autoencoder', article_count: 3 },
  },
}
