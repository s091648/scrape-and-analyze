import type { Meta, StoryObj } from '@storybook/nextjs-vite'
import { type ComponentProps, useState } from 'react'
import { WeeklyReportStepper } from '../components/features/weekly-report/weekly-report-stepper'
import type { WeeklyReport } from '../lib/api/weekly-reports'

function mockReport(id: string, weekStart: string): WeeklyReport {
  return {
    id,
    topic_id: 'topic-uuid-1',
    week_start_date: weekStart,
    title: `Weekly report for ${weekStart}`,
    summary_text: 'Summary text.',
    cover_image_url: null,
    article_count: 10,
    status: 'completed',
    created_at: `${weekStart}T00:00:00Z`,
    sources: [],
  }
}

const manyReports: WeeklyReport[] = [
  mockReport('report-1', '2026-06-30'),
  mockReport('report-2', '2026-06-23'),
  mockReport('report-3', '2026-06-16'),
  mockReport('report-4', '2026-06-09'),
]

const meta: Meta<typeof WeeklyReportStepper> = {
  title: 'Features/WeeklyReport/WeeklyReportStepper',
  component: WeeklyReportStepper,
  parameters: { layout: 'padded' },
  decorators: [
    (Story) => (
      <div className="relative h-96 w-40 overflow-hidden rounded-2xl bg-gradient-to-br from-indigo-500 via-purple-500 to-pink-500 p-4">
        <Story />
      </div>
    ),
  ],
}
export default meta
type Story = StoryObj<typeof WeeklyReportStepper>

function Controlled(args: ComponentProps<typeof WeeklyReportStepper>) {
  const [selectedId, setSelectedId] = useState(args.selectedId)
  return <WeeklyReportStepper {...args} selectedId={selectedId} onSelect={setSelectedId} />
}

export const MultipleWeeks: Story = {
  render: (args) => <Controlled {...args} />,
  args: {
    reports: manyReports,
    selectedId: 'report-1',
    onJumpToWeek: () => {},
    isWeekAvailable: () => true,
  },
}

export const SingleWeek: Story = {
  render: (args) => <Controlled {...args} />,
  args: {
    reports: [mockReport('report-1', '2026-06-30')],
    selectedId: 'report-1',
    onJumpToWeek: () => {},
    isWeekAvailable: () => true,
  },
}
