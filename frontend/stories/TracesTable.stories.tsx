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

export const WithData: Story = {
  args: {
    title: 'Recent Traces',
    query: 'unused',
    height: 300,
    refreshInterval: 0,
    grafanaUrl: 'https://mystack.grafana.net',
    externalData: {
      traces: [
        {
          traceID: 'abc123def456789012345678',
          rootServiceName: 'scrape-analyzer',
          rootTraceName: 'scraper.run',
          startTimeUnixNano: '1748000000000000000',
          durationMs: 4823,
        },
        {
          traceID: 'fed987cba654321098765432',
          rootServiceName: 'scrape-analyzer',
          rootTraceName: 'scraper.run',
          startTimeUnixNano: '1747999000000000000',
          durationMs: 12041,
        },
      ],
    },
    onRefresh: async () => { await new Promise(r => setTimeout(r, 800)) },
  },
}