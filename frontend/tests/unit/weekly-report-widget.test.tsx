import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor, fireEvent } from '@testing-library/react'

// jsdom does not implement scrollIntoView (used by CitedContent's citation-click handler)
Element.prototype.scrollIntoView = vi.fn()

vi.mock('@/components/features/articles/article-detail-dialog', () => ({
  ArticleDetailDialog: vi.fn(() => null),
}))

vi.mock('@/lib/api/articles', () => ({
  fetchArticleById: vi.fn().mockResolvedValue(null),
}))

let mockPinnedArticleState: { pinnedArticles: { id: string; title: string }[] } = { pinnedArticles: [] }
const mockPinArticles = vi.fn()
const mockRemovePinnedArticle = vi.fn()

vi.mock('@/lib/providers', () => ({
  useI18n: () => ({
    locale: 'en',
    t: (key: string, params?: Record<string, any>) => {
      const map: Record<string, string> = {
        'weeklyReport.noReportYet': 'No report for this week yet.',
        'weeklyReport.articleCount': `${params?.count ?? 0} articles`,
        'weeklyReport.selectWeek': 'Select report week',
        'weeklyReport.pinReport': "Ask AI about this week's report",
        'weeklyReport.unpinReport': "Remove this report's articles from AI chat",
      }
      return map[key] ?? key
    },
  }),
  usePinnedArticle: () => ({
    pinnedArticles: mockPinnedArticleState.pinnedArticles,
    pinArticles: mockPinArticles,
    removePinnedArticle: mockRemovePinnedArticle,
    areAllPinned: (ids: string[]) => ids.length > 0 && ids.every(id => mockPinnedArticleState.pinnedArticles.some(a => a.id === id)),
  }),
}))

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
  sources: [],
}

vi.mock('@/lib/api/weekly-reports', () => ({
  fetchLatestWeeklyReport: vi.fn(),
  fetchWeeklyReports: vi.fn(),
  fetchWeeklyReportByWeek: vi.fn(),
  fetchWeeklyReportWeeks: vi.fn().mockResolvedValue([]),
}))

import { fetchLatestWeeklyReport, fetchWeeklyReports } from '@/lib/api/weekly-reports'

describe('WeeklyReportWidget', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockPinnedArticleState.pinnedArticles = []
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

  it('renders a clickable citation marker when summary_text references a source', async () => {
    const citedReport = {
      ...mockReport,
      summary_text: 'A great week in AI research [1].',
      sources: [{ id: 'article-1', title: 'Paper One', url: 'https://example.com/paper-1', public_article_id: 'article-1' }],
    }
    vi.mocked(fetchLatestWeeklyReport).mockResolvedValue(citedReport)
    vi.mocked(fetchWeeklyReports).mockResolvedValue({ items: [citedReport], total: 1, page: 1, size: 10 })

    const { WeeklyReportWidget } = await import('@/components/features/weekly-report/weekly-report-widget')
    render(<WeeklyReportWidget topicId="topic-1" />)

    await waitFor(() => {
      expect(screen.getByRole('button', { name: /paper one/i })).toBeInTheDocument()
    })
  })

  // ── Pin report into chat (2026-07-12, US7) ───────────────────────────────

  it('does not show a pin control when the report has no sources', async () => {
    vi.mocked(fetchLatestWeeklyReport).mockResolvedValue(mockReport)
    vi.mocked(fetchWeeklyReports).mockResolvedValue({ items: [mockReport], total: 1, page: 1, size: 10 })

    const { WeeklyReportWidget } = await import('@/components/features/weekly-report/weekly-report-widget')
    render(<WeeklyReportWidget topicId="topic-1" />)

    await waitFor(() => {
      expect(screen.getByText('AI Weekly Highlights')).toBeInTheDocument()
    })
    expect(screen.queryByLabelText("Ask AI about this week's report")).not.toBeInTheDocument()
  })

  it('pins all cited articles when the pin control is activated and none are pinned yet', async () => {
    const citedReport = {
      ...mockReport,
      sources: [
        { id: 'a1', title: 'Paper One', url: 'https://example.com/1', public_article_id: 'a1' },
        { id: 'a2', title: 'Paper Two', url: 'https://example.com/2', public_article_id: 'a2' },
      ],
    }
    vi.mocked(fetchLatestWeeklyReport).mockResolvedValue(citedReport)
    vi.mocked(fetchWeeklyReports).mockResolvedValue({ items: [citedReport], total: 1, page: 1, size: 10 })

    const { WeeklyReportWidget } = await import('@/components/features/weekly-report/weekly-report-widget')
    render(<WeeklyReportWidget topicId="topic-1" />)

    const pinButton = await screen.findByLabelText("Ask AI about this week's report")
    fireEvent.click(pinButton)

    expect(mockPinArticles).toHaveBeenCalledWith([
      { id: 'a1', title: 'Paper One', tags: [] },
      { id: 'a2', title: 'Paper Two', tags: [] },
    ])
  })

  it('unpins all cited articles when the pin control is activated and all are already pinned', async () => {
    const citedReport = {
      ...mockReport,
      sources: [
        { id: 'a1', title: 'Paper One', url: 'https://example.com/1', public_article_id: 'a1' },
        { id: 'a2', title: 'Paper Two', url: 'https://example.com/2', public_article_id: 'a2' },
      ],
    }
    mockPinnedArticleState.pinnedArticles = [{ id: 'a1', title: 'Paper One' }, { id: 'a2', title: 'Paper Two' }]
    vi.mocked(fetchLatestWeeklyReport).mockResolvedValue(citedReport)
    vi.mocked(fetchWeeklyReports).mockResolvedValue({ items: [citedReport], total: 1, page: 1, size: 10 })

    const { WeeklyReportWidget } = await import('@/components/features/weekly-report/weekly-report-widget')
    render(<WeeklyReportWidget topicId="topic-1" />)

    const pinButton = await screen.findByLabelText("Remove this report's articles from AI chat")
    fireEvent.click(pinButton)

    expect(mockRemovePinnedArticle).toHaveBeenCalledWith('a1')
    expect(mockRemovePinnedArticle).toHaveBeenCalledWith('a2')
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
