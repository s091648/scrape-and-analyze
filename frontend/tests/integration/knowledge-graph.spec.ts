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

  test('initial graph request includes published_after and topic_id', async ({ page }) => {
    await page.goto('/graph')
    // The component defaults to published_after ~30 days ago; wait for that request
    const req = await page.waitForRequest(
      r => r.url().includes('analyses/graph') && r.url().includes('published_after=')
    )
    expect(req.url()).toContain('topic_id=')
  })
})
