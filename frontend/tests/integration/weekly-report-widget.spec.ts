import { test, expect } from '@playwright/test'

const mockReport1 = {
  id: 'report-001',
  topic_id: 'topic-001',
  week_start_date: '2026-06-16',
  title: 'AI Weekly: Multimodal Breakthroughs',
  summary_text: 'Major advances in multimodal AI this week.',
  cover_image_url: null,
  article_count: 8,
  status: 'completed',
  created_at: '2026-06-23T00:00:00Z',
}

const mockReport2 = {
  id: 'report-002',
  topic_id: 'topic-001',
  week_start_date: '2026-06-09',
  title: 'AI Weekly: LLM Efficiency',
  summary_text: 'Focus on LLM efficiency improvements.',
  cover_image_url: null,
  article_count: 5,
  status: 'completed',
  created_at: '2026-06-16T00:00:00Z',
}

async function mockWeeklyReportRoutes(page: any, reports: any[] = [mockReport1]) {
  await page.route((url: URL) => url.pathname === '/api/proxy/weekly-reports/latest', route =>
    route.fulfill({ json: reports[0] ?? null })
  )
  await page.route((url: URL) => url.pathname === '/api/proxy/weekly-reports', route =>
    route.fulfill({ json: { items: reports, total: reports.length, page: 1, size: 10 } })
  )
}

async function mockBaseRoutes(page: any) {
  await page.route((url: URL) => url.pathname.startsWith('/api/proxy/'), route => {
    const p = url.pathname
    if (p === '/api/proxy/topics') return route.fulfill({ json: [{ id: 'topic-001', name: 'ai', display_name: 'AI Research', color_hex: null, sort_order: 1 }] })
    if (p.includes('articles') && !p.includes('weekly')) return route.fulfill({ json: { items: [], total: 0, page: 1, size: 20 } })
    if (p.includes('filters')) return route.fulfill({ json: [] })
    if (p.includes('source-categories')) return route.fulfill({ json: { aggregator: [], scraper: [] } })
    route.fulfill({ status: 404, json: {} })
  })
}

test.describe('WeeklyReportWidget', () => {
  test('displays weekly report title on homepage when topic selected', async ({ page }) => {
    await mockBaseRoutes(page)
    await mockWeeklyReportRoutes(page, [mockReport1])

    await page.goto('/')
    await expect(page.getByText('AI Weekly: Multimodal Breakthroughs')).toBeVisible({ timeout: 10000 })
  })

  test('shows empty state when no report exists', async ({ page }) => {
    await mockBaseRoutes(page)
    await page.route((url: URL) => url.pathname === '/api/proxy/weekly-reports/latest', route =>
      route.fulfill({ json: null })
    )
    await page.route((url: URL) => url.pathname === '/api/proxy/weekly-reports', route =>
      route.fulfill({ json: { items: [], total: 0, page: 1, size: 10 } })
    )

    await page.goto('/')
    await expect(page.getByText(/no report for this week yet/i)).toBeVisible({ timeout: 10000 })
  })

  test('week stepper appears when multiple reports exist', async ({ page }) => {
    await mockBaseRoutes(page)
    await mockWeeklyReportRoutes(page, [mockReport1, mockReport2])

    await page.goto('/')
    await expect(page.getByRole('listbox', { name: /select report week/i })).toBeVisible({ timeout: 10000 })
    await expect(page.getByRole('option')).toHaveCount(2)
  })

  test('selecting a different week updates the displayed report', async ({ page }) => {
    await mockBaseRoutes(page)
    await mockWeeklyReportRoutes(page, [mockReport1, mockReport2])

    await page.goto('/')
    await expect(page.getByText('AI Weekly: Multimodal Breakthroughs')).toBeVisible({ timeout: 10000 })

    // Select the second report from the week stepper
    await page.getByRole('option').last().click()
    await expect(page.getByText('AI Weekly: LLM Efficiency')).toBeVisible()
  })

  test('clicking the report panel opens the detail dialog', async ({ page }) => {
    await mockBaseRoutes(page)
    await mockWeeklyReportRoutes(page, [mockReport1])

    await page.goto('/')
    await expect(page.getByText('AI Weekly: Multimodal Breakthroughs')).toBeVisible({ timeout: 10000 })

    await page.getByText('AI Weekly: Multimodal Breakthroughs').click()
    await expect(page.getByRole('dialog')).toBeVisible()
    await expect(page.getByRole('dialog').getByText('Major advances in multimodal AI this week.')).toBeVisible()
  })
})
