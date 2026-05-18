import type { Meta, StoryObj } from '@storybook/nextjs-vite'
import React from 'react'
import { SessionProvider } from 'next-auth/react'
import { NavBar } from '../components/features/navigation/nav-bar'

const meta: Meta<typeof NavBar> = {
  title: 'Features/Navigation/NavBar',
  component: NavBar,
  decorators: [
    (Story) => (
      <SessionProvider session={null}>
        <div className="h-20 relative">
          <Story />
        </div>
      </SessionProvider>
    ),
  ],
  parameters: {
    nextjs: {
      appDirectory: true,
      navigation: { pathname: '/' },
    },
  },
}
export default meta
type Story = StoryObj<typeof NavBar>

export const Unauthenticated: Story = {}

export const OnGraphPage: Story = {
  parameters: {
    nextjs: {
      appDirectory: true,
      navigation: { pathname: '/graph' },
    },
  },
}

export const Authenticated: Story = {
  decorators: [
    (Story) => (
      <SessionProvider
        session={{
          user: { name: 'Jane Doe', email: 'jane@example.com' },
          expires: '2027-01-01T00:00:00.000Z',
        }}
      >
        <div className="h-20 relative">
          <Story />
        </div>
      </SessionProvider>
    ),
  ],
}
