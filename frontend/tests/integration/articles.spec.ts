import { test, expect } from '@playwright/test'
import { mockApiRoutes, dismissFeatureSpotlights } from './fixtures/api-handlers'

test.describe('Article list page', () => {
  test.beforeEach(async ({ page }) => {
    await dismissFeatureSpotlights(page)
    await mockApiRoutes(page)
  })

  test('article list renders on load', async ({ page }) => {
    await page.goto('/articles')
    await expect(page.getByText('Digital Twin Innovation')).toBeVisible()
  })

  test('source filter updates URL', async ({ page }) => {
    await page.goto('/articles')
    // Open the Filters panel
    await page.getByRole('button', { name: /filters/i }).click()
    // Open Source popover
    await page.getByRole('button', { name: /source/i }).click()
    // Select 'rss' option
    await page.getByRole('option', { name: 'rss', exact: true }).click()
    // Apply filters
    await page.getByRole('button', { name: /apply/i }).click()
    await expect(page).toHaveURL(/original_source=rss/)
  })

  test('pagination advances to page 2', async ({ page }) => {
    // Provide a multi-page fixture
    await page.route('/api/proxy/articles**', route => route.fulfill({
      json: { items: [{ id: 'art-001', title: 'Article 1', source: 'rss', content: 'x', published_at: null, scraped_at: null, url: 'https://x.com' }], total: 30, page: 1, size: 20 }
    }))
    await page.goto('/articles')
    // Find and click next page — look for page 2 button or next button.
    // Anchored regex so this doesn't also match Next.js's own
    // "Open Next.js Dev Tools" floating button in dev mode.
    const page2 = page.getByRole('button', { name: '2' }).or(page.getByRole('button', { name: /^next$/i }))
    await page2.first().click()
    await expect(page).toHaveURL(/page=2/)
  })

  test('aggregator filter updates URL and re-fetches with the aggregator param', async ({ page }) => {
    await page.goto('/articles')
    await page.getByRole('button', { name: /filters/i }).click()
    await page.getByRole('button', { name: /aggregator/i }).click()
    await page.getByRole('option', { name: /semantic scholar/i }).click()

    const fetchPromise = page.waitForRequest(req =>
      req.url().includes('/api/proxy/articles') && req.url().includes('aggregator=semantic_scholar')
    )
    await page.getByRole('button', { name: /apply/i }).click()
    await fetchPromise
    await expect(page).toHaveURL(/aggregator=semantic_scholar/)
  })

  test('sort change resets to page 1', async ({ page }) => {
    await page.route('/api/proxy/articles**', route => route.fulfill({
      json: { items: [{ id: 'art-001', title: 'Article 1', source: 'rss', content: 'x', published_at: null, scraped_at: null, url: 'https://x.com' }], total: 30, page: 3, size: 20 }
    }))
    await page.goto('/articles?page=3&sort=scraped_at')
    await page.getByRole('button', { name: /sort by:/i }).click()
    await page.getByRole('option', { name: 'Published At', exact: true }).click()
    await expect(page).toHaveURL(/page=1/)
    await expect(page).toHaveURL(/sort=published_at/)
  })
})

test.describe('Article list page — source attribution badges', () => {
  test.beforeEach(async ({ page }) => {
    await dismissFeatureSpotlights(page)
    await mockApiRoutes(page)
  })

  async function mockSingleArticle(page: import('@playwright/test').Page, article: Record<string, unknown>) {
    await page.route(
      (url: URL) => url.pathname.startsWith('/api/proxy/articles') && !url.pathname.includes('/articles/'),
      route => route.fulfill({ json: { items: [article], total: 1, page: 1, size: 20 } })
    )
  }

  test('OpenAlex article with an arXiv ID shows "arxiv" + "via OpenAlex"', async ({ page }) => {
    await mockSingleArticle(page, {
      id: 'art-oa-1', title: 'OpenAlex ArXiv Paper', source: 'openalex', via_source: 'openalex',
      original_source: 'arxiv', content: 'x', published_at: null, scraped_at: null,
      url: 'https://openalex.org/W123',
    })
    await page.goto('/articles')
    await expect(page.getByText('arxiv', { exact: true })).toBeVisible()
    await expect(page.getByText('via OpenAlex')).toBeVisible()
  })

  test('OpenAlex article without an arXiv ID shows the journal name + "via OpenAlex"', async ({ page }) => {
    await mockSingleArticle(page, {
      id: 'art-oa-2', title: 'Journal Paper', source: 'openalex', via_source: 'openalex',
      original_source: 'Nature Neuroscience', content: 'x', published_at: null, scraped_at: null,
      url: 'https://openalex.org/W456',
    })
    await page.goto('/articles')
    await expect(page.getByText('Nature Neuroscience')).toBeVisible()
    await expect(page.getByText('via OpenAlex')).toBeVisible()
  })

  test('Semantic Scholar article with an arXiv ID shows "arxiv" + "via Semantic Scholar"', async ({ page }) => {
    await mockSingleArticle(page, {
      id: 'art-ss-1', title: 'Semantic Scholar Paper', source: 'semantic_scholar', via_source: 'semantic_scholar',
      original_source: 'arxiv', content: 'x', published_at: null, scraped_at: null,
      url: 'https://semanticscholar.org/p/789',
    })
    await page.goto('/articles')
    await expect(page.getByText('arxiv', { exact: true })).toBeVisible()
    await expect(page.getByText('via Semantic Scholar')).toBeVisible()
  })

  test('directly-scraped arXiv article shows "arxiv" with no "via" tag', async ({ page }) => {
    await mockSingleArticle(page, {
      id: 'art-direct-1', title: 'Direct ArXiv Paper', source: 'arxiv', via_source: null,
      original_source: null, content: 'x', published_at: null, scraped_at: null,
      url: 'https://arxiv.org/abs/1234',
    })
    await page.goto('/articles')
    await expect(page.getByText('arxiv', { exact: true })).toBeVisible()
    await expect(page.getByText(/via /)).not.toBeVisible()
  })
})
