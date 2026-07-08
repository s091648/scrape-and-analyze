import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor, fireEvent } from '@testing-library/react'

const mockReport = {
  id: 'report-1',
  topic_id: 'topic-1',
  week_start_date: '2026-06-16',
  title: 'AI Weekly Highlights',
  summary_text: 'A great week in AI research.',
  cover_image_url: null,
  article_count: 5,
  status: 'completed',
  created_at: '2026-06-23T00:00:00Z',
}

vi.mock('@/lib/api/weekly-reports', () => ({
  fetchLatestWeeklyReport: vi.fn(),
  fetchWeeklyReports: vi.fn(),
}))

import { fetchLatestWeeklyReport, fetchWeeklyReports } from '@/lib/api/weekly-reports'

describe('WeeklyReportWidget', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('renders nothing when topicId is null', async () => {
    const { WeeklyReportWidget } = await import('@/components/features/weekly-report/weekly-report-widget')
    const { container } = render(<WeeklyReportWidget topicId={null} />)
    expect(container.firstChild).toBeNull()
  })

  it('shows empty state placeholder when no report exists', async () => {
    vi.mocked(fetchLatestWeeklyReport).mockResolvedValue(null)
    vi.mocked(fetchWeeklyReports).mockResolvedValue({ items: [], total: 0, page: 1, size: 10 })

    const { WeeklyReportWidget } = await import('@/components/features/weekly-report/weekly-report-widget')
    render(<WeeklyReportWidget topicId="topic-1" />)

    await waitFor(() => {
      expect(screen.getByText(/no report for this week yet/i)).toBeInTheDocument()
    })
  })

  it('shows report title when report exists', async () => {
    vi.mocked(fetchLatestWeeklyReport).mockResolvedValue(mockReport)
    vi.mocked(fetchWeeklyReports).mockResolvedValue({ items: [mockReport], total: 1, page: 1, size: 10 })

    const { WeeklyReportWidget } = await import('@/components/features/weekly-report/weekly-report-widget')
    render(<WeeklyReportWidget topicId="topic-1" />)

    await waitFor(() => {
      expect(screen.getByText('AI Weekly Highlights')).toBeInTheDocument()
    })
  })

  it('shows report summary text', async () => {
    vi.mocked(fetchLatestWeeklyReport).mockResolvedValue(mockReport)
    vi.mocked(fetchWeeklyReports).mockResolvedValue({ items: [mockReport], total: 1, page: 1, size: 10 })

    const { WeeklyReportWidget } = await import('@/components/features/weekly-report/weekly-report-widget')
    render(<WeeklyReportWidget topicId="topic-1" />)

    await waitFor(() => {
      expect(screen.getByText('A great week in AI research.')).toBeInTheDocument()
    })
  })

  it('renders week stepper when multiple reports exist', async () => {
    const report2 = { ...mockReport, id: 'report-2', week_start_date: '2026-06-09', title: 'Previous Week' }
    vi.mocked(fetchLatestWeeklyReport).mockResolvedValue(mockReport)
    vi.mocked(fetchWeeklyReports).mockResolvedValue({ items: [mockReport, report2], total: 2, page: 1, size: 10 })

    const { WeeklyReportWidget } = await import('@/components/features/weekly-report/weekly-report-widget')
    render(<WeeklyReportWidget topicId="topic-1" />)

    await waitFor(() => {
      expect(screen.getByRole('listbox')).toBeInTheDocument()
      expect(screen.getAllByRole('option')).toHaveLength(2)
    })
  })

  it('does not render stepper when only one report', async () => {
    vi.mocked(fetchLatestWeeklyReport).mockResolvedValue(mockReport)
    vi.mocked(fetchWeeklyReports).mockResolvedValue({ items: [mockReport], total: 1, page: 1, size: 10 })

    const { WeeklyReportWidget } = await import('@/components/features/weekly-report/weekly-report-widget')
    render(<WeeklyReportWidget topicId="topic-1" />)

    await waitFor(() => {
      expect(screen.queryByRole('listbox')).not.toBeInTheDocument()
    })
  })

  it('selecting a different week option updates the displayed report', async () => {
    const report2 = { ...mockReport, id: 'report-2', week_start_date: '2026-06-09', title: 'Previous Week' }
    vi.mocked(fetchLatestWeeklyReport).mockResolvedValue(mockReport)
    vi.mocked(fetchWeeklyReports).mockResolvedValue({ items: [mockReport, report2], total: 2, page: 1, size: 10 })

    const { WeeklyReportWidget } = await import('@/components/features/weekly-report/weekly-report-widget')
    render(<WeeklyReportWidget topicId="topic-1" />)

    await waitFor(() => {
      expect(screen.getByText('AI Weekly Highlights')).toBeInTheDocument()
    })

    const options = screen.getAllByRole('option')
    fireEvent.click(options[1])

    await waitFor(() => {
      expect(screen.getByText('Previous Week')).toBeInTheDocument()
    })
  })
})
