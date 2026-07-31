import { test, expect } from '@playwright/test'
import { mockApiRoutes, dismissFeatureSpotlights } from './fixtures/api-handlers'

// Exercises the generic error-handling path in frontend/lib/api/client.ts (apiFetch),
// which every API call in the app goes through — chat.spec.ts already covers the
// chatbot's own error UI, this file covers the shared path for everything else.
// Response bodies are shaped like the backend's real central exception handler
// (backend/schemas/error.py::ErrorResponse: { error: { code, message, request_id } }),
// see site/guide/architecture/exception-handling.md.

test.describe('Generic apiFetch error handling', () => {
  test.beforeEach(async ({ page }) => {
    await dismissFeatureSpotlights(page)
    await mockApiRoutes(page)
  })

  test('a 500 response on a non-chat page surfaces the backend message as a toast', async ({ page }) => {
    await page.route((url: URL) => url.pathname === '/api/proxy/articles', route =>
      route.fulfill({
        status: 500,
        json: { error: { code: 'internal_error', message: 'Something went wrong loading articles', request_id: 'req-500-1' } },
      })
    )

    // domcontentloaded (not the default 'load') so the assertion starts polling
    // immediately — the error toast fires client-side after hydration and
    // auto-dismisses after sonner's 4s default; waiting for the full 'load'
    // event (all network resources) can eat into that window under parallel
    // test-worker contention and make the toast vanish before we ever look.
    await page.goto('/articles', { waitUntil: 'domcontentloaded' })

    await expect(page.getByText('Something went wrong loading articles')).toBeVisible()
  })

  test('a non-silent 4xx response also toasts the backend message', async ({ page }) => {
    await page.route((url: URL) => url.pathname === '/api/proxy/articles', route =>
      route.fulfill({
        status: 422,
        json: { error: { code: 'validation_error', message: 'Invalid filter combination', request_id: 'req-422-1' } },
      })
    )

    await page.goto('/articles', { waitUntil: 'domcontentloaded' })

    await expect(page.getByText('Invalid filter combination')).toBeVisible()
  })

  test('a response with no parseable JSON body falls back to a generic "Request failed" toast', async ({ page }) => {
    await page.route((url: URL) => url.pathname === '/api/proxy/articles', route =>
      route.fulfill({ status: 503, body: 'upstream is on fire', contentType: 'text/plain' })
    )

    await page.goto('/articles', { waitUntil: 'domcontentloaded' })

    await expect(page.getByText('Request failed (503)')).toBeVisible()
  })

  test('401 with an active session signs the user out and redirects to /login', async ({ page }) => {
    await page.route((url: URL) => url.pathname === '/api/proxy/articles', route =>
      route.fulfill({
        status: 401,
        json: { error: { code: 'unauthorized', message: 'token expired', request_id: 'req-401-1' } },
      })
    )

    await page.goto('/articles')

    await page.waitForURL('/login')
  })
})
