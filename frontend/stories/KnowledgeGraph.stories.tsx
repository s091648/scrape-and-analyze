import type { Meta, StoryObj } from '@storybook/nextjs-vite'
import React from 'react'
import { SessionProvider } from 'next-auth/react'
import { KnowledgeGraph } from '../components/features/graph/knowledge-graph'

const meta: Meta<typeof KnowledgeGraph> = {
  title: 'Features/Graph/KnowledgeGraph',
  component: KnowledgeGraph,
  decorators: [
    (Story) => (
      <SessionProvider session={null}>
        <div style={{ height: 600 }}>
          <Story />
        </div>
      </SessionProvider>
    ),
  ],
  parameters: {
    nextjs: {
      appDirectory: true,
      navigation: { pathname: '/graph' },
    },
  },
}
export default meta
type Story = StoryObj<typeof KnowledgeGraph>

// Guests see the built-in GUEST_GRAPH — no API calls are made.
export const GuestView: Story = {}
