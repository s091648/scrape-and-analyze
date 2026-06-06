import type { Meta, StoryObj } from '@storybook/nextjs-vite'
import { ErrorBoundary } from '../components/common/error-boundary'

function ThrowOnRender(): never {
  throw new Error('Simulated render error')
}

const meta: Meta<typeof ErrorBoundary> = {
  title: 'Common/ErrorBoundary',
  component: ErrorBoundary,
}
export default meta
type Story = StoryObj<typeof ErrorBoundary>

export const Normal: Story = {
  args: {
    children: <p className="p-4 text-sm text-muted-foreground">Content renders normally when no error occurs.</p>,
  },
}

export const ErrorState: Story = {
  args: {
    children: <ThrowOnRender />,
  },
}
