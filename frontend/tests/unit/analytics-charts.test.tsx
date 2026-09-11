import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen } from '@testing-library/react'

// jsdom's ResponsiveContainer always measures 0x0 (no real layout engine), so recharts
// skips rendering its children entirely — that would hide these components' own logic
// (tickFormatter/labelFormatter) from coverage. Stub recharts with lightweight
// passthroughs instead, capturing each chart's props so tests can invoke its
// formatter callbacks directly, the same way tests/unit/graph.test.tsx exercises
// react-force-graph-2d's canvas callbacks.
let lastXAxisProps: any = null
let lastTooltipProps: any = null
vi.mock('recharts', () => ({
  ResponsiveContainer: ({ children }: any) => <div data-testid="responsive-container">{children}</div>,
  LineChart: ({ children, data }: any) => <div data-testid="line-chart" data-points={data.length}>{children}</div>,
  Line: () => null,
  BarChart: ({ children, data }: any) => <div data-testid="bar-chart" data-points={data.length}>{children}</div>,
  Bar: () => null,
  XAxis: (props: any) => { lastXAxisProps = props; return null },
  YAxis: () => null,
  Tooltip: (props: any) => { lastTooltipProps = props; return null },
  CartesianGrid: () => null,
}))

beforeEach(() => {
  lastXAxisProps = null
  lastTooltipProps = null
})

describe('ViewsTrendChart', () => {
  it('renders a LineChart with the given daily views', async () => {
    const { ViewsTrendChart } = await import('@/components/features/analytics/charts')
    render(<ViewsTrendChart data={[{ day: '2026-09-10', views: 5 }]} />)
    expect(screen.getByTestId('line-chart')).toHaveAttribute('data-points', '1')
  })

  it('formats the X-axis day tick as M/D', async () => {
    const { ViewsTrendChart } = await import('@/components/features/analytics/charts')
    render(<ViewsTrendChart data={[]} />)
    expect(lastXAxisProps.tickFormatter('2026-09-05')).toBe('9/5')
  })

  it('formats the tooltip label the same way as the axis tick', async () => {
    const { ViewsTrendChart } = await import('@/components/features/analytics/charts')
    render(<ViewsTrendChart data={[]} />)
    expect(lastTooltipProps.labelFormatter('2026-01-02')).toBe('1/2')
  })
})

describe('TopicBarChart', () => {
  it('renders a BarChart with the given topic views', async () => {
    const { TopicBarChart } = await import('@/components/features/analytics/charts')
    render(<TopicBarChart data={[{ topic: 'LLMs', views: 12 }]} />)
    expect(screen.getByTestId('bar-chart')).toHaveAttribute('data-points', '1')
  })
})

describe('Sparkline', () => {
  it('renders a placeholder dash when there is no data', async () => {
    const { Sparkline } = await import('@/components/features/analytics/charts')
    render(<Sparkline data={[]} />)
    expect(screen.getByText('—')).toBeDefined()
    expect(screen.queryByTestId('line-chart')).toBeNull()
  })

  it('renders an inline LineChart when data is present', async () => {
    const { Sparkline } = await import('@/components/features/analytics/charts')
    render(<Sparkline data={[{ day: '2026-09-01', views: 3 }, { day: '2026-09-02', views: 7 }]} />)
    expect(screen.getByTestId('line-chart')).toHaveAttribute('data-points', '2')
  })
})
