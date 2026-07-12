import { test, expect } from '@playwright/test'
import { dismissFeatureSpotlights } from './fixtures/api-handlers'

const articleWithCitation = {
  id: 'art-high-citation',
  title: 'High Citation Paper',
  source: 'openalex',
  content: 'Highly cited research.',
  published_at: '2026-01-10T00:00:00Z',
  scraped_at: '2026-01-11T00:00:00Z',
  url: 'https://openalex.org/high',
  metrics: { citation_count: 500 },
  view_count: 100,
}

const articleLowCitation = {
  id: 'art-low-citation',
  title: 'Low Citation Paper',
  source: 'arxiv',
  content: 'Less cited research.',
  published_at: '2026-01-12T00:00:00Z',
  scraped_at: '2026-01-13T00:00:00Z',
  url: 'https://arxiv.org/low',
  metrics: { citation_count: 5 },
  view_count: 10,
}

const citationCountMetricDefinition = {
  metric_key: 'citation_count',
  label_i18n_key: 'metrics.citation_count',
  icon_name: 'quote',
  format_hint: 'integer',
  unit: null,
}

async function mockArticlesSortedByCitation(page: any, order: 'asc' | 'desc' = 'desc') {
  const items = order === 'desc'
    ? [articleWithCitation, articleLowCitation]
    : [articleLowCitation, articleWithCitation]

  await page.route((url: URL) => url.pathname === '/api/proxy/articles', route => {
    const params = new URL(route.request().url()).searchParams
    if (params.get('sort') === 'citation_count') {
      route.fulfill({ json: { items, total: 2, page: 1, size: 20 } })
    } else {
      route.fulfill({ json: { items: [articleWithCitation, articleLowCitation], total: 2, page: 1, size: 20 } })
    }
  })
}

test.describe('Sort by citation count', () => {
  test.beforeEach(async ({ page }) => {
    await dismissFeatureSpotlights(page)
    // Mock supporting routes
    await page.route((url: URL) => url.pathname.startsWith('/api/proxy/'), route => {
      const p = new URL(route.request().url()).pathname
      if (p === '/api/proxy/topics') {
        return route.fulfill({ json: [{ id: 'topic-001', name: 'ai', display_name: 'AI Research', color_hex: null, sort_order: 1 }] })
      }
      if (p.includes('filters')) return route.fulfill({ json: [] })
      if (p.includes('source-categories')) return route.fulfill({ json: { aggregator: [], scraper: [] } })
      if (p.includes('tag-groups')) return route.fulfill({ json: [] })
      if (p.includes('chat/quota')) return route.fulfill({ json: { tier: 'admin', remaining: -1, limit: -1 } })
      if (p.includes('weekly-reports')) return route.fulfill({ json: null })
      if (p === '/api/proxy/metric-definitions') return route.fulfill({ json: [citationCountMetricDefinition] })
      route.fulfill({ status: 404, json: {} })
    })
    await mockArticlesSortedByCitation(page, 'desc')
  })

  test('sort dropdown changes URL to sort=citation_count', async ({ page }) => {
    await page.goto('/articles')
    await page.getByRole('button', { name: /sort by:/i }).click()
    await page.getByRole('option', { name: 'Citation Count', exact: true }).click()
    await expect(page).toHaveURL(/sort=citation_count/)
  })

  test('high citation count article appears first after sort', async ({ page }) => {
    await page.goto('/articles?sort=citation_count&order=desc')
    const titles = page.locator('[data-slot="card-title"]')
    const firstTitle = titles.first()
    await expect(firstTitle).toContainText('High Citation Paper')
  })

  test('sort value is reflected in the sort dropdown', async ({ page }) => {
    await page.goto('/articles?sort=citation_count')
    await expect(page.getByRole('button', { name: /sort by: citation count/i })).toBeVisible()
  })
})
