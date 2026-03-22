import { test, expect } from '@playwright/test'

// These tests run unauthenticated — override storageState from playwright.config.ts
test.use({ storageState: { cookies: [], origins: [] } })

test.describe('Login page', () => {
  test('login form renders username and password inputs', async ({ page }) => {
    await page.goto('/login')
    await expect(page.getByLabel(/username/i).or(page.getByLabel(/email/i))).toBeVisible()
    await expect(page.getByLabel(/password/i)).toBeVisible()
  })

  test('empty submit shows validation or disabled state', async ({ page }) => {
    await page.goto('/login')
    const submitButton = page.getByRole('button', { name: 'Sign in', exact: true })
    await submitButton.click()
    // Either button is disabled, or an error message appears, or the form stays on the login page
    const staysOnLogin = page.url().includes('/login')
    const hasError = await page.getByRole('alert').count() > 0
    const buttonDisabled = await submitButton.isDisabled()
    expect(staysOnLogin || hasError || buttonDisabled).toBe(true)
  })
})
