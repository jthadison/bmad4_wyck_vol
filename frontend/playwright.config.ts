import { defineConfig, devices } from '@playwright/test'

export default defineConfig({
  testDir: './tests/e2e',
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  workers: process.env.CI ? 1 : 4, // Limit to 4 workers to prevent resource contention
  reporter: [['html', { outputFolder: 'playwright-report' }], ['list']],
  timeout: 30000, // 30 seconds per test (as per Story 12.11)
  use: {
    baseURL: process.env.DEPLOYMENT_URL || 'http://localhost:4173',
    trace: 'on-first-retry',
    screenshot: 'only-on-failure',
    video: 'retain-on-failure', // Record video on failure (as per Story 12.11)
  },
  projects: [
    {
      name: 'chromium',
      use: { ...devices['Desktop Chrome'] },
    },
    {
      name: 'firefox',
      use: { ...devices['Desktop Firefox'] },
    },
    {
      name: 'webkit',
      use: { ...devices['Desktop Safari'] },
    },
  ],
  webServer: process.env.CI
    ? undefined
    : {
        command: 'npm run preview',
        port: 4173,
        reuseExistingServer: !process.env.CI,
      },
})
