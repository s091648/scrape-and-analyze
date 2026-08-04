import type { Meta, StoryObj } from '@storybook/nextjs-vite'
import React from 'react'
import { SessionProvider } from 'next-auth/react'
import { PinnedArticleProvider } from '../lib/providers/pinned-article-provider'
import { FloatChatProvider } from '../lib/providers/float-chat-provider'
import { FloatingChatbotWrapper } from '../components/features/chat/FloatingChatbotWrapper'
import { withDarkMode } from './decorators'

const mockSession = {
  user: { name: 'Test User', email: 'test@example.com' },
  expires: '2027-01-01T00:00:00.000Z',
}

const meta: Meta<typeof FloatingChatbotWrapper> = {
  title: 'Features/Chat/FloatingChatbotWrapper',
  component: FloatingChatbotWrapper,
  decorators: [
    (Story) => (
      <SessionProvider session={mockSession}>
        <PinnedArticleProvider>
          <FloatChatProvider>
            <Story />
          </FloatChatProvider>
        </PinnedArticleProvider>
      </SessionProvider>
    ),
  ],
  parameters: {
    nextjs: { appDirectory: true },
    layout: 'fullscreen',
  },
}
export default meta
type Story = StoryObj<typeof FloatingChatbotWrapper>

// Smoke test — verifies the wrapper mounts without errors.
// For rich visual states (conversation, loading, sources) see FloatingChatbotPanel.stories.tsx
export const Default: Story = {}

export const DefaultDark: Story = {
  name: 'Default (Dark)',
  decorators: [withDarkMode],
}
