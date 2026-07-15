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

let capturedOnDragEnd: ((event: any) => void) | undefined
vi.mock('@dnd-kit/core', () => ({
  DndContext: ({ children, onDragEnd }: any) => {
    capturedOnDragEnd = onDragEnd
    return children
  },
  DragOverlay: ({ children }: any) => children,
  useDraggable: () => ({ attributes: {}, listeners: {}, setNodeRef: () => {}, isDragging: false }),
}))

let mockPinnedArticleState: { pinnedArticles: { id: string; title: string }[] } = { pinnedArticles: [] }
const mockPinArticles = vi.fn()
const mockPinGroup = vi.fn()
const mockRemoveGroup = vi.fn()

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
        'weeklyReport.switchToChat': 'View chat',
        'weeklyReport.switchToReport': "View this week's report",
      }
      return map[key] ?? key
    },
  }),
  usePinnedArticle: () => ({
    pinnedArticles: mockPinnedArticleState.pinnedArticles,
    pinArticles: mockPinArticles,
    pinGroup: mockPinGroup,
    removeGroup: mockRemoveGroup,
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

    // Source pills are collapsed by default (2026-07-14, US10) — expand via the article-count toggle first.
    const disclosure = await screen.findByText('5 articles')
    fireEvent.click(disclosure)

    await waitFor(() => {
      expect(screen.getByRole('button', { name: /paper one/i })).toBeInTheDocument()
    })
  })

  it('expands the collapsed source list and highlights the matching chip when an inline citation is clicked', async () => {
    const citedReport = {
      ...mockReport,
      summary_text: 'A great week in AI research [1].',
      sources: [{ id: 'article-1', title: 'Paper One', url: 'https://example.com/paper-1', public_article_id: 'article-1' }],
    }
    vi.mocked(fetchLatestWeeklyReport).mockResolvedValue(citedReport)
    vi.mocked(fetchWeeklyReports).mockResolvedValue({ items: [citedReport], total: 1, page: 1, size: 10 })

    const { WeeklyReportWidget } = await import('@/components/features/weekly-report/weekly-report-widget')
    render(<WeeklyReportWidget topicId="topic-1" />)

    // Click the inline [1] marker directly, without expanding the source list first.
    const marker = await screen.findByTitle('Paper One')
    expect(screen.queryByRole('button', { name: /paper one/i })).not.toBeInTheDocument()
    fireEvent.click(marker)

    const chip = await screen.findByRole('button', { name: /paper one/i })
    expect(chip.className).toContain('ring-2')
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

    expect(mockPinGroup).toHaveBeenCalledWith({
      id: 'report-1',
      dateLabel: expect.any(String),
      articles: [
        { id: 'a1', title: 'Paper One', tags: [] },
        { id: 'a2', title: 'Paper Two', tags: [] },
      ],
    })
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

    expect(mockRemoveGroup).toHaveBeenCalledWith('report-1')
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

  // ── Collapsible source pills (2026-07-14, US10) ──────────────────────────

  it('keeps the source pill list collapsed by default', async () => {
    const citedReport = {
      ...mockReport,
      summary_text: 'A great week in AI research [1].',
      sources: [{ id: 'article-1', title: 'Paper One', url: 'https://example.com/paper-1', public_article_id: 'article-1' }],
    }
    vi.mocked(fetchLatestWeeklyReport).mockResolvedValue(citedReport)
    vi.mocked(fetchWeeklyReports).mockResolvedValue({ items: [citedReport], total: 1, page: 1, size: 10 })

    const { WeeklyReportWidget } = await import('@/components/features/weekly-report/weekly-report-widget')
    render(<WeeklyReportWidget topicId="topic-1" />)

    await screen.findByText('5 articles')
    expect(screen.queryByRole('button', { name: /paper one/i })).not.toBeInTheDocument()
  })

  it('collapses the source pill list again after switching to a different report', async () => {
    const report2 = {
      ...mockReport,
      id: 'report-2',
      week_start_date: '2026-06-09',
      title: 'Previous Week',
      summary_text: 'Previous week research [1].',
      sources: [{ id: 'article-2', title: 'Paper Two', url: 'https://example.com/paper-2', public_article_id: 'article-2' }],
    }
    vi.mocked(fetchLatestWeeklyReport).mockResolvedValue(mockReport)
    vi.mocked(fetchWeeklyReports).mockResolvedValue({ items: [mockReport, report2], total: 2, page: 1, size: 10 })

    const { WeeklyReportWidget } = await import('@/components/features/weekly-report/weekly-report-widget')
    render(<WeeklyReportWidget topicId="topic-1" />)

    await waitFor(() => expect(screen.getByText('AI Weekly Highlights')).toBeInTheDocument())
    fireEvent.click(screen.getByText('5 articles'))

    const options = screen.getAllByRole('option')
    fireEvent.click(options[1])

    await waitFor(() => expect(screen.getByText('Previous Week')).toBeInTheDocument())
    expect(screen.queryByRole('button', { name: /paper two/i })).not.toBeInTheDocument()
  })

  // ── Drag a source pill into the chat dropzone (2026-07-14, US10) ─────────

  it('pins the dragged article when dropped on the chat input dropzone', async () => {
    vi.mocked(fetchLatestWeeklyReport).mockResolvedValue(mockReport)
    vi.mocked(fetchWeeklyReports).mockResolvedValue({ items: [mockReport], total: 1, page: 1, size: 10 })

    const { WeeklyReportWidget } = await import('@/components/features/weekly-report/weekly-report-widget')
    render(<WeeklyReportWidget topicId="topic-1" />)
    await waitFor(() => expect(screen.getByText('AI Weekly Highlights')).toBeInTheDocument())

    capturedOnDragEnd?.({
      over: { id: 'chat-input-dropzone' },
      active: { data: { current: { article: { id: 'a9', title: 'Dragged Paper' } } } },
    })

    expect(mockPinArticles).toHaveBeenCalledWith([{ id: 'a9', title: 'Dragged Paper' }])
  })

  // ── Report/chat card switching (2026-07-14) ───────────────────────────────

  it('stacks the report and chat children as today, before any conversation starts', async () => {
    vi.mocked(fetchLatestWeeklyReport).mockResolvedValue(mockReport)
    vi.mocked(fetchWeeklyReports).mockResolvedValue({ items: [mockReport], total: 1, page: 1, size: 10 })

    const { WeeklyReportWidget } = await import('@/components/features/weekly-report/weekly-report-widget')
    render(
      <WeeklyReportWidget topicId="topic-1">
        {({ onSend }) => <button data-testid="fake-chat" onClick={onSend}>chat</button>}
      </WeeklyReportWidget>
    )

    await waitFor(() => expect(screen.getByText('AI Weekly Highlights')).toBeInTheDocument())
    // Both visible at once — no card-swap yet, and no switch button either.
    expect(screen.getByTestId('fake-chat')).toBeInTheDocument()
    expect(screen.queryByLabelText('View chat')).not.toBeInTheDocument()
  })

  it('shows the switch button once the child calls onSend, and hides (but does not unmount) the report card', async () => {
    vi.mocked(fetchLatestWeeklyReport).mockResolvedValue(mockReport)
    vi.mocked(fetchWeeklyReports).mockResolvedValue({ items: [mockReport], total: 1, page: 1, size: 10 })

    const { WeeklyReportWidget } = await import('@/components/features/weekly-report/weekly-report-widget')
    render(
      <WeeklyReportWidget topicId="topic-1">
        {({ onSend }) => <button data-testid="fake-chat" onClick={onSend}>chat</button>}
      </WeeklyReportWidget>
    )

    await waitFor(() => expect(screen.getByText('AI Weekly Highlights')).toBeInTheDocument())
    fireEvent.click(screen.getByTestId('fake-chat'))

    await waitFor(() => {
      expect(screen.getByLabelText('View this week\'s report')).toBeInTheDocument()
    })
    // Report card stays mounted (2026-07-15 fix) — merely hidden via opacity/pointer-events, so
    // an in-flight chat response is never abandoned just because the report is what's on screen.
    const heading = screen.getByText('AI Weekly Highlights')
    expect(heading.closest('.opacity-0.pointer-events-none')).not.toBeNull()
  })

  it('switch button toggles back and forth between the report and chat cards', async () => {
    vi.mocked(fetchLatestWeeklyReport).mockResolvedValue(mockReport)
    vi.mocked(fetchWeeklyReports).mockResolvedValue({ items: [mockReport], total: 1, page: 1, size: 10 })

    const { WeeklyReportWidget } = await import('@/components/features/weekly-report/weekly-report-widget')
    render(
      <WeeklyReportWidget topicId="topic-1">
        {({ onSend }) => <button data-testid="fake-chat" onClick={onSend}>chat</button>}
      </WeeklyReportWidget>
    )

    await waitFor(() => expect(screen.getByText('AI Weekly Highlights')).toBeInTheDocument())
    fireEvent.click(screen.getByTestId('fake-chat'))
    await waitFor(() => expect(screen.getByLabelText('View this week\'s report')).toBeInTheDocument())

    fireEvent.click(screen.getByLabelText('View this week\'s report'))
    await waitFor(() => expect(screen.getByText('AI Weekly Highlights')).toBeInTheDocument())
    expect(screen.getByLabelText('View chat')).toBeInTheDocument()
  })

  it('does not pin when dropped outside the chat input dropzone', async () => {
    vi.mocked(fetchLatestWeeklyReport).mockResolvedValue(mockReport)
    vi.mocked(fetchWeeklyReports).mockResolvedValue({ items: [mockReport], total: 1, page: 1, size: 10 })

    const { WeeklyReportWidget } = await import('@/components/features/weekly-report/weekly-report-widget')
    render(<WeeklyReportWidget topicId="topic-1" />)
    await waitFor(() => expect(screen.getByText('AI Weekly Highlights')).toBeInTheDocument())

    capturedOnDragEnd?.({
      over: null,
      active: { data: { current: { article: { id: 'a9', title: 'Dragged Paper' } } } },
    })

    expect(mockPinArticles).not.toHaveBeenCalled()
  })
})
