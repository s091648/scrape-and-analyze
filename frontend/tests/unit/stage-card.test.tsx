import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { TooltipProvider } from '@/components/ui/tooltip'
import type { OtlpSpan } from '@/lib/api/grafana'

vi.mock('@/lib/providers', () => ({
  useI18n: () => ({ t: (k: string) => k }),
}))

beforeEach(() => {
  vi.clearAllMocks()
  vi.resetModules()
})

function makeSpan(overrides: Partial<OtlpSpan> = {}): OtlpSpan {
  return {
    traceId: 'trace1',
    spanId: 'span1',
    parentSpanId: '',
    name: 'article.scraped.handle',
    startTimeUnixNano: '1700000000000000000',
    endTimeUnixNano: '1700000001500000000', // 1.5 s
    attributes: [],
    status: { code: 0 },
    ...overrides,
  }
}

describe('StageCard rendering', () => {
  it('renders i18n label for known span names', async () => {
    const { StageCard } = await import('@/components/features/monitoring/stage-card')
    render(<StageCard span={makeSpan()} />)
    expect(screen.getByText('admin.stageLabel_scraped')).toBeDefined()
  })

  it('falls back to last span name segment for unknown names', async () => {
    const { StageCard } = await import('@/components/features/monitoring/stage-card')
    render(<StageCard span={makeSpan({ name: 'custom.module.operation' })} />)
    expect(screen.getByText('operation')).toBeDefined()
  })

  it('uses labelOverride when provided', async () => {
    const { StageCard } = await import('@/components/features/monitoring/stage-card')
    render(<StageCard span={makeSpan()} labelOverride="Translation: zh-TW" />)
    expect(screen.getByText('Translation: zh-TW')).toBeDefined()
  })

  it('shows error indicator and status message for error spans', async () => {
    const { StageCard } = await import('@/components/features/monitoring/stage-card')
    render(<StageCard span={makeSpan({ status: { code: 2, message: 'LLM timeout' } })} />)
    expect(screen.getByText('✗ Error')).toBeDefined()
    expect(screen.getByText('LLM timeout')).toBeDefined()
  })

  it('does not show error indicator for ok spans', async () => {
    const { StageCard } = await import('@/components/features/monitoring/stage-card')
    render(<StageCard span={makeSpan({ status: { code: 0 } })} />)
    expect(screen.queryByText('✗ Error')).toBeNull()
  })

  it('renders boolean true attribute as ✓', async () => {
    const { StageCard } = await import('@/components/features/monitoring/stage-card')
    render(
      <StageCard span={makeSpan({
        attributes: [{ key: 'analysis.success', value: { boolValue: true } }],
      })} />
    )
    expect(screen.getByText('✓')).toBeDefined()
  })

  it('renders boolean false attribute as ✗', async () => {
    const { StageCard } = await import('@/components/features/monitoring/stage-card')
    render(
      <StageCard span={makeSpan({
        attributes: [{ key: 'normalization.success', value: { boolValue: false } }],
      })} />
    )
    // ✗ appears both from bool false AND potentially from error — just check it's present
    expect(screen.getAllByText('✗').length).toBeGreaterThan(0)
  })

  it('renders integer attribute with locale formatting', async () => {
    const { StageCard } = await import('@/components/features/monitoring/stage-card')
    render(
      <StageCard span={makeSpan({
        attributes: [{ key: 'llm.input_tokens', value: { intValue: '1000' } }],
      })} />
    )
    expect(screen.getByText('admin.stageAttr_inputTokens')).toBeDefined()
    expect(screen.getByText('1,000')).toBeDefined()
  })

  it('renders double attribute with 3 decimal places', async () => {
    const { StageCard } = await import('@/components/features/monitoring/stage-card')
    render(
      <StageCard span={makeSpan({
        attributes: [{ key: 'pipeline.duration_seconds', value: { doubleValue: 1.23456 } }],
      })} />
    )
    expect(screen.getByText('1.235')).toBeDefined()
  })

  it('renders array attribute as comma-joined values', async () => {
    const { StageCard } = await import('@/components/features/monitoring/stage-card')
    render(
      <StageCard span={makeSpan({
        attributes: [{
          key: 'tags.tag_names',
          value: { arrayValue: { values: [{ stringValue: 'AI' }, { stringValue: 'NLP' }] } } as any,
        }],
      })} />
    )
    expect(screen.getByText('AI, NLP')).toBeDefined()
  })

  it('truncates long string attribute values to 57 chars + ellipsis', async () => {
    const { StageCard } = await import('@/components/features/monitoring/stage-card')
    const longStr = 'a'.repeat(70)
    render(
      <StageCard span={makeSpan({
        attributes: [{ key: 'article.url', value: { stringValue: longStr } }],
      })} />
    )
    expect(screen.getByText(`${'a'.repeat(57)}…`)).toBeDefined()
  })

  it('renders — for empty/undefined string attribute', async () => {
    const { StageCard } = await import('@/components/features/monitoring/stage-card')
    render(
      <StageCard span={makeSpan({
        attributes: [{ key: 'analysis.error_type', value: {} }],
      })} />
    )
    expect(screen.getByText('—')).toBeDefined()
  })

  it('renders unknown attribute key as-is', async () => {
    const { StageCard } = await import('@/components/features/monitoring/stage-card')
    render(
      <StageCard span={makeSpan({
        attributes: [{ key: 'custom.unknown.key', value: { stringValue: 'value' } }],
      })} />
    )
    expect(screen.getByText('custom.unknown.key')).toBeDefined()
    expect(screen.getByText('value')).toBeDefined()
  })
})

