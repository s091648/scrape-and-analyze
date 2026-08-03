import type { Meta, StoryObj } from '@storybook/nextjs-vite'
import { LogsTable } from '../components/features/monitoring/logs-table'

const meta: Meta<typeof LogsTable> = {
  title: 'Features/Monitoring/LogsTable',
  component: LogsTable,
  args: {
    title: 'Error & Failure Logs',
    query: '{app="scraper"} |= "error"',
    height: 300,
    refreshInterval: 0,
  },
}
export default meta
type Story = StoryObj<typeof LogsTable>

export const NotConfigured: Story = {
  args: {
    title: 'Application Logs',
    externalData: { error: 'not_configured' } as unknown as Parameters<typeof LogsTable>[0]['externalData'],
  },
}

export const ControlledPending: Story = {
  name: 'Controlled mode — data pending (externalData=null)',
  args: {
    title: 'Execution Timeline',
    query: 'unused',
    // null is distinct from undefined: it means a parent batch-hook hasn't
    // resolved yet, so the table stays in its loading state rather than
    // falling back to self-fetch mode (see LogsTableProps.externalData doc).
    externalData: null,
  },
}

export const ExecutionTimeline: Story = {
  args: {
    title: 'Execution Timeline',
    query: '{app="scraper"}',
    externalData: {
      status: 'success',
      data: { resultType: 'streams', result: [] },
    },
  },
}

export const WithData: Story = {
  args: {
    title: 'Error & Failure Logs',
    query: 'unused',
    height: 300,
    refreshInterval: 0,
    externalData: {
      status: 'success',
      data: {
        resultType: 'streams',
        result: [{
          stream: { app: 'scraper', level: 'error' },
          values: [
            ['1748000000000000000', JSON.stringify({ level: 'error',   event: 'article_fetch_failed', url: 'https://example.com' })],
            ['1747999900000000000', JSON.stringify({ level: 'info',    event: 'article_analyzed',    title: 'AI Trends 2026' })],
            ['1747999800000000000', JSON.stringify({ level: 'warning', event: 'rate_limit_hit',      provider: 'gemini' })],
          ] as [string, string][],
        }],
      },
    },
    onRefresh: async () => { await new Promise(r => setTimeout(r, 800)) },
  },
}

export const WithFilter: Story = {
  name: 'WithData + Filter toolbar',
  args: {
    title: 'Article Logs',
    query: 'unused',
    height: 300,
    refreshInterval: 0,
    tooltip: 'Use the filter dropdown to narrow by log level.',
    externalData: {
      status: 'success',
      data: {
        resultType: 'streams',
        result: [{
          stream: { app: 'scraper' },
          values: [
            ['1748000100000000000', JSON.stringify({ level: 'error',   event: 'analysis_failed',  article_id: 'abc' })],
            ['1748000050000000000', JSON.stringify({ level: 'info',    event: 'article_analyzed', title: 'LLMs in 2026' })],
            ['1748000000000000000', JSON.stringify({ level: 'warning', event: 'rate_limit_hit',   provider: 'claude' })],
            ['1747999950000000000', JSON.stringify({ level: 'info',    event: 'article_analyzed', title: 'Diffusion Models' })],
          ] as [string, string][],
        }],
      },
    },
    onRefresh: async () => { await new Promise(r => setTimeout(r, 800)) },
  },
}

export const PlainTextLevelParsing: Story = {
  name: 'Plain-text lines — level derived from prefix / HTTP status',
  args: {
    title: 'httpx Request Tracing',
    query: 'unused',
    height: 300,
    refreshInterval: 0,
    tooltip: 'Non-JSON lines: level comes from a LEVEL: prefix, or (for prefix-less httpx tracing) the HTTP status code — never from substring-matching "error"/"warn" anywhere in the line.',
    externalData: {
      status: 'success',
      data: {
        resultType: 'streams',
        result: [{
          stream: { app: 'scraper' },
          values: [
            ['1748000300000000000', 'ERROR: connection refused while fetching feed'],
            ['1748000200000000000', 'WARNING: retrying request after transient failure'],
            // Status 500 with no "error"/"warn" text at all — level must come from the status code.
            ['1748000100000000000', 'HTTP Request: GET https://api.openalex.org/works "HTTP/1.1 500 Internal Server Error"'],
            // Query string embeds the word "warn" as a value — must NOT be misread as a WARNING line;
            // the 200 status code is what determines the (info) level.
            ['1748000000000000000', 'HTTP Request: GET https://grafana.internal/api?detected_level=warn "HTTP/1.1 200 OK"'],
            ['1747999900000000000', 'INFO: scheduled scrape started'],
          ] as [string, string][],
        }],
      },
    },
  },
}

export const Empty: Story = {
  args: {
    title: 'Execution Timeline',
    query: 'unused',
    refreshInterval: 0,
    externalData: {
      status: 'success',
      data: { resultType: 'streams', result: [] },
    },
  },
}
