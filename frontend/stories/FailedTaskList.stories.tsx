import type { Meta, StoryObj } from '@storybook/nextjs-vite'
import { FailedTaskList } from '../components/features/monitoring/failed-task-list'

const meta: Meta<typeof FailedTaskList> = {
  title: 'Features/Monitoring/FailedTaskList',
  component: FailedTaskList,
}
export default meta
type Story = StoryObj<typeof FailedTaskList>

export const WithFailedTasks: Story = {
  args: {
    items: [
      {
        id: '1',
        task_type: 'analyze',
        article_url: 'https://arxiv.org/abs/2405.00001',
        exception_type: 'RateLimitError',
        exception_message: 'Rate limit exceeded. Retry after 60s.',
        failed_at: '2026-05-17T01:00:00Z',
        resolved: false,
      },
      {
        id: '2',
        task_type: 'scrape',
        article_url: 'https://example.com/blog/post-1',
        exception_type: 'ConnectionError',
        exception_message: 'Connection timed out after 30s',
        failed_at: '2026-05-17T02:30:00Z',
        resolved: false,
      },
      {
        id: '3',
        task_type: 'translate',
        article_url: null,
        exception_type: null,
        exception_message: null,
        failed_at: null,
        resolved: true,
      },
    ],
  },
}

export const SingleTask: Story = {
  args: {
    items: [
      {
        id: '1',
        task_type: 'analyze',
        article_url: 'https://arxiv.org/abs/2405.99999',
        exception_type: 'APIError',
        exception_message: 'LLM provider returned 503 Service Unavailable',
        failed_at: '2026-05-17T10:00:00Z',
        resolved: false,
      },
    ],
  },
}

export const Empty: Story = {
  args: { items: [] },
}
