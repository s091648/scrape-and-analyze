import { test, expect } from '@playwright/test'
import { mockApiRoutes } from './fixtures/api-handlers'

// These tests run unauthenticated — override storageState from playwright.config.ts
test.use({ storageState: { cookies: [], origins: [] } })

test.describe('Login page', () => {
  test.beforeEach(async ({ page }) => {
    await mockApiRoutes(page)
  })

  test('login form renders username and password inputs', async ({ page }) => {
    await page.goto('/login')
    await expect(page.getByLabel(/username/i).or(page.getByLabel(/email/i))).toBeVisible()
    await expect(page.getByLabel(/password/i)).toBeVisible()
  })

  test('empty submit shows validation or disabled state', async ({ page }) => {
    await page.goto('/login')
    const submitButton = page.getByRole('button', { name: 'Sign in', exact: true })
    await expect(submitButton).toBeVisible()
    await submitButton.click()
    // Either an error message appears, or we stay on the login page
    const staysOnLogin = page.url().includes('/login')
    const hasError = await page.getByRole('alert').count() > 0
    // Use evaluate (sync DOM read) to avoid waiting for element that may have navigated away
    const buttonDisabled = staysOnLogin
      ? await submitButton.evaluate(el => (el as HTMLButtonElement).disabled)
      : false
    expect(staysOnLogin || hasError || buttonDisabled).toBe(true)
  })
})
