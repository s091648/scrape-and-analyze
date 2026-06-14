import { test, expect } from '@playwright/test'
import { mockApiRoutes, articleDetailFixture } from './fixtures/api-handlers'

test.describe('Article Sharing — URL sync', () => {
  test.beforeEach(async ({ page }) => {
    await mockApiRoutes(page)
  })

  test('opening article card adds ?article= to URL', async ({ page }) => {
    await page.goto('/articles')
    await page.waitForURL(/topic=/)
    await page.getByText('Digital Twin Innovation').click()
    await expect(page).toHaveURL(/article=art-001/)
  })

  test('closing article dialog removes ?article from URL', async ({ page }) => {
    await page.goto('/articles')
    await page.waitForURL(/topic=/)
    await page.getByText('Digital Twin Innovation').click()
    await expect(page.getByRole('dialog')).toBeVisible()
    await page.keyboard.press('Escape')
    await expect(page.getByRole('dialog')).not.toBeVisible()
    await expect(page).not.toHaveURL(/article=/)
  })

  test('direct URL with ?article= auto-opens the matching dialog', async ({ page }) => {
    await page.goto('/articles?topic=topic-001&article=art-001')
    await expect(page.getByRole('dialog')).toBeVisible()
  })

  test('URL preserves existing topic param when article opens', async ({ page }) => {
    await page.goto('/articles')
    await page.waitForURL(/topic=/)
    await page.getByText('Digital Twin Innovation').click()
    await expect(page).toHaveURL(/topic=/)
    await expect(page).toHaveURL(/article=art-001/)
  })
})

test.describe('Article Sharing — share icon clipboard', () => {
  test.beforeEach(async ({ page }) => {
    await page.addInitScript(() => {
      const captured: string[] = []
      Object.defineProperty(navigator, 'clipboard', {
        value: {
          writeText: (text: string) => {
            captured.push(text)
            ;(window as any).__clipboardCapture = captured
            return Promise.resolve()
          },
          readText: () => Promise.resolve(captured[captured.length - 1] ?? ''),
        },
        configurable: true,
      })
    })
    await mockApiRoutes(page)
  })

  test('clicking share icon writes a /articles/{id} URL to clipboard', async ({ page }) => {
    await page.goto('/articles')
    await page.waitForURL(/topic=/)
    await page.getByRole('button', { name: 'Share article' }).first().click({ force: true })
    const clipboardText = await page.evaluate(() =>
      (window as any).__clipboardCapture?.[(window as any).__clipboardCapture.length - 1] ?? ''
    )
    expect(clipboardText).toMatch(/\/articles\/art-001/)
  })
})

test.describe('Article Sharing — standalone page', () => {
  test.beforeEach(async ({ page }) => {
    await mockApiRoutes(page)
  })

  test('standalone /articles/[id] page renders the article', async ({ page }) => {
    await page.goto('/articles/art-001')
    await expect(page.getByText('Digital Twin Innovation')).toBeVisible()
  })

  test('standalone page has no FilterBar', async ({ page }) => {
    await page.goto('/articles/art-001')
    await expect(page.getByRole('button', { name: /filters/i })).not.toBeVisible()
  })

  test('standalone page shows a link back to home', async ({ page }) => {
    await page.goto('/articles/art-001')
    await expect(page.getByText('Scrape Analyzer')).toBeVisible()
  })

  test('standalone page shows Open in App link for authenticated user', async ({ page }) => {
    await page.goto('/articles/art-001')
    await expect(page.getByText(/open in app/i)).toBeVisible()
  })

  test('invalid article ID shows 404 message', async ({ page }) => {
    await page.route(
      (url: URL) => /\/api\/proxy\/articles\/invalid-id$/.test(url.pathname),
      route => route.fulfill({ status: 404, json: { detail: 'not found' } })
    )
    await page.goto('/articles/invalid-id')
    await expect(page.getByTestId('article-not-found')).toBeVisible()
  })
})
