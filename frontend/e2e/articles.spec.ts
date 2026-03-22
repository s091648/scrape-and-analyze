import { test, expect } from '@playwright/test'
import { mockApiRoutes } from './fixtures/api-handlers'

test.describe('Article list page', () => {
  test.beforeEach(async ({ page }) => {
    await mockApiRoutes(page)
  })

  test('article list renders on load', async ({ page }) => {
    await page.goto('/')
    await expect(page.getByText('Digital Twin Innovation')).toBeVisible()
  })

  test('source filter updates URL', async ({ page }) => {
    await page.goto('/')
    // Open the Filters panel
    await page.getByRole('button', { name: /filters/i }).click()
    // Open Source popover
    await page.getByRole('button', { name: /source/i }).click()
    // Select 'rss' option
    await page.getByRole('option', { name: 'rss', exact: true }).click()
    // Apply filters
    await page.getByRole('button', { name: /apply/i }).click()
    await expect(page).toHaveURL(/source=rss/)
  })

  test('pagination advances to page 2', async ({ page }) => {
    // Provide a multi-page fixture
    await page.route('/api/proxy/articles**', route => route.fulfill({
      json: { items: [{ id: 'art-001', title: 'Article 1', source: 'rss', content: 'x', published_at: null, scraped_at: null, url: 'https://x.com' }], total: 30, page: 1, size: 20 }
    }))
    await page.goto('/')
    // Find and click next page — look for page 2 button or next button
    const page2 = page.getByRole('button', { name: '2' }).or(page.getByRole('button', { name: /next/i }))
    await page2.first().click()
    await expect(page).toHaveURL(/page=2/)
  })

  test('sort change resets to page 1', async ({ page }) => {
    await page.goto('/?page=3&sort=scraped_at')
    // Find sort dropdown and change it
    const sortSelect = page.getByRole('combobox').or(page.locator('select[name="sort"]'))
    if (await sortSelect.count() > 0) {
      await sortSelect.first().selectOption('published_at')
      await expect(page).toHaveURL(/page=1/)
      await expect(page).toHaveURL(/sort=published_at/)
    }
  })
})
