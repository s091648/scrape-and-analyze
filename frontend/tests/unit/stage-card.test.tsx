import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import type { OtlpSpan } from '@/lib/api/grafana'
import type { SpanPercentileThresholds } from '@/components/features/monitoring/stage-card'

vi.mock('@/lib/providers', () => ({
  useI18n: () => ({
    t: (k: string) => k,
  }),
}))

vi.mock('@/components/ui/tooltip', () => ({
  Tooltip: ({ children }: any) => <>{children}</>,
  TooltipTrigger: ({ children }: any) => <>{children}</>,
  TooltipContent: ({ children }: any) => <div data-testid="tooltip-content">{children}</div>,
}))

function makeSpan(overrides: Partial<OtlpSpan> = {}): OtlpSpan {
  return {
    traceId: 'trace1',
    spanId: 'span1',
    name: 'article.scraped.handle',
    startTimeUnixNano: '1700000000000000000',
    endTimeUnixNano: '1700000001500000000',
    attributes: [],
    ...overrides,
  }
}

describe('StageCard label', () => {
  it('shows the i18n-mapped label for a known stage name', async () => {
    const { StageCard } = await import('@/components/features/monitoring/stage-card')
    render(<StageCard span={makeSpan({ name: 'article.scraped.handle' })} />)
    expect(screen.getByText('admin.stageLabel_scraped')).toBeDefined()
  })

  it('falls back to the last dot-segment of the span name when unmapped', async () => {
    const { StageCard } = await import('@/components/features/monitoring/stage-card')
    render(<StageCard span={makeSpan({ name: 'some.unmapped.name' })} />)
    expect(screen.getByText('name')).toBeDefined()
  })

  it('prefers labelOverride when provided', async () => {
    const { StageCard } = await import('@/components/features/monitoring/stage-card')
    render(<StageCard span={makeSpan()} labelOverride="Custom Label" />)
    expect(screen.getByText('Custom Label')).toBeDefined()
  })
})

describe('StageCard error state', () => {
  it('shows the error marker and message for a failed span', async () => {
    const { StageCard } = await import('@/components/features/monitoring/stage-card')
    render(<StageCard span={makeSpan({ status: { code: 2, message: 'boom happened' } })} />)
    expect(screen.getByText('✗ Error')).toBeDefined()
    expect(screen.getByText('boom happened')).toBeDefined()
  })

  it('does not show an error marker for a healthy span', async () => {
    const { StageCard } = await import('@/components/features/monitoring/stage-card')
    render(<StageCard span={makeSpan({ status: { code: 0 } })} />)
    expect(screen.queryByText('✗ Error')).toBeNull()
  })
})

describe('StageCard collapse + view-logs controls', () => {
  it('calls onToggleCollapse when the toggle button is clicked', async () => {
    const { StageCard } = await import('@/components/features/monitoring/stage-card')
    const onToggleCollapse = vi.fn()
    render(<StageCard span={makeSpan()} collapsed={false} onToggleCollapse={onToggleCollapse} />)
    fireEvent.click(screen.getByLabelText('Collapse'))
    expect(onToggleCollapse).toHaveBeenCalledOnce()
  })

  it('shows the Expand label when collapsed', async () => {
    const { StageCard } = await import('@/components/features/monitoring/stage-card')
    render(<StageCard span={makeSpan()} collapsed onToggleCollapse={vi.fn()} />)
    expect(screen.getByLabelText('Expand')).toBeDefined()
  })

  it('calls onViewLogs when the view-logs button is clicked', async () => {
    const { StageCard } = await import('@/components/features/monitoring/stage-card')
    const onViewLogs = vi.fn()
    render(<StageCard span={makeSpan()} onViewLogs={onViewLogs} />)
    fireEvent.click(screen.getByTitle('View logs for this span'))
    expect(onViewLogs).toHaveBeenCalledOnce()
  })
})

