/**
 * E2E Test for Tutorials Page (Story 11.8b)
 *
 * Purpose:
 * --------
 * Validate that the tutorials page loads correctly and can fetch data from the API
 *
 * Test Coverage:
 * --------------
 * 1. Page loads without errors
 * 2. API requests succeed (no CORS errors)
 * 3. Page title renders
 * 4. Tutorial cards or list items render (if data exists)
 *
 * Usage:
 * ------
 * ```bash
 * # Run against development server
 * cd frontend
 * npx playwright test tutorials-page.spec.ts --config=playwright-dev.config.ts
 * ```
 */

import { test, expect } from '@playwright/test'

const BACKEND_URL = process.env.BACKEND_URL || 'http://localhost:8000'
const FRONTEND_URL = process.env.FRONTEND_URL || 'http://localhost:4173'
const TIMEOUT = 30000 // 30 seconds

test.describe('Tutorials Page (Story 11.8b)', () => {
  test('tutorials page loads without CORS errors', async ({ page }) => {
    // Listen for console errors
    const consoleErrors: string[] = []
    page.on('console', (msg) => {
      if (msg.type() === 'error') {
        consoleErrors.push(msg.text())
      }
    })

    // Listen for failed network requests
    const failedRequests: string[] = []
    page.on('requestfailed', (request) => {
      failedRequests.push(`${request.method()} ${request.url()}`)
    })

    // Navigate to tutorials page
    await page.goto(`${FRONTEND_URL}/tutorials`, {
      timeout: TIMEOUT,
      waitUntil: 'networkidle',
    })

    // Wait for Vue app to mount
    await page.waitForSelector('#app', { timeout: TIMEOUT })
    await page.waitForTimeout(2000)

    // Check for CORS-specific errors
    const corsErrors = consoleErrors.filter((error) =>
      error.toLowerCase().includes('cors')
    )
    const networkErrors = consoleErrors.filter(
      (error) =>
        error.toLowerCase().includes('failed to fetch') ||
        error.toLowerCase().includes('network error') ||
        error.toLowerCase().includes('net::err')
    )

    // Log all errors for debugging
    if (consoleErrors.length > 0) {
      console.log('Console Errors:', consoleErrors)
    }
    if (failedRequests.length > 0) {
      console.log('Failed Requests:', failedRequests)
    }

    // Assert no CORS errors
    expect(corsErrors).toHaveLength(0)
    expect(networkErrors).toHaveLength(0)
  })

  test('tutorials page renders title', async ({ page }) => {
    await page.goto(`${FRONTEND_URL}/tutorials`, {
      timeout: TIMEOUT,
      waitUntil: 'networkidle',
    })

    await page.waitForSelector('#app', { timeout: TIMEOUT })
    await page.waitForTimeout(2000)

    // Should have page title (correct class is .tutorial-title)
    const pageTitle = page.locator('.tutorial-title')
    const titleText = await pageTitle.textContent().catch(() => null)

    // Title should exist and contain "tutorial" (case insensitive)
    expect(titleText).toBeTruthy()
    if (titleText) {
      expect(titleText.toLowerCase()).toContain('tutorial')
    }
  })

  test('tutorials page makes successful API request', async ({ page }) => {
    // Track API requests
    const apiRequests: any[] = []
    page.on('response', (response) => {
      const url = response.url()
      if (url.includes('/api/v1/help/tutorials')) {
        apiRequests.push({
          url,
          status: response.status(),
          statusText: response.statusText(),
        })
      }
    })

    await page.goto(`${FRONTEND_URL}/tutorials`, {
      timeout: TIMEOUT,
      waitUntil: 'networkidle',
    })

    await page.waitForSelector('#app', { timeout: TIMEOUT })
    await page.waitForTimeout(2000)

    // Should have made at least one API request to tutorials endpoint
    expect(apiRequests.length).toBeGreaterThan(0)

    // All requests should be successful (200 OK)
    const allSuccessful = apiRequests.every((req) => req.status === 200)

    if (!allSuccessful) {
      console.log('API Requests:', apiRequests)
    }

    expect(allSuccessful).toBe(true)
  })

  test('tutorials page displays content or empty state', async ({ page }) => {
    await page.goto(`${FRONTEND_URL}/tutorials`, {
      timeout: TIMEOUT,
      waitUntil: 'networkidle',
    })

    await page.waitForSelector('#app', { timeout: TIMEOUT })
    await page.waitForTimeout(2000)

    // Should either have tutorial cards/items OR empty state message
    const tutorialItems = page.locator(
      '.tutorial-card, .tutorial-item, [data-testid="tutorial"]'
    )
    const emptyState = page.locator('text=/No tutorials/i, text=/coming soon/i')

    const hasItems = (await tutorialItems.count()) > 0
    const hasEmptyState = await emptyState.isVisible().catch(() => false)

    // Should have either items or empty state
    expect(hasItems || hasEmptyState).toBe(true)
  })

  test('no JavaScript errors on page load', async ({ page }) => {
    const jsErrors: Error[] = []
    page.on('pageerror', (error) => {
      jsErrors.push(error)
    })

    await page.goto(`${FRONTEND_URL}/tutorials`, {
      timeout: TIMEOUT,
      waitUntil: 'networkidle',
    })

    await page.waitForSelector('#app', { timeout: TIMEOUT })
    await page.waitForTimeout(2000)

    if (jsErrors.length > 0) {
      console.log(
        'JavaScript Errors:',
        jsErrors.map((e) => e.message)
      )
    }

    expect(jsErrors).toHaveLength(0)
  })
})
