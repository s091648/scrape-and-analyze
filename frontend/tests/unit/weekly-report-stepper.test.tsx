import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'

// jsdom does not implement scrollTo
Element.prototype.scrollTo = vi.fn()

vi.mock('@/lib/providers', () => ({
  useI18n: () => ({
    locale: 'en',
    t: (key: string) => {
      const map: Record<string, string> = {
        'weeklyReport.selectWeek': 'Select report week',
        'weeklyReport.jumpToNewest': 'Jump to newest week',
        'weeklyReport.jumpToOldest': 'Jump to oldest week',
      }
      return map[key] ?? key
    },
  }),
}))

vi.mock('@/components/ui/week-picker', () => ({
  WeekPicker: (props: any) => (
    <div data-testid="week-picker">
      <button data-testid="week-picker-select" onClick={() => props.onSelectWeek(new Date('2026-07-13'))}>
        select
      </button>
    </div>
  ),
}))

function makeReports(count: number) {
  return Array.from({ length: count }, (_, i) => ({
    id: `report-${i}`,
    topic_id: 'topic-1',
    week_start_date: `2026-0${(i % 9) + 1}-01`,
    title: `Report ${i}`,
    summary_text: '',
    cover_image_url: null,
    article_count: 1,
    status: 'completed',
    created_at: '2026-01-01T00:00:00Z',
    sources: [],
  })) as any
}

function withOverflow<T>(scrollHeight: number, clientHeight: number, fn: () => T): T {
  const originalScrollHeight = Object.getOwnPropertyDescriptor(HTMLElement.prototype, 'scrollHeight')
  const originalClientHeight = Object.getOwnPropertyDescriptor(HTMLElement.prototype, 'clientHeight')
  Object.defineProperty(HTMLElement.prototype, 'scrollHeight', { configurable: true, value: scrollHeight })
  Object.defineProperty(HTMLElement.prototype, 'clientHeight', { configurable: true, value: clientHeight })
  try {
    return fn()
  } finally {
    if (originalScrollHeight) Object.defineProperty(HTMLElement.prototype, 'scrollHeight', originalScrollHeight)
    if (originalClientHeight) Object.defineProperty(HTMLElement.prototype, 'clientHeight', originalClientHeight)
  }
}

describe('WeeklyReportStepper — scroll fix (2026-07-14, US10)', () => {
  it('does not show jump-to-top/bottom chevrons when the list fits', async () => {
    const { WeeklyReportStepper } = await import('@/components/features/weekly-report/weekly-report-stepper')
    withOverflow(100, 100, () => {
      render(<WeeklyReportStepper reports={makeReports(3)} selectedId="report-0" onSelect={vi.fn()} />)
    })
    expect(screen.queryByLabelText('Jump to newest week')).not.toBeInTheDocument()
    expect(screen.queryByLabelText('Jump to oldest week')).not.toBeInTheDocument()
  })

  it('shows jump-to-top/bottom chevrons when the list overflows, and they scroll the list', async () => {
    const { WeeklyReportStepper } = await import('@/components/features/weekly-report/weekly-report-stepper')
    withOverflow(500, 100, () => {
      render(<WeeklyReportStepper reports={makeReports(10)} selectedId="report-0" onSelect={vi.fn()} />)

      const up = screen.getByLabelText('Jump to newest week')
      const down = screen.getByLabelText('Jump to oldest week')
      expect(up).toBeInTheDocument()
      expect(down).toBeInTheDocument()

      fireEvent.click(up)
      expect(Element.prototype.scrollTo).toHaveBeenCalledWith({ top: 0, behavior: 'smooth' })

      fireEvent.click(down)
      expect(Element.prototype.scrollTo).toHaveBeenCalledWith({ top: 500, behavior: 'smooth' })
    })
  })

  it('renders the date picker even when the week list is empty of dots (single report)', async () => {
    const { WeeklyReportStepper } = await import('@/components/features/weekly-report/weekly-report-stepper')
    render(
      <WeeklyReportStepper
        reports={makeReports(1)}
        selectedId="report-0"
        onSelect={vi.fn()}
        onJumpToWeek={vi.fn()}
      />
    )
    expect(screen.getByTestId('week-picker')).toBeInTheDocument()
    expect(screen.queryByRole('listbox')).not.toBeInTheDocument()
  })

  it('applies the slim custom scrollbar class and hides horizontal overflow on the listbox', async () => {
    const { WeeklyReportStepper } = await import('@/components/features/weekly-report/weekly-report-stepper')
    withOverflow(500, 100, () => {
      render(<WeeklyReportStepper reports={makeReports(10)} selectedId="report-0" onSelect={vi.fn()} />)
      const list = screen.getByRole('listbox')
      expect(list.className).toContain('weekly-stepper-scroll')
      expect(list.className).toContain('overflow-x-hidden')
    })
  })
})

