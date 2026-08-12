import { test, expect } from '@playwright/test'

// Covers 021-ssr-public-pages (SSR conversion of /, /articles, /graph, /tags).
//
// A note on what these tests can and can't verify: unlike the rest of this suite, the pages
// under test here perform their first-paint data fetch on the SERVER (inside the Next.js
// process, straight to BACKEND_URL) rather than in the browser — so `page.route()` (which only
// intercepts BROWSER-originated requests) cannot mock or observe that fetch. Whether an
// authenticated visitor's SSR fetch actually returns real backend data in any given test
// environment additionally depends on this run's session JWT validating against whatever
// NEXTAUTH_SECRET the real backend container was started with (see
// tests/integration/global-setup.ts) — something this suite doesn't control. Because of that,
// the tests below assert only what's true regardless of that alignment: that SSR never leaks
// content to a visitor with no session (fully deterministic — no backend call is even attempted,
// per lib/server/ssr-fetch.ts's resolveSsrContext()), and that every converted route still loads
// successfully either way (no crash, per FR-007). The specific guarantee that an authenticated,
// successfully-seeded render skips its client-side mount fetch (FR-003/SC-004) is covered instead
// at the component level in tests/unit/articles-page-content-ssr-seed.test.tsx, where it can be
// asserted deterministically without a real backend in the loop.

test.describe('SSR conversion — anonymous visitor (no session)', () => {
  test.use({ storageState: { cookies: [], origins: [] }, javaScriptEnabled: false })

  for (const path of ['/', '/articles', '/graph', '/tags']) {
    test(`${path} loads successfully and never embeds real content pre-hydration`, async ({ page }) => {
      const response = await page.goto(path)
      expect(response?.status()).toBeLessThan(400)

      // With JS disabled, this is exactly (and only) what the server sent — proving no real
      // backend content was fetched/embedded on this anonymous visitor's behalf (FR-002).
      const html = await page.content()
      expect(html).not.toContain('ArticleCard')
      expect(html.toLowerCase()).not.toContain('pain_points')
    })
  }
})

test.describe('SSR conversion — every converted route survives with a real (possibly expired/invalid) session cookie', () => {
  // Deliberately reuses the shared authenticated storageState (playwright.config.ts default) —
  // see the file header: whether this session validates against the real backend's secret is
  // environment-dependent, so this test only asserts the structural guarantee (FR-007: no crash
  // either way), not that specific content was fetched.
  for (const path of ['/', '/articles', '/graph', '/tags']) {
    test(`${path} renders without a server error`, async ({ page }) => {
      const response = await page.goto(path)
      expect(response?.status()).toBeLessThan(500)
      // Next.js's default error overlay/digest text would appear here on an unhandled
      // server-side exception — confirms fetchXSSR's try/catch (FR-007) actually holds even
      // when resolveSsrContext()'s downstream calls behave unexpectedly.
      await expect(page.getByText(/application error/i)).toHaveCount(0)
    })
  }
})
