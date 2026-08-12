import { test, expect } from '@playwright/test'
import { mockApiRoutes, dismissFeatureSpotlights, articleDetailFixture } from './fixtures/api-handlers'

const unfavoritedArticle = {
  id: 'art-fav-1', title: 'Plain Paper', source: 'rss',
  content: 'x', published_at: null, scraped_at: null, url: 'https://x.com/1',
  is_favorited: false,
}

const favoritedArticle = {
  id: 'art-fav-2', title: 'Favorited Paper', source: 'rss',
  content: 'x', published_at: null, scraped_at: null, url: 'https://x.com/2',
  is_favorited: true,
}

async function mockArticleList(page: import('@playwright/test').Page, items: Record<string, unknown>[]) {
  await page.route(
    (url: URL) => url.pathname.startsWith('/api/proxy/articles') && !url.pathname.includes('/articles/'),
    route => route.fulfill({ json: { items, total: items.length, page: 1, size: 20 } })
  )
}

test.describe('Favorites — authenticated member', () => {
  test.beforeEach(async ({ page }) => {
    await dismissFeatureSpotlights(page)
    await mockApiRoutes(page)
  })

  test('clicking the heart icon favorites an unfavorited article', async ({ page }) => {
    await mockArticleList(page, [unfavoritedArticle])
    const favPromise = page.waitForRequest(req =>
      req.url().includes('/api/proxy/user/favorites/art-fav-1') && req.method() === 'POST'
    )

    await page.goto('/articles')
    await expect(page.getByText('Plain Paper')).toBeVisible()
    await page.getByRole('button', { name: 'Add to favorites' }).click({ force: true })
    await favPromise
    await expect(page.getByRole('button', { name: 'Remove from favorites' })).toBeVisible()
  })

  test('clicking a filled heart icon unfavorites the article', async ({ page }) => {
    await mockArticleList(page, [favoritedArticle])
    const removePromise = page.waitForRequest(req =>
      req.url().includes('/api/proxy/user/favorites/art-fav-2') && req.method() === 'DELETE'
    )

    await page.goto('/articles')
    // Wait for the article itself first — the favorite button only renders once useSession()
    // resolves to 'authenticated', so asserting on it immediately races session hydration.
    await expect(page.getByText('Favorited Paper')).toBeVisible()
    await expect(page.getByRole('button', { name: 'Remove from favorites' })).toBeVisible()
    await page.getByRole('button', { name: 'Remove from favorites' }).click({ force: true })
    await removePromise
    await expect(page.getByRole('button', { name: 'Add to favorites' })).toBeVisible()
  })

  test('enabling the Favorites filter shows only favorited articles', async ({ page }) => {
    await mockArticleList(page, [unfavoritedArticle, favoritedArticle])
    await page.goto('/articles')
    await expect(page.getByText('Plain Paper')).toBeVisible()
    await expect(page.getByText('Favorited Paper')).toBeVisible()

    await page.getByRole('button', { name: /filters/i }).click()
    await page.getByRole('button', { name: /favorites only/i }).click()

    await expect(page.getByText('Favorited Paper')).toBeVisible()
    await expect(page.getByText('Plain Paper')).not.toBeVisible()
    await expect(page).toHaveURL(/favorites_only=true/)
  })
})

test.describe('Favorites — guest mode (not authenticated)', () => {
  test.use({ storageState: { cookies: [], origins: [] } })

  test.beforeEach(async ({ page }) => {
    await mockApiRoutes(page)
    await mockArticleList(page, [unfavoritedArticle])
    // Guest mode on /articles can auto-open two different tour dialogs that are unrelated to
    // this test — the guest onboarding tour (see guest-tutorial.spec.ts) and, once that's
    // suppressed, the still-unseen "New: AI Chat Assistant" feature-spotlight tour (also
    // targets /articles) right behind it. Either one sits on top of the Filters button and
    // blocks the click for the full 30s timeout. Suppress both outright, same as the other
    // describes in this file already do via dismissFeatureSpotlights.
    await dismissFeatureSpotlights(page)
    await page.addInitScript(() => {
      sessionStorage.setItem('tutorial_onboarding_dismissed', 'true')
    })
  })

  test('no heart icon and no Favorites filter are shown to guests', async ({ page }) => {
    await page.goto('/login')
    await page.getByRole('button', { name: /continue as guest|以訪客身份繼續/i }).click()
    await page.waitForURL('/')
    await page.evaluate(() => sessionStorage.setItem('guest_mode', 'true'))

    await page.goto('/articles')

    await expect(page.getByText('Plain Paper')).toBeVisible()
    await expect(page.getByRole('button', { name: /add to favorites|remove from favorites/i })).not.toBeVisible()

    await page.getByRole('button', { name: /filters/i }).click()
    await expect(page.getByRole('button', { name: /favorites only/i })).not.toBeVisible()
  })
})

test.describe('Article detail dialog — citation and view counts', () => {
  test.beforeEach(async ({ page }) => {
    await dismissFeatureSpotlights(page)
    await mockApiRoutes(page)
  })

  test('shows citation and view counts once the detail loads', async ({ page }) => {
    await page.route((url: URL) => /\/api\/proxy\/articles\/[^/]+$/.test(url.pathname), route =>
      route.fulfill({ json: { ...articleDetailFixture, metrics: { citation_count: 42 }, view_count: 137 } })
    )

    await page.goto('/articles')
    await page.waitForURL(/topic=/)
    await page.getByText('Digital Twin Innovation').click()
    await expect(page.getByRole('dialog')).toBeVisible()
    await expect(page.getByText('42 Citations')).toBeVisible()
    await expect(page.getByText('137 views')).toBeVisible()
  })
})
