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
    // Find the add form — fill in name and URL
    const nameInput = page.getByLabel(/name/i)
    const urlInput = page.getByLabel(/url/i)
    await nameInput.fill('New RSS Source')
    await urlInput.fill('https://new.com/feed')
    // Submit via Add Source button
    const submitPromise = page.waitForRequest(req =>
      req.url().includes('/api/proxy/scraper-settings') && req.method() === 'POST'
    )
    await page.getByRole('button', { name: /add source/i }).click()
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