describe('WeeklyReportStepper — render guard', () => {
  it('renders nothing when there is only one report and no onJumpToWeek', async () => {
    const { WeeklyReportStepper } = await import('@/components/features/weekly-report/weekly-report-stepper')
    const { container } = render(
      <WeeklyReportStepper reports={makeReports(1)} selectedId="report-0" onSelect={vi.fn()} />
    )
    expect(container.firstChild).toBeNull()
  })

  it('renders nothing when there are zero reports and no onJumpToWeek', async () => {
    const { WeeklyReportStepper } = await import('@/components/features/weekly-report/weekly-report-stepper')
    const { container } = render(
      <WeeklyReportStepper reports={makeReports(0)} selectedId={null} onSelect={vi.fn()} />
    )
    expect(container.firstChild).toBeNull()
  })

  it('still renders the date picker with a single report when onJumpToWeek is provided', async () => {
    const { WeeklyReportStepper } = await import('@/components/features/weekly-report/weekly-report-stepper')
    render(
      <WeeklyReportStepper
        reports={makeReports(1)}
        selectedId="report-0"
        onSelect={vi.fn()}
        onJumpToWeek={vi.fn()}
      />
    )
    expect(screen.getByTestId('week-picker')).toBeInTheDocument()
  })
})

describe('WeeklyReportStepper — week selection', () => {
  it('calls onSelect with the clicked report id', async () => {
    const { WeeklyReportStepper } = await import('@/components/features/weekly-report/weekly-report-stepper')
    const onSelect = vi.fn()
    render(<WeeklyReportStepper reports={makeReports(3)} selectedId="report-0" onSelect={onSelect} />)

    fireEvent.click(screen.getByText('Feb 1').closest('button')!)
    expect(onSelect).toHaveBeenCalledWith('report-1')
  })

  it('marks the selected week as aria-selected', async () => {
    const { WeeklyReportStepper } = await import('@/components/features/weekly-report/weekly-report-stepper')
    render(<WeeklyReportStepper reports={makeReports(3)} selectedId="report-0" onSelect={vi.fn()} />)

    const options = screen.getAllByRole('option')
    expect(options[0]).toHaveAttribute('aria-selected', 'true')
    expect(options[1]).toHaveAttribute('aria-selected', 'false')
  })

  it('forwards the picked week to onJumpToWeek via WeekPicker', async () => {
    const { WeeklyReportStepper } = await import('@/components/features/weekly-report/weekly-report-stepper')
    const onJumpToWeek = vi.fn()
    render(
      <WeeklyReportStepper
        reports={makeReports(2)}
        selectedId="report-0"
        onSelect={vi.fn()}
        onJumpToWeek={onJumpToWeek}
      />
    )
    fireEvent.click(screen.getByTestId('week-picker-select'))
    expect(onJumpToWeek).toHaveBeenCalledWith(new Date('2026-07-13'))
  })
})

describe('WeeklyReportStepper — hover auto-scroll', () => {
  it('nudges scrollTop while hovering the up chevron, and stops on mouse leave', async () => {
    vi.useFakeTimers()
    try {
      const { WeeklyReportStepper } = await import('@/components/features/weekly-report/weekly-report-stepper')
      withOverflow(500, 100, () => {
        render(<WeeklyReportStepper reports={makeReports(10)} selectedId="report-0" onSelect={vi.fn()} />)
        const up = screen.getByLabelText('Jump to newest week')
        const list = screen.getByRole('listbox')
        Object.defineProperty(list, 'scrollTop', { writable: true, value: 100 })

        fireEvent.mouseEnter(up)
        vi.advanceTimersByTime(60) // 3 ticks @ 20ms, -3 each
        expect(list.scrollTop).toBe(91)

        fireEvent.mouseLeave(up)
        const afterLeave = list.scrollTop
        vi.advanceTimersByTime(100)
        expect(list.scrollTop).toBe(afterLeave) // no further movement once stopped
      })
    } finally {
      vi.useRealTimers()
    }
  })

  it('nudges scrollTop in the opposite direction while hovering the down chevron', async () => {
    vi.useFakeTimers()
    try {
      const { WeeklyReportStepper } = await import('@/components/features/weekly-report/weekly-report-stepper')
      withOverflow(500, 100, () => {
        render(<WeeklyReportStepper reports={makeReports(10)} selectedId="report-0" onSelect={vi.fn()} />)
        const down = screen.getByLabelText('Jump to oldest week')
        const list = screen.getByRole('listbox')
        Object.defineProperty(list, 'scrollTop', { writable: true, value: 100 })

        fireEvent.mouseEnter(down)
        vi.advanceTimersByTime(60)
        expect(list.scrollTop).toBe(109)

        fireEvent.mouseLeave(down)
      })
    } finally {
      vi.useRealTimers()
    }
  })
})