describe('StageCard interactions', () => {
  it('calls onViewLogs when log button is clicked', async () => {
    const { StageCard } = await import('@/components/features/monitoring/stage-card')
    const onViewLogs = vi.fn()
    render(<StageCard span={makeSpan()} onViewLogs={onViewLogs} />)
    fireEvent.click(screen.getByTitle('View logs for this span'))
    expect(onViewLogs).toHaveBeenCalledOnce()
  })

  it('calls onToggleCollapse when collapse button clicked', async () => {
    const { StageCard } = await import('@/components/features/monitoring/stage-card')
    const onToggleCollapse = vi.fn()
    render(<StageCard span={makeSpan()} collapsed={false} onToggleCollapse={onToggleCollapse} />)
    fireEvent.click(screen.getByLabelText('Collapse'))
    expect(onToggleCollapse).toHaveBeenCalledOnce()
  })

  it('shows Expand label when collapsed=true', async () => {
    const { StageCard } = await import('@/components/features/monitoring/stage-card')
    render(<StageCard span={makeSpan()} collapsed={true} onToggleCollapse={vi.fn()} />)
    expect(screen.getByLabelText('Expand')).toBeDefined()
  })

  it('does not render toggle button without onToggleCollapse', async () => {
    const { StageCard } = await import('@/components/features/monitoring/stage-card')
    render(<StageCard span={makeSpan()} />)
    expect(screen.queryByLabelText('Collapse')).toBeNull()
  })

  it('does not render logs button without onViewLogs', async () => {
    const { StageCard } = await import('@/components/features/monitoring/stage-card')
    render(<StageCard span={makeSpan()} />)
    expect(screen.queryByTitle('View logs for this span')).toBeNull()
  })
})

describe('StageCard highlight', () => {
  it('renders pulsing glow overlay when isHighlighted=true', async () => {
    const { StageCard } = await import('@/components/features/monitoring/stage-card')
    const { container } = render(<StageCard span={makeSpan()} isHighlighted={true} />)
    expect(container.querySelector('[style*="span-glow"]')).not.toBeNull()
  })

  it('does not render glow overlay when isHighlighted is not set', async () => {
    const { StageCard } = await import('@/components/features/monitoring/stage-card')
    const { container } = render(<StageCard span={makeSpan()} />)
    expect(container.querySelector('[style*="span-glow"]')).toBeNull()
  })
})

describe('StageCard with thresholds', () => {
  it('renders tooltip-wrapped duration when threshold count >= 5', async () => {
    const { StageCard } = await import('@/components/features/monitoring/stage-card')
    const durations = [800, 900, 1000, 1100, 1200, 1300, 1400, 1500, 1600, 1700]
    render(
      <TooltipProvider>
        <StageCard
          span={makeSpan()}
          thresholds={{ avg: 1300, count: 10, durations }}
        />
      </TooltipProvider>
    )
    expect(screen.getByText('1.5 s')).toBeDefined()
  })

  it('renders plain duration for fewer than 5 samples', async () => {
    const { StageCard } = await import('@/components/features/monitoring/stage-card')
    render(
      <StageCard
        span={makeSpan()}
        thresholds={{ avg: 1000, count: 3, durations: [800, 1000, 1200] }}
      />
    )
    expect(screen.getByText('1.5 s')).toBeDefined()
  })

  it('renders plain duration when no thresholds provided', async () => {
    const { StageCard } = await import('@/components/features/monitoring/stage-card')
    render(<StageCard span={makeSpan()} />)
    expect(screen.getByText('1.5 s')).toBeDefined()
  })
})

describe('StageCard known span labels', () => {
  it.each([
    ['article.processed.handle', 'admin.stageLabel_processed'],
    ['article.tag_normalization.handle', 'admin.stageLabel_tagNorm'],
    ['article.analysis_completed.handle', 'admin.stageLabel_analysisDone'],
    ['article.translate.handle', 'admin.stageLabel_translate'],
    ['scraper.pipeline_completed.handle', 'admin.stageLabel_pipelineCompleted'],
  ])('renders correct i18n key for %s', async (spanName, expectedKey) => {
    const { StageCard } = await import('@/components/features/monitoring/stage-card')
    render(<StageCard span={makeSpan({ name: spanName })} />)
    expect(screen.getByText(expectedKey)).toBeDefined()
  })
})
