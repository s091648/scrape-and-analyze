import type { Meta, StoryObj } from '@storybook/nextjs-vite'
import { RunWaterfallDialog } from '../components/features/monitoring/run-waterfall-dialog'
import type { OtlpTraceResponse } from '../lib/api/grafana'

const meta: Meta<typeof RunWaterfallDialog> = {
  title: 'Features/Monitoring/RunWaterfallDialog',
  component: RunWaterfallDialog,
  args: { open: true, onClose: () => {}, traceId: 'abc123def456789012345678' },
}
export default meta
type Story = StoryObj<typeof RunWaterfallDialog>

const mockTrace: OtlpTraceResponse = {
  batches: [{
    resource: {
      attributes: [
        { key: 'service.name',           value: { stringValue: 'scrape-analyzer' } },
        { key: 'deployment.environment', value: { stringValue: 'production' } },
      ],
    },
    scopeSpans: [{
      spans: [
        {
          traceId: 'abc123', spanId: 'root', parentSpanId: '', name: 'scraper.run',
          startTimeUnixNano: '1748000000000000000',
          endTimeUnixNano:   '1748000045200000000',
          attributes: [
            { key: 'run.id',             value: { stringValue: 'run-001' } },
            { key: 'run.correlation_id', value: { stringValue: 'corr-abc' } },
          ],
          status: { code: 0 },
        },
        {
          traceId: 'abc123', spanId: 'p1', parentSpanId: 'root', name: 'article.pipeline',
          startTimeUnixNano: '1748000001000000000',
          endTimeUnixNano:   '1748000013300000000',
          attributes: [
            { key: 'article.url',    value: { stringValue: 'https://arxiv.org/abs/2506.01234' } },
            { key: 'article.source', value: { stringValue: 'arxiv' } },
          ],
          status: { code: 0 },
        },
        {
          traceId: 'abc123', spanId: 'p1s1', parentSpanId: 'p1', name: 'article.scraped.handle',
          startTimeUnixNano: '1748000001000000000',
          endTimeUnixNano:   '1748000001100000000',
          attributes: [{ key: 'article.outcome', value: { stringValue: 'new' } }],
          status: { code: 0 },
        },
        {
          traceId: 'abc123', spanId: 'p1s2', parentSpanId: 'p1', name: 'article.processed.handle',
          startTimeUnixNano: '1748000001100000000',
          endTimeUnixNano:   '1748000012600000000',
          attributes: [
            { key: 'llm.model',         value: { stringValue: 'gemini-flash' } },
            { key: 'llm.input_tokens',  value: { intValue: '1234' } },
            { key: 'llm.output_tokens', value: { intValue: '456' } },
          ],
          status: { code: 0 },
        },
        {
          traceId: 'abc123', spanId: 'p1s3', parentSpanId: 'p1', name: 'article.tag_normalization.handle',
          startTimeUnixNano: '1748000012600000000',
          endTimeUnixNano:   '1748000012900000000',
          attributes: [{ key: 'tags.total_count', value: { intValue: '12' } }],
          status: { code: 0 },
        },
        {
          traceId: 'abc123', spanId: 'p1s4', parentSpanId: 'p1', name: 'article.analysis_completed.handle',
          startTimeUnixNano: '1748000012900000000',
          endTimeUnixNano:   '1748000013300000000',
          attributes: [{ key: 'translation.target_languages', value: { stringValue: 'zh-TW' } }],
          status: { code: 0 },
        },
        {
          traceId: 'abc123', spanId: 'p2', parentSpanId: 'root', name: 'article.pipeline',
          startTimeUnixNano: '1748000013500000000',
          endTimeUnixNano:   '1748000022200000000',
          attributes: [
            { key: 'article.url',    value: { stringValue: 'https://rss.example.com/post/hello-world' } },
            { key: 'article.source', value: { stringValue: 'rss' } },
          ],
          status: { code: 0 },
        },
        {
          traceId: 'abc123', spanId: 'p2s1', parentSpanId: 'p2', name: 'article.scraped.handle',
          startTimeUnixNano: '1748000013500000000',
          endTimeUnixNano:   '1748000013600000000',
          attributes: [{ key: 'article.outcome', value: { stringValue: 'new' } }],
          status: { code: 0 },
        },
        {
          traceId: 'abc123', spanId: 'p2s2', parentSpanId: 'p2', name: 'article.processed.handle',
          startTimeUnixNano: '1748000013600000000',
          endTimeUnixNano:   '1748000020800000000',
          attributes: [
            { key: 'llm.model',         value: { stringValue: 'gemini-flash' } },
            { key: 'analysis.success',  value: { boolValue: false } },
            { key: 'analysis.error_type', value: { stringValue: 'RateLimitExhausted' } },
          ],
          status: { code: 2, message: 'RateLimitExhausted' },
        },
      ],
    }],
  }],
}

export const Default: Story = {
  args: { trace: mockTrace, onSelectArticle: () => {} },
}