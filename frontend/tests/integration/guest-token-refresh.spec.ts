import { test, expect } from '@playwright/test'
import { mockApiRoutes } from './fixtures/api-handlers'

// Exercises AuthTokenProvider's guest-token lifecycle (frontend/lib/providers/auth-token-provider.tsx,
// spec 018-public-api-auth). The provider wraps every route and bootstraps a token for ANY
// unauthenticated visitor automatically — no need to click through "Continue as Guest" first,
// that button only toggles paywall/tutorial UI, it's unrelated to auth token issuance.
test.use({ storageState: { cookies: [], origins: [] } })

test.describe('Guest token refresh', () => {
  test.beforeEach(async ({ page }) => {
    await mockApiRoutes(page)
  })

  test('an expired cached pair is refreshed via /auth/guest/refresh instead of re-issued from scratch', async ({ page }) => {
    await page.addInitScript(() => {
      sessionStorage.setItem(
        'guest_token_pair',
        JSON.stringify({
          accessToken: 'stale-access-token',
          refreshToken: 'valid-refresh-token',
          expiresAt: Date.now() - 5_000,
        })
      )
    })

    let issueCalled = false
    let refreshCalled = false

    await page.route((url: URL) => url.pathname === '/api/proxy/auth/guest', route => {
      issueCalled = true
      return route.fulfill({ json: { access_token: 'should-not-be-used', refresh_token: 'should-not-be-used', expires_in: 3600 } })
    })
    await page.route((url: URL) => url.pathname === '/api/proxy/auth/guest/refresh', route => {
      refreshCalled = true
      return route.fulfill({ json: { access_token: 'refreshed-access-token', refresh_token: 'valid-refresh-token', expires_in: 3600 } })
    })

    const refreshedArticlesRequest = page.waitForRequest(
      req => req.url().includes('/api/proxy/articles') && req.headers()['authorization'] === 'Bearer refreshed-access-token'
    )

    await page.goto('/articles')
    await refreshedArticlesRequest

    expect(refreshCalled).toBe(true)
    expect(issueCalled).toBe(false)
  })

  test('falls back to issuing a brand-new pair when the refresh call fails', async ({ page }) => {
    await page.addInitScript(() => {
      sessionStorage.setItem(
        'guest_token_pair',
        JSON.stringify({
          accessToken: 'stale-access-token',
          refreshToken: 'dead-refresh-token',
          expiresAt: Date.now() - 5_000,
        })
      )
    })

    await page.route((url: URL) => url.pathname === '/api/proxy/auth/guest/refresh', route =>
      route.fulfill({
        status: 401,
        json: { error: { code: 'unauthorized', message: 'refresh token expired or revoked', request_id: 'req-refresh-1' } },
      })
    )
    await page.route((url: URL) => url.pathname === '/api/proxy/auth/guest', route =>
      route.fulfill({ json: { access_token: 'freshly-issued-token', refresh_token: 'freshly-issued-refresh', expires_in: 3600 } })
    )

    const freshArticlesRequest = page.waitForRequest(
      req => req.url().includes('/api/proxy/articles') && req.headers()['authorization'] === 'Bearer freshly-issued-token'
    )

    await page.goto('/articles')
    await freshArticlesRequest
  })
})
