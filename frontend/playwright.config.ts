import { defineConfig, devices } from '@playwright/test'

// Use GitHub Actions secret when available; fall back to fixed local test secret.
// Must match the value used in tests/integration/global-setup.ts.
const NEXTAUTH_SECRET =
  process.env.NEXTAUTH_SECRET || 'e2e-nextauth-secret-local-testing-only'

// Allows pointing tests at an already-running dev server (e.g. the `frontend`
// docker-compose service) during local iteration, without changing CI's
// build+start behavior when unset.
const baseURL = process.env.PLAYWRIGHT_TEST_BASE_URL || 'http://localhost:3000'

export default defineConfig({
  testDir: './tests/integration',
  timeout: 30_000,
  retries: process.env.CI ? 2 : 0,
  // CI's frontend-e2e job (.github/workflows/ci.yml) runs `npx playwright test`
  // with no --workers override on a 2-vCPU GitHub Actions runner, which resolves
  // to Playwright's default of ~half the cores, i.e. 1. Pinning it here keeps
  // local/docker runs (which otherwise see far more cores and pick a much
  // higher default) on the same worker count as CI, avoiding failures caused
  // by request contention against the single Next.js server under webServer.
  workers: 1,
  globalSetup: './tests/integration/global-setup.ts',
  webServer: process.env.PLAYWRIGHT_TEST_BASE_URL ? undefined : {
    command: 'npm run build && npm run start',
    url: baseURL,
    reuseExistingServer: !process.env.CI,
    timeout: 120_000,
    env: {
      NEXTAUTH_SECRET,
      NEXTAUTH_URL: 'http://localhost:3000',
      BACKEND_URL: 'http://localhost:8000',
    },
  },
  use: {
    baseURL,
    storageState: 'tests/integration/fixtures/auth-state.json',
    screenshot: 'only-on-failure',
    video: 'retain-on-failure',
  },
  reporter: [
    ['html', { open: 'never' }],
    ['junit', { outputFile: 'playwright-results.xml' }],
  ],
  projects: [
    { name: 'chromium', use: { ...devices['Desktop Chrome'] } },
  ],
})
