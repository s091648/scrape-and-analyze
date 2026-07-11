import { test, expect } from '@playwright/test'
import { mockApiRoutes, dismissFeatureSpotlights } from './fixtures/api-handlers'

async function mockWeeklyReportsEmpty(page: import('@playwright/test').Page) {
  await page.route((url: URL) => url.pathname === '/api/proxy/weekly-reports/latest', route =>
    route.fulfill({ json: null })
  )
  await page.route((url: URL) => url.pathname === '/api/proxy/weekly-reports', route =>
    route.fulfill({ json: { items: [], total: 0, page: 1, size: 10 } })
  )
}

// A minimal OpenAI-style SSE response: one content delta carrying a citation
// marker, a custom `sources` event (consumed by the wrapper's adapter, not
// rendered by the base openaiAdapter), then [DONE].
function sseBody(answer: string, sources: Array<{ id: string; title: string; url: string; public_article_id: string | null }>) {
  const lines = [
    `data: ${JSON.stringify({ choices: [{ delta: { content: answer } }] })}`,
    '',
    `data: ${JSON.stringify({ sources })}`,
    '',
    'data: [DONE]',
    '',
  ]
  return lines.join('\n')
}

async function mockChatCompletion(
  page: import('@playwright/test').Page,
  answer: string,
  sources: Array<{ id: string; title: string; url: string; public_article_id: string | null }> = [],
) {
  await page.route((url: URL) => url.pathname === '/api/proxy/chat/completions', route =>
    route.fulfill({
      status: 200,
      contentType: 'text/event-stream',
      body: sseBody(answer, sources),
    })
  )
}

test.describe('RAG chatbot — FloatingChatbot FAB visibility', () => {
  test.describe('as authenticated member', () => {
    test.beforeEach(async ({ page }) => {
      await dismissFeatureSpotlights(page)
      await mockApiRoutes(page)
    })

    test('FAB is visible on /articles', async ({ page }) => {
      await page.goto('/articles')
      await expect(page.getByRole('button', { name: /open chat/i })).toBeVisible()
    })

    test('FAB is not rendered on the homepage', async ({ page }) => {
      await mockWeeklyReportsEmpty(page)
      await page.goto('/')
      await expect(page.getByRole('button', { name: /open chat|close chat/i })).not.toBeVisible()
    })

    test('clicking the FAB opens the panel, and clicking again closes it', async ({ page }) => {
      await page.goto('/articles')
      const fab = page.getByRole('button', { name: /open chat/i })
      await fab.click()
      await expect(page.getByRole('button', { name: /close chat/i })).toBeVisible()
      await expect(page.getByRole('log')).toBeVisible()

      await page.getByRole('button', { name: /close chat/i }).click()
      await expect(page.getByRole('button', { name: /open chat/i })).toBeVisible()
    })
  })

  test.describe('as guest', () => {
    test.use({ storageState: { cookies: [], origins: [] } })

    test.beforeEach(async ({ page }) => {
      await mockApiRoutes(page)
    })

    test('FAB is visible for guest-mode users', async ({ page }) => {
      await page.goto('/login')
      await page.getByRole('button', { name: /continue as guest|以訪客身份繼續/i }).click()
      await page.waitForURL('/')
      await page.evaluate(() => sessionStorage.setItem('guest_mode', 'true'))

      await page.goto('/articles')
      // Guest onboarding tour auto-opens on every fresh load while in guest mode.
      const skipBtn = page.getByRole('button', { name: /^skip$|^略過$/i })
      if (await skipBtn.count() > 0) await skipBtn.click()

      await expect(page.getByRole('button', { name: /open chat/i })).toBeVisible()
    })
  })

  test.describe('as pure unauthenticated (paywall)', () => {
    test.use({ storageState: { cookies: [], origins: [] } })

    test.beforeEach(async ({ page }) => {
      await mockApiRoutes(page)
    })

    test('FAB is hidden for non-guest unauthenticated users', async ({ page }) => {
      await page.goto('/articles')
      await expect(page.getByRole('button', { name: /open chat|close chat/i })).not.toBeVisible()
    })
  })
})

test.describe('RAG chatbot — InlineQABar on the homepage', () => {
  test.beforeEach(async ({ page }) => {
    await dismissFeatureSpotlights(page)
    await mockApiRoutes(page)
    await mockWeeklyReportsEmpty(page)
  })

  test('submitting a question renders the answer with a cited source', async ({ page }) => {
    await mockChatCompletion(page, 'Digital twins reduce downtime by 30% [1].', [
      { id: 'src-1', title: 'Digital Twin Innovation', url: 'https://example.com/digital-twins', public_article_id: 'art-001' },
    ])

    await page.goto('/')
    const input = page.getByLabel('Agent input')
    await input.fill('What are digital twins?')
    await page.getByRole('button', { name: 'Send' }).click()

    await expect(page.getByText(/digital twins reduce downtime by 30%/i)).toBeVisible()
    await expect(page.getByText('Digital Twin Innovation')).toBeVisible()
  })

  test('empty question does not trigger a request', async ({ page }) => {
    let requestFired = false
    await page.route((url: URL) => url.pathname === '/api/proxy/chat/completions', route => {
      requestFired = true
      route.fulfill({ status: 200, contentType: 'text/event-stream', body: sseBody('should not happen', []) })
    })

    await page.goto('/')
    const sendBtn = page.getByRole('button', { name: 'Send' })
    await expect(sendBtn).toBeDisabled()
    await sendBtn.click({ force: true })
    expect(requestFired).toBe(false)
  })

  test('shows an error message when the chat backend is unavailable', async ({ page }) => {
    await page.route((url: URL) => url.pathname === '/api/proxy/chat/completions', route =>
      route.fulfill({ status: 503, json: { detail: 'unavailable' } })
    )

    await page.goto('/')
    await page.getByLabel('Agent input').fill('Anything?')
    await page.getByRole('button', { name: 'Send' }).click()

    await expect(page.getByText(/temporarily unavailable/i)).toBeVisible()
  })
})
