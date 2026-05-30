import { test, expect } from '@playwright/test'
import { mockApiRoutes, articleListFixture, graphFixture } from './fixtures/api-handlers'

test.use({ storageState: { cookies: [], origins: [] } })

test.describe('Guest Mode', () => {
  test.beforeEach(async ({ page }) => {
    await mockApiRoutes(page)
  })

  test('login page shows "Continue as Guest" button', async ({ page }) => {
    await page.goto('/login')
    await expect(page.getByRole('button', { name: /continue as guest|以訪客身份繼續/i })).toBeVisible()
  })

  test('clicking "Continue as Guest" redirects to home with real articles (no blur)', async ({ page }) => {
    await page.goto('/login')
    await page.getByRole('button', { name: /continue as guest|以訪客身份繼續/i }).click()
    await page.waitForURL('/')

    // Should NOT show blurred placeholder articles
    const blurredEl = page.locator('.blur-\\[2px\\]')
    await expect(blurredEl).toHaveCount(0)

    // Should NOT show lock overlay (paywall)
    await expect(page.locator('text=Sign in to read more').or(page.locator('text=登入以閱讀更多文章'))).not.toBeVisible()
  })

  test('guest mode: pagination controls are not visible on home page', async ({ page }) => {
    await page.goto('/login')
    await page.getByRole('button', { name: /continue as guest|以訪客身份繼續/i }).click()
    await page.waitForURL('/')

    // Pagination buttons should not be rendered for guests
    await expect(page.getByRole('button', { name: /previous|上一頁/i })).not.toBeVisible()
    await expect(page.getByRole('button', { name: /next|下一頁/i })).not.toBeVisible()
  })

  test('guest mode persists after page refresh', async ({ page }) => {
    await page.goto('/login')
    await page.getByRole('button', { name: /continue as guest|以訪客身份繼續/i }).click()
    await page.waitForURL('/')

    // Set sessionStorage as the button does
    await page.evaluate(() => sessionStorage.setItem('guest_mode', 'true'))
    await page.reload()

    // Still no blur (still in guest mode, not paywall)
    await expect(page.locator('.blur-\\[2px\\]')).toHaveCount(0)
  })

  test('guest visiting /settings via URL sees "Account required" prompt', async ({ page }) => {
    // Enter guest mode
    await page.goto('/login')
    await page.getByRole('button', { name: /continue as guest|以訪客身份繼續/i }).click()
    await page.waitForURL('/')
    await page.evaluate(() => sessionStorage.setItem('guest_mode', 'true'))

    await page.goto('/settings')

    await expect(
      page.getByRole('heading', { name: /account required|需要帳號/i })
    ).toBeVisible()

    // Login and Register links should be present
    await expect(page.getByRole('link', { name: /sign in|登入/i })).toBeVisible()
    await expect(page.getByRole('link', { name: /register|註冊/i })).toBeVisible()
  })

  test('non-guest unauthenticated user still sees paywall on home page', async ({ page }) => {
    // Go directly to home WITHOUT entering guest mode
    await page.goto('/')

    // Should show blurred placeholder articles
    const blurredEl = page.locator('.blur-\\[2px\\]')
    await expect(blurredEl.first()).toBeVisible()
  })

  test('guest visiting /graph sees limited preview banner', async ({ page }) => {
    await page.route('**/analyses/graph**', async route => {
      await route.fulfill({ json: graphFixture })
    })

    await page.goto('/login')
    await page.getByRole('button', { name: /continue as guest|以訪客身份繼續/i }).click()
    await page.waitForURL('/')
    await page.evaluate(() => sessionStorage.setItem('guest_mode', 'true'))

    await page.goto('/graph')

    await expect(
      page.getByText(/limited preview|有限預覽/i)
    ).toBeVisible()

    // No paywall blur overlay
    const lockOverlay = page.locator('[class*="backdrop-blur"]')
    await expect(lockOverlay).toHaveCount(0)
  })
})
