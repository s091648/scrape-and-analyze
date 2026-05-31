import type { Meta, StoryObj } from '@storybook/nextjs-vite'
import { MetricsChart } from '../components/features/monitoring/metrics-chart'

const meta: Meta<typeof MetricsChart> = {
  title: 'Features/Monitoring/MetricsChart',
  component: MetricsChart,
  args: {
    title: 'Article Volume Over Time',
    query: 'scraper_articles_new_total',
    height: 200,
    refreshInterval: 0,
  },
}
export default meta
type Story = StoryObj<typeof MetricsChart>

export const NotConfigured: Story = {
  args: { title: 'Run Duration Over Time' },
}

export const BarVariant: Story = {
  args: { title: 'New Articles by Source', chartType: 'bar' },
}

export const WithData: Story = {
  args: {
    title: 'Article Volume Over Time',
    query: 'unused_in_controlled_mode',
    refreshInterval: 0,
    externalData: {
      status: 'success',
      data: {
        resultType: 'matrix',
        result: [{
          metric: {},
          values: [
            [1748000000, '3'], [1748003600, '7'], [1748007200, '2'],
            [1748010800, '9'], [1748014400, '5'], [1748018000, '11'],
          ] as [number, string][],
        }],
      },
    },
    onRefresh: async () => { await new Promise(r => setTimeout(r, 800)) },
  },
}