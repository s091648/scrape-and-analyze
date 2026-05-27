import { test, expect } from '@playwright/test'
import { mockApiRoutes } from './fixtures/api-handlers'

test.describe('Article detail dialog', () => {
  test.beforeEach(async ({ page }) => {
    await mockApiRoutes(page)
  })

  test('clicking article card opens detail dialog', async ({ page }) => {
    await page.goto('/')
    // Wait for topic URL sync to complete so the article list is stable before clicking
    await page.waitForURL(/topic=/)
    await expect(page.getByText('Digital Twin Innovation')).toBeVisible()
    await page.getByText('Digital Twin Innovation').click()
    await expect(page.getByRole('dialog')).toBeVisible()
  })

  test('dialog displays pain_points and insights from analysis', async ({ page }) => {
    await page.goto('/')
    await page.getByText('Digital Twin Innovation').click()
    await expect(page.getByText('Integration complexity is high.')).toBeVisible()
    await expect(page.getByText('Digital twins reduce downtime by 30%.')).toBeVisible()
  })

  test('pressing Escape closes dialog', async ({ page }) => {
    await page.goto('/')
    await page.getByText('Digital Twin Innovation').click()
    await expect(page.getByRole('dialog')).toBeVisible()
    await page.keyboard.press('Escape')
    await expect(page.getByRole('dialog')).not.toBeVisible()
  })
})
