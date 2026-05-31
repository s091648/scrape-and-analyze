import type { Meta, StoryObj } from '@storybook/nextjs-vite'
import { LogsTable } from '../components/features/monitoring/logs-table'

const meta: Meta<typeof LogsTable> = {
  title: 'Features/Monitoring/LogsTable',
  component: LogsTable,
  args: {
    title: 'Error & Failure Logs',
    query: '{app="scraper"} |= "error"',
    height: 300,
    refreshInterval: 0,
  },
}
export default meta
type Story = StoryObj<typeof LogsTable>

export const NotConfigured: Story = {
  args: { title: 'Application Logs' },
}

export const ExecutionTimeline: Story = {
  args: { title: 'Execution Timeline', query: '{app="scraper"}' },
}

export const WithData: Story = {
  args: {
    title: 'Error & Failure Logs',
    query: 'unused',
    height: 300,
    refreshInterval: 0,
    externalData: {
      status: 'success',
      data: {
        resultType: 'streams',
        result: [{
          stream: { app: 'scraper', level: 'error' },
          values: [
            ['1748000000000000000', JSON.stringify({ level: 'error', event: 'article_fetch_failed', url: 'https://example.com' })],
            ['1747999900000000000', JSON.stringify({ level: 'info', event: 'article_analyzed', title: 'AI Trends 2026' })],
            ['1747999800000000000', JSON.stringify({ level: 'warning', event: 'rate_limit_hit', provider: 'gemini' })],
          ] as [string, string][],
        }],
      },
    },
    onRefresh: async () => { await new Promise(r => setTimeout(r, 800)) },
  },
}