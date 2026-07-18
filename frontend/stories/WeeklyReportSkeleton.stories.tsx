import type { Meta, StoryObj } from '@storybook/nextjs-vite'
import { WeeklyReportSkeleton } from '../components/features/weekly-report/weekly-report-skeleton'

const meta: Meta<typeof WeeklyReportSkeleton> = {
  title: 'Features/WeeklyReport/WeeklyReportSkeleton',
  component: WeeklyReportSkeleton,
  parameters: { layout: 'padded' },
}
export default meta
type Story = StoryObj<typeof WeeklyReportSkeleton>

export const Default: Story = {
  render: () => (
    <div className="w-80">
      <WeeklyReportSkeleton />
    </div>
  ),
}
