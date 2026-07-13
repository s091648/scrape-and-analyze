import { test, expect } from '@playwright/test'
import { mockApiRoutes, dismissFeatureSpotlights } from './fixtures/api-handlers'

test.describe('Dark mode toggle', () => {
  test.beforeEach(async ({ page }) => {
    await dismissFeatureSpotlights(page)
    await mockApiRoutes(page)
  })

  test('first-time visitor defaults to auto (no stored preference)', async ({ page }) => {
    await page.goto('/articles')
    const stored = await page.evaluate(() => localStorage.getItem('app-theme-mode'))
    expect(stored).toBeNull()
    await expect(page.getByRole('button', { name: /^theme: auto$/i })).toBeVisible()
  })

  test('clicking the theme icon cycles light -> dark -> auto', async ({ page }) => {
    await page.goto('/articles')
    const themeButton = page.getByRole('button', { name: /^theme:/i })

    await themeButton.click()
    await expect(page.getByRole('button', { name: /^theme: light$/i })).toBeVisible()
    await expect(page.locator('html')).not.toHaveClass(/dark/)

    await themeButton.click()
    await expect(page.getByRole('button', { name: /^theme: dark$/i })).toBeVisible()
    await expect(page.locator('html')).toHaveClass(/dark/)

    await themeButton.click()
    await expect(page.getByRole('button', { name: /^theme: auto$/i })).toBeVisible()
  })

  test('dark mode selection persists in localStorage and across reload without flashing back to light', async ({ page }) => {
    await page.goto('/articles')
    const themeButton = page.getByRole('button', { name: /^theme:/i })
    await themeButton.click() // light
    await themeButton.click() // dark
    await expect(page.locator('html')).toHaveClass(/dark/)

    const stored = await page.evaluate(() => localStorage.getItem('app-theme-mode'))
    expect(stored).toBe('dark')

    await page.reload()
    await expect(page.locator('html')).toHaveClass(/dark/)
    await expect(page.getByRole('button', { name: /^theme: dark$/i })).toBeVisible()
  })

  test('hovering the theme icon shows a tooltip with the current mode name', async ({ page }) => {
    await page.goto('/articles')
    const themeButton = page.getByRole('button', { name: /^theme: auto$/i })
    const tooltip = page.locator('[data-slot="tooltip-content"]', { hasText: 'Auto' })

    // Radix Tooltip's delayDuration timer starts on a genuine pointer
    // transition onto the trigger, so we move away first. The exact sequence
    // of synthetic mouse events Playwright dispatches can rarely land in a
    // timing window where Radix's pointer state machine misses that
    // transition — retry the hover rather than fail on one missed attempt.
    await expect(async () => {
      await page.mouse.move(0, 0)
      await themeButton.hover()
      await expect(tooltip).toBeVisible({ timeout: 2000 })
    }).toPass({ timeout: 10000 })
  })
})
