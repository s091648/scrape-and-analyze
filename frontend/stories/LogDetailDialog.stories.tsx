import type { Meta, StoryObj } from '@storybook/nextjs-vite'
import { LogDetailDialog } from '../components/features/monitoring/log-detail-dialog'
import type { LogEntry } from '../components/features/monitoring/log-detail-dialog'

const meta: Meta<typeof LogDetailDialog> = {
  title: 'Features/Monitoring/LogDetailDialog',
  component: LogDetailDialog,
  args: {
    onClose: () => {},
  },
}
export default meta
type Story = StoryObj<typeof LogDetailDialog>

function makeEntry(overrides: Partial<LogEntry> = {}): LogEntry {
  return {
    ts: '14:30:00',
    tsExact: '2026-06-04T14:30:00.123Z',
    level: 'info',
    env: 'production',
    message: 'article analyzed successfully',
    raw: JSON.stringify({
      level: 'info',
      event: 'article_analyzed',
      article_id: 'f47ac10b-58cc-4372-a567-0e02b2c3d479',
      title: 'Scaling LLMs with Mixture of Experts',
      source: 'arxiv',
    }),
    ...overrides,
  }
}

export const InfoLevel: Story = {
  name: 'Info — article analyzed',
  args: { entry: makeEntry() },
}

export const ErrorLevel: Story = {
  name: 'Error — analysis failed',
  args: {
    entry: makeEntry({
      level: 'error',
      message: 'LLM analysis failed: rate limit exhausted',
      raw: JSON.stringify({
        level: 'error',
        event: 'llm_analysis_failed',
        article_id: 'f47ac10b-58cc-4372-a567-0e02b2c3d479',
        error_type: 'RateLimitExhausted',
        provider: 'gemini',
      }),
    }),
  },
}

export const WarningLevel: Story = {
  name: 'Warning — rate limit hit',
  args: {
    entry: makeEntry({
      level: 'warning',
      message: 'rate limit hit, retrying with next provider',
      raw: JSON.stringify({
        level: 'warning',
        event: 'rate_limit_hit',
        provider: 'claude',
        retry_provider: 'gemini',
      }),
    }),
  },
}

export const WithTraceLink: Story = {
  name: 'WithTraceLink — trace_id in raw JSON',
  args: {
    entry: makeEntry({
      raw: JSON.stringify({
        level: 'info',
        event: 'article_analyzed',
        trace_id: 'a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4',
        span_id: 'f1e2d3c4b5a6f1e2',
        article_id: 'abc',
        source: 'arxiv',
      }),
    }),
    onOpenTrace: (traceId, spanId) => alert(`Open trace: ${traceId} span: ${spanId}`),
  },
}

export const NonJsonRaw: Story = {
  name: 'Non-JSON raw — plain text fallback',
  args: {
    entry: makeEntry({
      message: 'scrapy error output',
      raw: '[ERROR] 2026-06-04 14:30:00 — Connection refused: https://example.com',
    }),
  },
}

export const NoExtraFields: Story = {
  name: 'No extra fields',
  args: {
    entry: makeEntry({
      raw: JSON.stringify({ level: 'info', event: 'pipeline_started' }),
    }),
  },
}

export const Closed: Story = {
  name: 'Closed (entry = null)',
  args: { entry: null },
}
