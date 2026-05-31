import type { Meta, StoryObj } from '@storybook/nextjs-vite'
import { TracesTable } from '../components/features/monitoring/traces-table'

const meta: Meta<typeof TracesTable> = {
  title: 'Features/Monitoring/TracesTable',
  component: TracesTable,
  args: {
    title: 'Recent Traces',
    query: '{ resource.service.name = "scrape-analyzer" }',
    height: 300,
    refreshInterval: 0,
  },
}
export default meta
type Story = StoryObj<typeof TracesTable>

export const NotConfigured: Story = {
  args: { title: 'Recent Traces' },
}

export const WithGrafanaLink: Story = {
  args: {
    title: 'Recent Traces',
    grafanaUrl: 'https://mystack.grafana.net',
  },
}
