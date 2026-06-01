import type { Meta, StoryObj } from '@storybook/nextjs-vite'
import { ArticleWorkflowDialog } from '../components/features/monitoring/article-workflow-dialog'
import type { OtlpSpan } from '../lib/api/grafana'

const meta: Meta<typeof ArticleWorkflowDialog> = {
  title: 'Features/Monitoring/ArticleWorkflowDialog',
  component: ArticleWorkflowDialog,
  args: { open: true, onClose: () => {} },
}
export default meta
type Story = StoryObj<typeof ArticleWorkflowDialog>

function makeSpan(overrides: Partial<OtlpSpan>): OtlpSpan {
  return {
    traceId: 'trace1', spanId: 'span1', name: 'test',
    startTimeUnixNano: '1748000000000000000',
    endTimeUnixNano:   '1748000001000000000',
    attributes: [],
    status: { code: 0 },
    ...overrides,
  }
}

const pipelineSpan = makeSpan({
  spanId: 'p1', name: 'article.pipeline',
  endTimeUnixNano: '1748000012300000000',
  attributes: [
    { key: 'article.url',    value: { stringValue: 'https://arxiv.org/abs/2506.01234' } },
    { key: 'article.source', value: { stringValue: 'arxiv' } },
  ],
})

const stageSpans: OtlpSpan[] = [
  makeSpan({
    spanId: 'c1', name: 'article.scraped.handle', parentSpanId: 'p1',
    startTimeUnixNano: '1748000000000000000',
    endTimeUnixNano:   '1748000000100000000',
    attributes: [
      { key: 'article.source',  value: { stringValue: 'arxiv' } },
      { key: 'article.outcome', value: { stringValue: 'new' } },
    ],
  }),
  makeSpan({
    spanId: 'c2', name: 'article.processed.handle', parentSpanId: 'p1',
    startTimeUnixNano: '1748000000100000000',
    endTimeUnixNano:   '1748000011600000000',
    attributes: [
      { key: 'llm.model',         value: { stringValue: 'gemini-flash' } },
      { key: 'llm.input_tokens',  value: { intValue: '1234' } },
      { key: 'llm.output_tokens', value: { intValue: '456' } },
      { key: 'analysis.success',  value: { boolValue: true } },
    ],
  }),
  makeSpan({
    spanId: 'c3', name: 'article.tag_normalization.handle', parentSpanId: 'p1',
    startTimeUnixNano: '1748000011600000000',
    endTimeUnixNano:   '1748000011900000000',
    attributes: [
      { key: 'tags.group_count', value: { intValue: '3' } },
      { key: 'tags.total_count', value: { intValue: '12' } },
      { key: 'normalization.success', value: { boolValue: true } },
    ],
  }),
  makeSpan({
    spanId: 'c4', name: 'article.analysis_completed.handle', parentSpanId: 'p1',
    startTimeUnixNano: '1748000011900000000',
    endTimeUnixNano:   '1748000012300000000',
    attributes: [
      { key: 'translation.target_languages', value: { stringValue: 'zh-TW' } },
    ],
  }),
]

export const Default: Story = {
  args: { pipelineSpan, stageSpans },
}

export const WithFailedStage: Story = {
  args: {
    pipelineSpan,
    stageSpans: [
      stageSpans[0],
      makeSpan({
        spanId: 'c2-err', name: 'article.processed.handle', parentSpanId: 'p1',
        startTimeUnixNano: '1748000000100000000',
        endTimeUnixNano:   '1748000003200000000',
        attributes: [{ key: 'analysis.error_type', value: { stringValue: 'RateLimitExhausted' } }],
        status: { code: 2, message: 'RateLimitExhausted: all providers exhausted' },
      }),
    ],
  },
}

export const SingleStage: Story = {
  args: { pipelineSpan, stageSpans: [stageSpans[0]] },
}