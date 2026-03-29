import { Page } from '@playwright/test'

// Note: Playwright page.route() uses LIFO ordering — routes registered LATER take higher priority.
// Specific routes (filters, detail) are registered AFTER generic routes to override them.

export const articleListFixture = {
  items: [
    {
      id: 'art-001',
      title: 'Digital Twin Innovation',
      source: 'rss',
      content: 'Digital twins are revolutionizing manufacturing.',
      published_at: '2026-01-15T10:00:00Z',
      scraped_at: '2026-01-16T00:00:00Z',
      url: 'https://example.com/digital-twins',
    },
  ],
  total: 1,
  page: 1,
  size: 20,
}

export const articleDetailFixture = {
  id: 'art-001',
  title: 'Digital Twin Innovation',
  source: 'rss',
  content: 'Digital twins are revolutionizing manufacturing.',
  published_at: '2026-01-15T10:00:00Z',
  scraped_at: '2026-01-16T00:00:00Z',
  url: 'https://example.com/digital-twins',
  tags: ['AI', 'IoT'],
  tag_groups: [
    { group_name: 'technology', display_name: 'Technology', color: '#6366f1', tags: ['AI', 'IoT'] }
  ],
  pain_points: 'Integration complexity is high.',
  insights: 'Digital twins reduce downtime by 30%.',
  innovations: null,
  model_used: 'claude-test',
}

export const graphFixture = {
  nodes: [
    { id: 'group:technology', type: 'group', label: 'Technology', groupName: 'technology', color: '#6366f1' },
    { id: 'art-001', type: 'article', label: 'Digital Twin Innovation', color: '#10b981' },
  ],
  edges: [
    { source: 'group:technology', target: 'art-001' },
  ],
}

export const scraperListFixture = [
  {
    id: 'sc-001',
    source_type: 'rss',
    name: 'TechCrunch RSS',
    url: 'https://techcrunch.com/feed/',
    frequency: 24,
    is_active: true,
    last_scraped_at: '2026-01-15T00:00:00Z',
    activity: [0, 1, 2, 3, 0, 1, 2, 3, 0, 1, 2, 3, 0, 1],
  },
]

export const newSettingFixture = {
  id: 'sc-002',
  source_type: 'rss',
  name: 'New RSS Source',
  url: 'https://new.com/feed',
  frequency: 24,
  is_active: true,
  last_scraped_at: null,
  activity: Array(14).fill(0),
}

export const updatedSettingFixture = {
  ...scraperListFixture[0],
  is_active: false,
}

export async function mockApiRoutes(page: Page) {
  // Note: Playwright page.route() uses LIFO ordering — routes registered LATER take higher priority.
  // Catch-all is registered FIRST (lowest priority) so specific routes below always win.

  // Catch-all: any unmocked /api/proxy/** route returns 404 instead of hitting the real backend
  await page.route('/api/proxy/**', route =>
    route.fulfill({ status: 404, json: { detail: 'not found (test mock catch-all)' } })
  )

  // Generic routes
  await page.route('/api/proxy/analyses/graph**', route => route.fulfill({ json: graphFixture }))
  await page.route('/api/proxy/scraper-settings', async route => {
    if (route.request().method() === 'POST') {
      await route.fulfill({ status: 201, json: newSettingFixture })
    } else {
      await route.fulfill({ json: scraperListFixture })
    }
  })
  await page.route('/api/proxy/scraper-settings/*', async route => {
    if (route.request().method() === 'PATCH') {
      await route.fulfill({ json: updatedSettingFixture })
    } else {
      await route.fallback()
    }
  })
  await page.route('/api/proxy/articles**', route => route.fulfill({ json: articleListFixture }))

  // Specific routes registered last (higher priority in LIFO — override generic patterns above)
  await page.route('/api/proxy/articles/filters/sources', route =>
    route.fulfill({ json: ['rss', 'blog'] })
  )
  await page.route('/api/proxy/articles/filters/tags', route =>
    route.fulfill({ json: ['AI', 'IoT', 'Digital Twin'] })
  )
  await page.route('/api/proxy/articles/*', route =>
    route.fulfill({ json: articleDetailFixture })
  )
}
