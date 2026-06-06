import type { Meta, StoryObj } from '@storybook/nextjs-vite'
import { StatCard } from '../components/features/monitoring/stat-card'

const meta: Meta<typeof StatCard> = {
  title: 'Features/Monitoring/StatCard',
  component: StatCard,
}
export default meta
type Story = StoryObj<typeof StatCard>

export const Default: Story = {
  args: { title: 'Total Runs (24h)', value: 42 },
}

export const WithUnit: Story = {
  args: { title: 'Avg Duration', value: '12.3', unit: 's' },
}

export const Loading: Story = {
  args: { title: 'Error Count', loading: true },
}

export const ZeroValue: Story = {
  args: { title: 'Failed Articles', value: 0 },
}

export const ErrorState: Story = {
  args: { title: 'New Articles', error: true },
}

export const WithRefresh: Story = {
  args: {
    title: 'Total Runs (24h)',
    value: 42,
    onRefresh: async () => { await new Promise(r => setTimeout(r, 1000)) },
  },
}