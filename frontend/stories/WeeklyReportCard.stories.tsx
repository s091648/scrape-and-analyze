import type { Meta, StoryObj } from '@storybook/nextjs-vite'
import { WeeklyReportCard } from '../components/features/weekly-report/weekly-report-card'

const meta: Meta<typeof WeeklyReportCard> = {
  title: 'Features/WeeklyReport/WeeklyReportCard',
  component: WeeklyReportCard,
  parameters: {
    layout: 'padded',
  },
}
export default meta
type Story = StoryObj<typeof WeeklyReportCard>

export const WithCoverImage: Story = {
  args: {
    report: {
      id: 'report-1',
      topic_id: 'topic-1',
      week_start_date: '2026-06-16',
      title: 'AI Research Weekly: Breakthrough in Multimodal Models',
      summary_text:
        'This week saw major advances in multimodal AI, with several papers demonstrating emergent capabilities in combined vision-language models. Researchers also published new findings on scaling laws for diffusion models.',
      cover_image_url: 'https://images.unsplash.com/photo-1677442135703-1787eea5ce01?w=800&q=80',
      article_count: 12,
      status: 'completed',
      created_at: '2026-06-23T00:00:00Z',
    },
  },
}

export const WithoutCoverImage: Story = {
  args: {
    report: {
      id: 'report-2',
      topic_id: 'topic-1',
      week_start_date: '2026-06-09',
      title: 'LLM Efficiency: Quantization and Pruning Research',
      summary_text:
        'A focus on efficiency this week — quantization, pruning, and distillation dominated the research landscape. Multiple groups published results showing 2-4x inference speedups with minimal accuracy loss.',
      cover_image_url: null,
      article_count: 8,
      status: 'completed',
      created_at: '2026-06-16T00:00:00Z',
    },
  },
}

export const LongSummary: Story = {
  args: {
    report: {
      id: 'report-3',
      topic_id: 'topic-1',
      week_start_date: '2026-06-02',
      title: 'Weekly: Alignment, Safety, and RLHF Advances',
      summary_text:
        'An unusually active week for alignment research. Constitutional AI received follow-up work from two independent groups. RLHF sample efficiency was addressed by a new paper proposing preference model distillation. Several safety teams published red-teaming results for GPT-4 class models, revealing novel jailbreak vectors and mitigation strategies. Reinforcement learning from human feedback continues to be the dominant fine-tuning paradigm despite growing interest in Direct Preference Optimization variants.',
      cover_image_url: null,
      article_count: 18,
      status: 'completed',
      created_at: '2026-06-09T00:00:00Z',
    },
  },
}
