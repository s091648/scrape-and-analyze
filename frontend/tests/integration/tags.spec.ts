import { test, expect } from '@playwright/test'
import { mockApiRoutes, dismissFeatureSpotlights } from './fixtures/api-handlers'

const groupsFixture = [
  {
    id: 'group-1', name: 'machine_learning', display_name: 'Machine Learning',
    description: 'ML techniques', color_hex: '#6366f1', topic_id: 'topic-001',
    tags: [
      { id: 'tag-1', name: 'Transformer', article_count: 12 },
      { id: 'tag-2', name: 'Diffusion Model', article_count: 5 },
    ],
    similar_groups: [],
  },
  {
    id: 'group-2', name: 'applications', display_name: 'Applications',
    description: null, color_hex: '#10b981', topic_id: 'topic-001',
    tags: [
      { id: 'tag-3', name: 'Computer Vision', article_count: 8 },
    ],
    similar_groups: [],
  },
]

const suggestionsFixture = [
  {
    id: 'sugg-1', new_tag_id: 'tag-new', new_tag_name: 'ML',
    existing_tag_id: 'tag-1', existing_tag_name: 'Transformer',
    group_name: 'machine_learning', similarity_score: 0.93, article_id: null,
  },
]

async function mockTagGroups(page: import('@playwright/test').Page, groups: any[] = groupsFixture) {
  await page.route((url: URL) => url.pathname === '/api/proxy/tag-groups', route => {
    if (route.request().method() === 'POST') {
      return route.fulfill({
        status: 201,
        json: {
          id: 'group-new', name: 'new_group', display_name: 'New Group',
          description: null, color_hex: null, topic_id: 'topic-001', tags: [], similar_groups: [],
        },
      })
    }
    route.fulfill({ json: groups })
  })
}

async function mockSuggestions(page: import('@playwright/test').Page, suggestions: any[] = suggestionsFixture) {
  await page.route((url: URL) => url.pathname === '/api/proxy/tag-normalization-suggestions', route =>
    route.fulfill({ json: suggestions })
  )
}

