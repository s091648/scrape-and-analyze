import { defineConfig, devices } from '@playwright/test'

// Use GitHub Actions secret when available; fall back to fixed local test secret.
// Must match the value used in tests/integration/global-setup.ts.
const NEXTAUTH_SECRET =
  process.env.NEXTAUTH_SECRET || 'e2e-nextauth-secret-local-testing-only'

export default defineConfig({
  testDir: './tests/integration',
  timeout: 30_000,
  globalSetup: './tests/integration/global-setup.ts',
  webServer: {
    command: 'npm run build && npm run start',
    url: 'http://localhost:3000',
    reuseExistingServer: !process.env.CI,
    timeout: 120_000,
    env: {
      NEXTAUTH_SECRET,
      NEXTAUTH_URL: 'http://localhost:3000',
      BACKEND_URL: 'http://localhost:8000',
    },
  },
  use: {
    baseURL: 'http://localhost:3000',
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
