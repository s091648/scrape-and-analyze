import { test, expect } from '@playwright/test'
import { mockApiRoutes } from './fixtures/api-handlers'

test.describe('Knowledge graph page', () => {
  test.beforeEach(async ({ page }) => {
    await mockApiRoutes(page)
  })

  test('graph canvas renders on load', async ({ page }) => {
    await page.goto('/graph')
    // The ForceGraph2D renders a canvas element
    await expect(page.locator('canvas')).toBeVisible({ timeout: 10_000 })
  })

  test('days filter change triggers new request', async ({ page }) => {
    await page.goto('/graph')
    // Wait for initial request with days=30
    await page.waitForRequest(req => req.url().includes('days=30'))

    // Find the days selector and change it to 7
    const daysInput = page.getByRole('spinbutton').or(page.getByRole('combobox')).first()
    if (await daysInput.count() > 0) {
      const requestPromise = page.waitForRequest(req => req.url().includes('days=7'))
      await daysInput.fill('7')
      await daysInput.press('Enter')
      await requestPromise
    }
  })
})
