import { Page } from '@playwright/test'

// Note: Playwright page.route() uses LIFO ordering — routes registered LATER take higher priority.
// Specific routes (filters, detail) are registered AFTER generic routes to override them.
// Function matchers are used instead of glob strings to reliably intercept URLs with query params.

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

export const topicsFixture = [
  {
    id: 'topic-001',
    name: 'digital_twin',
    display_name: 'Digital Twin',
    color_hex: '#6366f1',
    sort_order: 1,
  },
]

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
  // Function matchers are used to reliably match URLs with query strings (glob ** may not match ?).

  const proxy = (path: string) => (url: URL) =>
    url.pathname === `/api/proxy/${path}` || url.pathname.startsWith(`/api/proxy/${path}/`)
  const proxyPrefix = (prefix: string) => (url: URL) =>
    url.pathname.startsWith(`/api/proxy/${prefix}`)

  // Catch-all: any unmocked /api/proxy/** route returns 404 instead of hitting the real backend
  await page.route((url: URL) => url.pathname.startsWith('/api/proxy/'), route =>
    route.fulfill({ status: 404, json: { detail: 'not found (test mock catch-all)' } })
  )

  // Generic routes (registered before specifics — lower priority in LIFO)
  await page.route(proxyPrefix('analyses/graph'), route => route.fulfill({ json: graphFixture }))

  await page.route(proxy('scraper-settings'), async route => {
    if (route.request().method() === 'POST') {
      await route.fulfill({ status: 201, json: newSettingFixture })
    } else {
      await route.fulfill({ json: scraperListFixture })
    }
  })

  await page.route((url: URL) => /\/api\/proxy\/scraper-settings\/[^/]+$/.test(url.pathname), async route => {
    if (route.request().method() === 'PATCH') {
      await route.fulfill({ json: updatedSettingFixture })
    } else {
      await route.fallback()
    }
  })

  // scraper keyword sub-resources (needed by scraper-settings page)
  await page.route(proxyPrefix('scraper-keywords'), route => route.fulfill({ json: [] }))

  await page.route(proxyPrefix('articles'), route => route.fulfill({ json: articleListFixture }))

  // Specific routes registered last (higher priority in LIFO — override generic patterns above)
  await page.route(proxy('source-categories'), route =>
    route.fulfill({ json: { aggregator: [{ value: 'semantic_scholar', label: 'Semantic Scholar' }, { value: 'openalex', label: 'OpenAlex' }], scraper: [{ value: 'rss', label: 'RSS' }, { value: 'blog', label: 'Blog' }, { value: 'arxiv', label: 'arXiv' }] } })
  )
  await page.route(proxy('articles/filters/sources'), route =>
    route.fulfill({ json: ['rss', 'blog'] })
  )
  await page.route(proxy('articles/filters/original-sources'), route =>
    route.fulfill({ json: ['rss', 'blog'] })
  )
  await page.route(proxy('articles/filters/tags'), route =>
    route.fulfill({ json: ['AI', 'IoT', 'Digital Twin'] })
  )
  await page.route((url: URL) => /\/api\/proxy\/articles\/[^/]+$/.test(url.pathname), route =>
    route.fulfill({ json: articleDetailFixture })
  )

  // Tag groups — needed by FilterBar (must come before catch-all)
  await page.route(proxyPrefix('tag-groups'), route => route.fulfill({ json: [] }))

  // Chat quota — needed by ChatQuotaProvider and FloatingChatbotWrapper on /articles
  await page.route(proxy('chat/quota'), route =>
    route.fulfill({ json: { tier: 'guest', remaining: 5, limit: 10, guest_daily_limit: 10, member_daily_limit: 30 } })
  )

  // Topics — needed by TopicContext on every page load (must be last = highest priority)
  await page.route(proxy('topics'), route => route.fulfill({ json: topicsFixture }))
}

// Every registered Feature Spotlight tour (components/features/tutorial/tutorial-registry.ts)
// auto-opens for any authenticated or guest session visiting its target route that hasn't
// seen it yet (see tutorial-provider.tsx). Specs that aren't testing the tutorial itself need
// to mark them all as already seen, otherwise a spotlight dialog covers the page and
// intercepts clicks intended for the content underneath.
// NB: keep this list in sync with the `kind: 'spotlight'` tour ids in tutorial-registry.ts.
const SPOTLIGHT_TOUR_IDS = [
  'feature-chat-2026-07',
  'feature-weekly-report-2026-07',
  'feature-articles-stats-2026-07',
]

export async function dismissFeatureSpotlights(page: Page) {
  await page.addInitScript((ids) => {
    localStorage.setItem('tutorial_seen_tours', JSON.stringify(ids))
  }, SPOTLIGHT_TOUR_IDS)
}
