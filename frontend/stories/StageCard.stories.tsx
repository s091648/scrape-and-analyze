import type { Meta, StoryObj } from '@storybook/nextjs-vite'
import { TooltipProvider } from '../components/ui/tooltip'
import { StageCard } from '../components/features/monitoring/stage-card'
import type { OtlpSpan } from '../lib/api/grafana'

const meta: Meta<typeof StageCard> = {
  title: 'Features/Monitoring/StageCard',
  component: StageCard,
  decorators: [
    (Story) => (
      <TooltipProvider>
        <div className="p-4 flex gap-4 flex-wrap">
          <Story />
        </div>
      </TooltipProvider>
    ),
  ],
}
export default meta
type Story = StoryObj<typeof StageCard>

function makeSpan(overrides: Partial<OtlpSpan>): OtlpSpan {
  return {
    traceId: 'trace1',
    spanId: 'span1',
    name: 'article.scraped.handle',
    startTimeUnixNano: '1748693400000000000',
    endTimeUnixNano:   '1748693400080000000', // 80ms
    attributes: [],
    status: { code: 0 },
    ...overrides,
  }
}

export const ScrapedStage: Story = {
  name: 'Success — scraped.handle',
  args: {
    span: makeSpan({
      name: 'article.scraped.handle',
      endTimeUnixNano: '1748693400080000000',
      attributes: [
        { key: 'article.source',  value: { stringValue: 'arxiv' } },
        { key: 'article.outcome', value: { stringValue: 'new' } },
      ],
    }),
  },
}

export const AnalysisStage: Story = {
  name: 'Success — processed.handle (with LLM attrs)',
  args: {
    span: makeSpan({
      name: 'article.processed.handle',
      endTimeUnixNano: '1748693411600000000', // 11.6s
      attributes: [
        { key: 'llm.model',         value: { stringValue: 'gemini-2.5-flash-preview' } },
        { key: 'llm.input_tokens',  value: { intValue: '3421' } },
        { key: 'llm.output_tokens', value: { intValue: '512' } },
        { key: 'analysis.success',  value: { boolValue: true } },
      ],
    }),
  },
}

export const ErrorStage: Story = {
  name: 'Error — analysis_failed',
  args: {
    span: makeSpan({
      name: 'article.analysis_failed.handle',
      endTimeUnixNano: '1748693403200000000',
      attributes: [
        { key: 'analysis.error_type', value: { stringValue: 'RateLimitExhausted' } },
        { key: 'task.type',           value: { stringValue: 'llm_analyze' } },
      ],
      status: { code: 2, message: 'RateLimitExhausted: all providers exhausted' },
    }),
  },
}

export const TranslationStage: Story = {
  name: 'Success — translate.handle',
  args: {
    span: makeSpan({
      name: 'article.translate.handle',
      endTimeUnixNano: '1748693414500000000', // 14.5s
      attributes: [
        { key: 'translation.language',         value: { stringValue: 'zh-TW' } },
        { key: 'translation.success',           value: { boolValue: true } },
        { key: 'translation.target_languages',  value: { stringValue: 'zh-TW' } },
      ],
    }),
  },
}

export const WithPercentileThresholds: Story = {
  name: 'With percentile thresholds (p90 badge)',
  args: {
    span: makeSpan({
      name: 'article.processed.handle',
      endTimeUnixNano: '1748693421600000000', // 21.6s (slow)
      attributes: [
        { key: 'llm.model', value: { stringValue: 'gemini-flash' } },
        { key: 'analysis.success', value: { boolValue: true } },
      ],
    }),
    thresholds: {
      avg: 8500,
      count: 42,
      durations: [4200, 5100, 6800, 7200, 8000, 8500, 9100, 11400, 14200, 21600],
    },
  },
}

export const Highlighted: Story = {
  name: 'Highlighted (current span)',
  args: {
    span: makeSpan({
      name: 'article.tag_normalization.handle',
      endTimeUnixNano: '1748693400300000000',
      attributes: [
        { key: 'tags.group_count', value: { intValue: '3' } },
        { key: 'tags.total_count', value: { intValue: '12' } },
      ],
    }),
    isHighlighted: true,
  },
}

export const WithCollapse: Story = {
  name: 'With collapse toggle',
  args: {
    span: makeSpan({
      name: 'article.analysis_completed.handle',
      endTimeUnixNano: '1748693400400000000',
      attributes: [
        { key: 'translation.target_languages', value: { stringValue: 'zh-TW' } },
      ],
    }),
    collapsed: false,
    onToggleCollapse: () => {},
  },
}

export const WithViewLogs: Story = {
  name: 'With "view logs" button',
  args: {
    span: makeSpan({
      name: 'article.processed.handle',
      endTimeUnixNano: '1748693411200000000',
      attributes: [
        { key: 'llm.model', value: { stringValue: 'claude-sonnet' } },
      ],
    }),
    onViewLogs: () => alert('open logs for this span'),
  },
}
