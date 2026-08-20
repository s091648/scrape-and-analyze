import { test, expect } from '@playwright/test'
import { dismissFeatureSpotlights } from './fixtures/api-handlers'

const article = {
  id: 'art-1',
  title: 'Machine Learning Basics',
  source: 'arxiv',
  content: 'An article about machine learning.',
  published_at: '2026-01-10T00:00:00Z',
  scraped_at: '2026-01-11T00:00:00Z',
  url: 'https://arxiv.org/ml-basics',
  metrics: {},
  view_count: 0,
}

test.describe('Search autocomplete — debounce & staleness (023-article-search US3)', () => {
  let autocompleteCallCount = 0
  let autocompletePrefixesSeen: string[] = []

  test.beforeEach(async ({ page }) => {
    autocompleteCallCount = 0
    autocompletePrefixesSeen = []
    await dismissFeatureSpotlights(page)

    await page.route((url: URL) => url.pathname.startsWith('/api/proxy/'), route => {
      const req = route.request()
      const url = new URL(req.url())
      const p = url.pathname

      if (p === '/api/proxy/topics') {
        return route.fulfill({ json: [{ id: 'topic-001', name: 'ai', display_name: 'AI Research', color_hex: null, sort_order: 1 }] })
      }
      if (p === '/api/proxy/articles') {
        return route.fulfill({ json: { items: [article], total: 1, page: 1, size: 20 } })
      }
      if (p === '/api/proxy/search/autocomplete') {
        autocompleteCallCount++
        const prefix = url.searchParams.get('prefix') ?? ''
        autocompletePrefixesSeen.push(prefix)
        return route.fulfill({
          json: { suggestions: [{ term: `${prefix}suggestion`, occurrence_count: 5 }] },
        })
      }
      if (p.includes('filters')) return route.fulfill({ json: [] })
      if (p.includes('source-categories')) return route.fulfill({ json: { aggregator: [], scraper: [] } })
      if (p.includes('tag-groups')) return route.fulfill({ json: [] })
      if (p.includes('chat/quota')) return route.fulfill({ json: { tier: 'admin', remaining: -1, limit: -1 } })
      if (p.includes('weekly-reports')) return route.fulfill({ json: null })
      if (p === '/api/proxy/metric-definitions') return route.fulfill({ json: [] })
      route.fulfill({ status: 404, json: {} })
    })
  })

  test('typing quickly sends far fewer autocomplete requests than keystrokes', async ({ page }) => {
    await page.goto('/articles')
    const input = page.getByPlaceholder(/search/i)
    await input.click()
    await input.pressSequentially('learning', { delay: 30 }) // well under the 300ms debounce window per keystroke

    // Give the debounce window time to settle after the last keystroke.
    await page.waitForTimeout(500)

    expect(autocompleteCallCount).toBeLessThan('learning'.length)
  })

  test('only the final typed text\'s suggestions are ever shown, not an intermediate state', async ({ page }) => {
    await page.goto('/articles')
    const input = page.getByPlaceholder(/search/i)
    await input.click()
    await input.pressSequentially('lear', { delay: 30 })
    await page.waitForTimeout(500)

    await expect(page.getByText('learsuggestion')).toBeVisible()

    await input.pressSequentially('ning', { delay: 30 })
    await page.waitForTimeout(500)

    await expect(page.getByText('learningsuggestion')).toBeVisible()
    await expect(page.getByText('learsuggestion', { exact: true })).not.toBeVisible()
    expect(autocompletePrefixesSeen[autocompletePrefixesSeen.length - 1]).toBe('learning')
  })
})
