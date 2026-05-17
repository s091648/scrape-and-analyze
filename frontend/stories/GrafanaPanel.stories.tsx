import type { Meta, StoryObj } from '@storybook/nextjs-vite'
import { GrafanaPanel } from '../components/features/monitoring/grafana-panel'

const meta: Meta<typeof GrafanaPanel> = {
  title: 'Features/Monitoring/GrafanaPanel',
  component: GrafanaPanel,
  args: {
    dashboardUid: 'scrape-analyzer',
    panelId: 1,
    height: 200,
    refreshInterval: 0,
  },
}
export default meta
type Story = StoryObj<typeof GrafanaPanel>

export const NotConfigured: Story = {
  args: {
    grafanaUrl: '',
    title: 'Articles Scraped',
  },
}

export const NotConfiguredNoTitle: Story = {
  args: {
    grafanaUrl: '',
    panelId: 5,
  },
}

export const LoadingState: Story = {
  args: {
    grafanaUrl: 'https://grafana.example.com',
    title: 'Articles Scraped',
  },
}

export const TallPanel: Story = {
  args: {
    grafanaUrl: '',
    title: 'Failed Tasks Over Time',
    panelId: 2,
    height: 350,
  },
}
