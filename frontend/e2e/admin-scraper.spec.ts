import { test, expect } from '@playwright/test'
import { mockApiRoutes } from './fixtures/api-handlers'

test.describe('Admin scraper settings', () => {
  test.beforeEach(async ({ page }) => {
    await mockApiRoutes(page)
  })

  test('scraper settings list renders on load', async ({ page }) => {
    await page.goto('/admin/scraper-settings')
    await expect(page.getByText('TechCrunch RSS')).toBeVisible()
  })

  test('add RSS source via form and new item appears', async ({ page }) => {
    await page.goto('/admin/scraper-settings')
    // The RSS AddSourceCard is the last "Add source" button — click it to expand the form
    await page.getByRole('button', { name: 'Add source' }).last().click()
    // Labels lack htmlFor association — use placeholder selectors
    await page.getByPlaceholder('e.g. Hacker News').fill('New RSS Source')
    await page.getByPlaceholder('https://...').fill('https://new.com/feed')
    // Wait for POST request, then click the "Add" submit button (last on page = inside RSS form)
    const submitPromise = page.waitForRequest(req =>
      req.url().includes('/api/proxy/scraper-settings') && req.method() === 'POST'
    )
    await page.getByRole('button', { name: 'Add' }).last().click()
    await submitPromise
    // After POST, the new item should appear (page refetches or state updates)
    await expect(page.getByText('New RSS Source')).toBeVisible()
  })

  test('toggle active source to inactive', async ({ page }) => {
    await page.goto('/admin/scraper-settings')
    // Click the 'active' badge on TechCrunch RSS to toggle it inactive
    const patchPromise = page.waitForRequest(req =>
      req.url().includes('/api/proxy/scraper-settings/sc-001') && req.method() === 'PATCH'
    )
    await page.getByText('active').first().click()
    await patchPromise
    // Badge should now show inactive (after refetch/optimistic update)
    await expect(page.getByText('inactive').first()).toBeVisible()
  })
})
