import type { Meta, StoryObj } from '@storybook/nextjs-vite'
import React from 'react'
import { SessionProvider } from 'next-auth/react'
import { InlineQABarWrapper } from '../components/features/chat/InlineQABarWrapper'
import { PinnedReportProvider } from '../lib/providers/pinned-article-provider'
import { InlineChatProvider } from '../lib/providers/inline-chat-provider'
import { withDarkMode } from './decorators'

const mockSession = {
  user: { name: 'Test User', email: 'test@example.com' },
  expires: '2027-01-01T00:00:00.000Z',
}

const meta: Meta<typeof InlineQABarWrapper> = {
  title: 'Features/Chat/InlineQABarWrapper',
  component: InlineQABarWrapper,
  decorators: [
    (Story) => (
      <SessionProvider session={mockSession}>
        <PinnedReportProvider>
          <InlineChatProvider>
            <Story />
          </InlineChatProvider>
        </PinnedReportProvider>
      </SessionProvider>
    ),
  ],
  parameters: {
    nextjs: { appDirectory: true },
  },
}
export default meta
type Story = StoryObj<typeof InlineQABarWrapper>

// Smoke test — verifies the wrapper mounts without errors.
// For rich visual states (loading, answer, error, thinking) see AnswerDisplay.stories.tsx
export const Default: Story = {
  args: {
    placeholder: '詢問 AI：最近有哪些相關研究？',
  },
}

export const DefaultDark: Story = {
  name: 'Default (Dark)',
  args: {
    placeholder: '詢問 AI：最近有哪些相關研究？',
  },
  decorators: [withDarkMode],
}
