/**
 * Playwright Configuration for Development Testing
 *
 * This configuration runs tests against the running development server
 * without starting a new web server.
 */
import { defineConfig, devices } from '@playwright/test'

export default defineConfig({
  testDir: './tests/smoke',
  fullyParallel: false, // Run serially for development testing
  forbidOnly: false,
  retries: 0,
  workers: 1,
  reporter: [['list'], ['html', { outputFolder: 'playwright-report-dev' }]],
  timeout: 60000, // 60 seconds per test
  use: {
    baseURL: 'http://localhost:5175',
    trace: 'on-first-retry',
    screenshot: 'only-on-failure',
    video: 'retain-on-failure',
  },
  projects: [
    {
      name: 'chromium',
      use: { ...devices['Desktop Chrome'] },
    },
  ],
  // No webServer - we expect the dev server to already be running
})
