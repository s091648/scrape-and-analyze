import { test, expect } from '@playwright/test'
import { mockApiRoutes } from './fixtures/api-handlers'

test.describe('Admin monitoring page', () => {
  test.beforeEach(async ({ page }) => {
    await mockApiRoutes(page)

    // Mock Grafana proxy endpoints to return "not_configured" (no env vars in test env)
    await page.route('**/api/proxy/grafana/**', route => {
      route.fulfill({
        status: 403,
        contentType: 'application/json',
        body: JSON.stringify({ error: 'not_configured' }),
      })
    })
  })

  test('monitoring page renders without crashing when Grafana not configured', async ({ page }) => {
    await page.goto('/admin/monitoring')
    // Page should load and show monitoring heading
    await expect(page.getByRole('heading', { level: 1 })).toBeVisible()
    // Operations tab should be active by default
    await expect(page.getByRole('tab', { name: /operations/i })).toBeVisible()
  })

  test('shows "Grafana not configured" placeholder for each chart panel', async ({ page }) => {
    await page.goto('/admin/monitoring')
    // Wait for loading states to resolve
    await page.waitForTimeout(1000)
    const placeholders = page.getByText('Grafana not configured')
    // Multiple panels should show the placeholder
    await expect(placeholders.first()).toBeVisible()
  })

  test('logs tab renders log table placeholders', async ({ page }) => {
    await page.goto('/admin/monitoring')
    await page.getByRole('tab', { name: /logs/i }).click()
    await page.waitForTimeout(500)
    const placeholders = page.getByText('Grafana not configured')
    await expect(placeholders.first()).toBeVisible()
  })

  test('traces tab renders trace table placeholder', async ({ page }) => {
    await page.goto('/admin/monitoring')
    await page.getByRole('tab', { name: /traces/i }).click()
    await page.waitForTimeout(500)
    const placeholder = page.getByText('Grafana not configured').first()
    await expect(placeholder).toBeVisible()
  })
})
