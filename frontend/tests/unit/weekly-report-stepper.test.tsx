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
  WeekPicker: () => <div data-testid="week-picker" />,
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
})
