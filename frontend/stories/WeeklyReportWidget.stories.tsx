import type { Meta, StoryObj } from '@storybook/nextjs-vite'
import { fn } from 'storybook/test'

const mockReport = {
  id: 'report-uuid-1',
  topic_id: 'topic-uuid-1',
  week_start_date: '2026-06-16',
  title: 'AI Research Weekly: Breakthrough in Multimodal Models',
  summary_text:
    'This week saw major advances in multimodal AI, with several papers demonstrating emergent capabilities in combined vision-language models. Researchers also published new findings on scaling laws for diffusion models, and a landmark study on constitutional AI approaches for alignment.',
  cover_image_url: null,
  article_count: 12,
  status: 'completed',
  created_at: '2026-06-23T00:00:00Z',
}

const mockReport2 = {
  ...mockReport,
  id: 'report-uuid-2',
  week_start_date: '2026-06-09',
  title: 'AI Research Weekly: LLM Efficiency Improvements',
  summary_text: 'A focus on efficiency this week — quantization, pruning, and distillation dominated the research landscape.',
  article_count: 8,
}

import { WeeklyReportWidget } from '../components/features/weekly-report/weekly-report-widget'

const meta: Meta<typeof WeeklyReportWidget> = {
  title: 'Features/WeeklyReport/WeeklyReportWidget',
  component: WeeklyReportWidget,
  parameters: {
    layout: 'padded',
  },
}
export default meta
type Story = StoryObj<typeof WeeklyReportWidget>

export const WithReport: Story = {
  args: {
    topicId: 'topic-uuid-1',
  },
  parameters: {
    mockData: [
      {
        url: '/api/proxy/weekly-reports/latest?topic_id=topic-uuid-1',
        method: 'GET',
        status: 200,
        response: mockReport,
      },
      {
        url: '/api/proxy/weekly-reports?topic_id=topic-uuid-1&limit=10&offset=0',
        method: 'GET',
        status: 200,
        response: { items: [mockReport], total: 1, page: 1, size: 10 },
      },
    ],
  },
}

export const WithMultipleReports: Story = {
  args: {
    topicId: 'topic-uuid-1',
  },
  parameters: {
    mockData: [
      {
        url: '/api/proxy/weekly-reports/latest?topic_id=topic-uuid-1',
        method: 'GET',
        status: 200,
        response: mockReport,
      },
      {
        url: '/api/proxy/weekly-reports?topic_id=topic-uuid-1&limit=10&offset=0',
        method: 'GET',
        status: 200,
        response: { items: [mockReport, mockReport2], total: 2, page: 1, size: 10 },
      },
    ],
  },
}

export const NoReport: Story = {
  args: {
    topicId: 'topic-uuid-1',
  },
  parameters: {
    mockData: [
      {
        url: '/api/proxy/weekly-reports/latest?topic_id=topic-uuid-1',
        method: 'GET',
        status: 200,
        response: null,
      },
      {
        url: '/api/proxy/weekly-reports?topic_id=topic-uuid-1&limit=10&offset=0',
        method: 'GET',
        status: 200,
        response: { items: [], total: 0, page: 1, size: 10 },
      },
    ],
  },
}

export const NoTopic: Story = {
  args: {
    topicId: null,
  },
}