describe('StageCard duration + percentile', () => {
  it('renders a plain duration badge when no thresholds are given', async () => {
    const { StageCard } = await import('@/components/features/monitoring/stage-card')
    render(<StageCard span={makeSpan()} />)
    expect(screen.getByText('1.5 s')).toBeDefined()
    expect(screen.queryByTestId('tooltip-content')).toBeNull()
  })

  it('does not show a percentile tooltip when the sample count is below 5', async () => {
    const { StageCard } = await import('@/components/features/monitoring/stage-card')
    const thresholds: SpanPercentileThresholds = { avg: 1000, count: 3, durations: [900, 1000, 1100] }
    render(<StageCard span={makeSpan()} thresholds={thresholds} />)
    expect(screen.queryByTestId('tooltip-content')).toBeNull()
  })

  it('shows a percentile tooltip with a KDE sparkline once there is enough sample data', async () => {
    const { StageCard } = await import('@/components/features/monitoring/stage-card')
    const thresholds: SpanPercentileThresholds = {
      avg: 1000, count: 6, durations: [200, 400, 600, 800, 1000, 1200],
    }
    render(<StageCard span={makeSpan({ endTimeUnixNano: '1700000006000000000' })} thresholds={thresholds} />)

    const tooltip = screen.getByTestId('tooltip-content')
    expect(tooltip.textContent).toContain('percentile:')
    expect(tooltip.textContent).toContain('n=6')
    expect(tooltip.querySelector('svg')).not.toBeNull()
  })

  it('colors an unusually slow span red (>=90th percentile)', async () => {
    const { StageCard } = await import('@/components/features/monitoring/stage-card')
    const thresholds: SpanPercentileThresholds = {
      avg: 500, count: 6, durations: [100, 150, 200, 250, 300, 350],
    }
    // 10s is far beyond every sample duration — percentile ~100%.
    render(
      <StageCard
        span={makeSpan({ startTimeUnixNano: '0', endTimeUnixNano: '10000000000' })}
        thresholds={thresholds}
      />
    )
    const badge = screen.getByText('10.0 s')
    expect(badge.className).toContain('text-red-500')
  })

  it('leaves a typically-fast span at the default color (<70th percentile)', async () => {
    const { StageCard } = await import('@/components/features/monitoring/stage-card')
    const thresholds: SpanPercentileThresholds = {
      avg: 500, count: 6, durations: [500, 550, 600, 650, 700, 750],
    }
    // 1ms is far below every sample duration — percentile ~0%.
    render(
      <StageCard
        span={makeSpan({ startTimeUnixNano: '0', endTimeUnixNano: '1000000' })}
        thresholds={thresholds}
      />
    )
    const badge = screen.getByText('1 ms')
    expect(badge.className).toContain('text-foreground')
  })
})

describe('StageCard attributes', () => {
  it('renders known attribute keys with their i18n label and a boolean checkmark', async () => {
    const { StageCard } = await import('@/components/features/monitoring/stage-card')
    render(
      <StageCard
        span={makeSpan({
          attributes: [{ key: 'analysis.success', value: { boolValue: true } }],
        })}
      />
    )
    expect(screen.getByText('admin.stageAttr_success')).toBeDefined()
    expect(screen.getByText('✓')).toBeDefined()
  })

  it('renders an unmapped attribute key verbatim with its formatted value', async () => {
    const { StageCard } = await import('@/components/features/monitoring/stage-card')
    render(
      <StageCard
        span={makeSpan({
          attributes: [{ key: 'http.route', value: { stringValue: '/api/articles' } }],
        })}
      />
    )
    expect(screen.getByText('http.route')).toBeDefined()
    expect(screen.getByText('/api/articles')).toBeDefined()
  })

  it('renders an arrayValue attribute as a comma-joined list', async () => {
    const { StageCard } = await import('@/components/features/monitoring/stage-card')
    render(
      <StageCard
        span={makeSpan({
          attributes: [{
            key: 'tags.tag_names',
            value: { arrayValue: { values: [{ stringValue: 'ai' }, { stringValue: 'ml' }] } } as any,
          }],
        })}
      />
    )
    expect(screen.getByText('ai, ml')).toBeDefined()
  })

  it('renders an http.method attribute as a colored badge', async () => {
    const { StageCard } = await import('@/components/features/monitoring/stage-card')
    render(
      <StageCard
        span={makeSpan({
          attributes: [{ key: 'http.method', value: { stringValue: 'GET' } }],
        })}
      />
    )
    expect(screen.getByText('GET')).toBeDefined()
  })
})

describe('StageCard events', () => {
  it('renders an event name with its offset from the span start', async () => {
    const { StageCard } = await import('@/components/features/monitoring/stage-card')
    render(
      <StageCard
        span={makeSpan({
          startTimeUnixNano: '1700000000000000000',
          events: [{ timeUnixNano: '1700000000500000000', name: 'first_chunk' }],
        })}
      />
    )
    expect(screen.getByText('first_chunk')).toBeDefined()
    expect(screen.getByText('+500 ms')).toBeDefined()
  })

  it('appends event attributes to the offset line', async () => {
    const { StageCard } = await import('@/components/features/monitoring/stage-card')
    render(
      <StageCard
        span={makeSpan({
          startTimeUnixNano: '1700000000000000000',
          events: [{
            timeUnixNano: '1700000000500000000',
            name: 'first_chunk',
            attributes: [{ key: 'chunk.index', value: { intValue: '1' } }],
          }],
        })}
      />
    )
    expect(screen.getByText(/chunk\.index=1/)).toBeDefined()
  })

  it('renders nothing extra when there are no events', async () => {
    const { StageCard } = await import('@/components/features/monitoring/stage-card')
    const { container } = render(<StageCard span={makeSpan({ events: [] })} />)
    expect(container.querySelectorAll('table')).toHaveLength(0)
  })
})
