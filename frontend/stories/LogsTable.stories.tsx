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