test.describe('Tag management — admin', () => {
  test.beforeEach(async ({ page }) => {
    await dismissFeatureSpotlights(page)
    await mockApiRoutes(page)
    await mockTagGroups(page)
    await mockSuggestions(page, [])
  })

  test('renders tag group cards with their tags', async ({ page }) => {
    await page.goto('/tags')
    await expect(page.getByText('Machine Learning')).toBeVisible()
    await expect(page.getByText('Transformer')).toBeVisible()
    await expect(page.getByText('Applications')).toBeVisible()
    await expect(page.getByText('Computer Vision')).toBeVisible()
  })

  test('search filters groups and tags by query', async ({ page }) => {
    await page.goto('/tags')
    await expect(page.getByText('Machine Learning')).toBeVisible()
    await page.getByPlaceholder('Search groups or tags...').fill('vision')
    await expect(page.getByText('Applications')).toBeVisible()
    await expect(page.getByText('Machine Learning')).not.toBeVisible()
  })

  test('adding a group via the Add Group dialog appends it to the list', async ({ page }) => {
    await page.goto('/tags')
    await page.getByRole('button', { name: 'Add Group' }).click()

    // Fields aren't <label for>-associated, so target inputs positionally
    // within the dialog form: [name, display_name, color(hidden), color(text), description].
    const form = page.locator('form').filter({ hasText: 'Add Group' })
    await form.locator('input').nth(0).fill('new_group')
    await form.locator('input').nth(1).fill('New Group')

    const postPromise = page.waitForRequest(req =>
      req.url().includes('/api/proxy/tag-groups') && req.method() === 'POST'
    )
    await form.getByRole('button', { name: 'Create' }).click()
    await postPromise
    await expect(page.getByText('New Group')).toBeVisible()
  })

  test('renaming a tag via the tag dialog updates its label', async ({ page }) => {
    await page.route((url: URL) => url.pathname === '/api/proxy/articles', route =>
      route.fulfill({ json: { items: [], total: 0, page: 1, size: 10 } })
    )
    await page.route((url: URL) => url.pathname === '/api/proxy/tags/tag-1', route => {
      if (route.request().method() === 'PUT') {
        return route.fulfill({ json: { id: 'tag-1', name: 'Transformers', article_count: 12 } })
      }
      route.fallback()
    })

    await page.goto('/tags')
    await page.getByText('Transformer', { exact: false }).click()
    await expect(page.getByRole('dialog')).toBeVisible()
    await page.getByLabel('Rename tag').click()
    const input = page.getByRole('dialog').locator('input')
    await input.fill('Transformers')
    await page.keyboard.press('Enter')
    // Wait for the rename PUT to resolve (dialog title reverts from input to text)
    // before closing, otherwise Escape can race the in-flight request.
    await expect(page.getByRole('dialog').getByText('Transformers')).toBeVisible()

    await page.keyboard.press('Escape')
    await expect(page.getByRole('dialog')).not.toBeVisible()
    await expect(page.getByText('Transformers')).toBeVisible()
  })

  test('deleting a tag via the confirm step removes it from the group', async ({ page }) => {
    await page.route((url: URL) => url.pathname === '/api/proxy/articles', route =>
      route.fulfill({ json: { items: [], total: 0, page: 1, size: 10 } })
    )
    await page.route((url: URL) => url.pathname === '/api/proxy/tags/tag-3', route => {
      if (route.request().method() === 'DELETE') return route.fulfill({ status: 204 })
      route.fallback()
    })

    await page.goto('/tags')
    await page.getByText('Computer Vision', { exact: false }).click()
    await expect(page.getByRole('dialog')).toBeVisible()
    await page.getByLabel('Delete tag').click()
    await expect(page.getByText('Delete tag "Computer Vision"?')).toBeVisible()
    await page.getByRole('button', { name: 'Delete' }).click()

    await expect(page.getByRole('dialog')).not.toBeVisible()
    await expect(page.getByText('Computer Vision')).not.toBeVisible()
  })

  test('editing a group via the pencil icon updates its display name', async ({ page }) => {
    await page.route((url: URL) => url.pathname === '/api/proxy/tag-groups/group-2', route => {
      if (route.request().method() === 'PUT') {
        return route.fulfill({
          json: { id: 'group-2', name: 'applications', display_name: 'Use Cases', description: null, color_hex: '#10b981', topic_id: 'topic-001', tags: groupsFixture[1].tags, similar_groups: [] },
        })
      }
      route.fallback()
    })

    await page.goto('/tags')
    const applicationsCard = page.locator('.rounded-xl.border.border-border.bg-card').filter({ hasText: 'Applications' })
    await applicationsCard.getByLabel('Edit group').click()
    // Not <label for>-associated — inputs appear in order [name, display_name, color(hidden), color(text), description].
    const form = applicationsCard.locator('form')
    await form.locator('input').nth(1).fill('Use Cases')
    await form.getByRole('button', { name: 'Save' }).click()

    await expect(page.getByText('Use Cases')).toBeVisible()
  })

  test('deleting a group via the trash icon removes its card', async ({ page }) => {
    await page.route((url: URL) => url.pathname === '/api/proxy/tag-groups/group-2', route => {
      if (route.request().method() === 'DELETE') return route.fulfill({ status: 204 })
      route.fallback()
    })

    await page.goto('/tags')
    await expect(page.getByText('Applications')).toBeVisible()
    const applicationsCard = page.locator('.rounded-xl.border.border-border.bg-card').filter({ hasText: 'Applications' })
    await applicationsCard.getByLabel('Delete group').click()
    await expect(page.getByText('Applications')).not.toBeVisible()
  })

  test('merging two groups via the merge button flow replaces both with the result', async ({ page }) => {
    // Note: the page fires GET /tag-groups twice on initial mount (once before
    // `showSimilarities` flips true for admins, once after) — mock by actual
    // merge state, not call count, so both pre-merge fetches stay consistent.
    let merged = false
    const mergedGroup = {
      id: 'group-1', name: 'machine_learning', display_name: 'Machine Learning',
      description: 'ML techniques', color_hex: '#6366f1', topic_id: 'topic-001',
      tags: [...groupsFixture[0].tags, ...groupsFixture[1].tags], similar_groups: [],
    }
    await page.route((url: URL) => url.pathname === '/api/proxy/tag-groups', route =>
      route.fulfill({ json: merged ? [mergedGroup] : groupsFixture })
    )
    await page.route((url: URL) => url.pathname === '/api/proxy/tag-groups/merge', route => {
      merged = true
      return route.fulfill({ json: mergedGroup })
    })
    await page.route((url: URL) => url.pathname === '/api/proxy/tag-groups/group-1', route =>
      route.fulfill({ json: mergedGroup })
    )

    await page.goto('/tags')
    await page.getByLabel('Merge group').first().click()
    await expect(page.getByText(/click another group to merge with/i)).toBeVisible()
    await page.getByText('Merge here').click()

    await expect(page.getByText('Merge Tag Groups')).toBeVisible()
    await page.getByRole('button', { name: 'Merge Groups' }).click()

    await expect(page.getByText('Merge Tag Groups')).not.toBeVisible()
    await expect(page.getByText('Computer Vision')).toBeVisible() // merged tag now under group-1
    await expect(page.getByText('Applications', { exact: true })).not.toBeVisible() // group-2 card is gone
  })

  test('approving a pending suggestion removes it from the list', async ({ page }) => {
    await mockSuggestions(page, suggestionsFixture)
    await page.route((url: URL) => url.pathname === '/api/proxy/tag-normalization-suggestions/sugg-1/approve', route =>
      route.fulfill({ status: 204 })
    )

    await page.goto('/tags')
    const suggestionsPanel = page.locator('.border-amber-200')
    await expect(suggestionsPanel).toBeVisible()
    await expect(suggestionsPanel.getByText('machine_learning', { exact: false })).toBeVisible()

    await suggestionsPanel.getByRole('button', { name: 'Merge', exact: true }).click()
    await expect(page.getByText(/pending merge suggestions/i)).not.toBeVisible()
  })

  test('rejecting a pending suggestion removes it from the list', async ({ page }) => {
    await mockSuggestions(page, suggestionsFixture)
    await page.route((url: URL) => url.pathname === '/api/proxy/tag-normalization-suggestions/sugg-1/reject', route =>
      route.fulfill({ status: 204 })
    )

    await page.goto('/tags')
    const suggestionsPanel = page.locator('.border-amber-200')
    await expect(suggestionsPanel).toBeVisible()

    await suggestionsPanel.getByRole('button', { name: 'Keep both' }).click()
    await expect(page.getByText(/pending merge suggestions/i)).not.toBeVisible()
  })
})

test.describe('Tag management — guest paywall', () => {
  test.use({ storageState: { cookies: [], origins: [] } })

  test.beforeEach(async ({ page }) => {
    await mockApiRoutes(page)
  })

  test('shows blurred fake groups with a sign-in prompt, real group data is never displayed', async ({ page }) => {
    await page.route((url: URL) => url.pathname === '/api/proxy/tag-groups', route =>
      route.fulfill({ json: groupsFixture })
    )

    await page.goto('/tags')
    await expect(page.getByText('Research Methods')).toBeVisible()
    await expect(page.getByText('Sign in to explore Tags')).toBeVisible()
    await expect(page.getByRole('link', { name: 'Sign in', exact: true })).toHaveAttribute('href', '/login')
    // The paywall must never leak real group data, even if a stray request for it succeeds.
    // ("Applications" isn't checked here — it coincidentally collides with a name in the
    // hardcoded FAKE_GROUPS paywall placeholder data, which legitimately renders that text.)
    await expect(page.getByText('Machine Learning')).not.toBeVisible()
  })
})
