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
