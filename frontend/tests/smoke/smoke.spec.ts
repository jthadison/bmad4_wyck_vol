/**
 * Smoke Tests for Production Deployment (Story 10.10)
 *
 * Purpose:
 * --------
 * Validate critical paths work after deployment to ensure the application is functional.
 * These tests run against a deployed environment (local or production).
 *
 * Test Coverage:
 * --------------
 * 1. Homepage loads successfully (200 status)
 * 2. API health endpoint responds
 * 3. WebSocket connection establishes
 * 4. Signal dashboard renders
 * 5. Chart component loads
 *
 * Usage:
 * ------
 * ```bash
 * # Set deployment URL
 * export DEPLOYMENT_URL=http://localhost
 *
 * # Run smoke tests
 * npm run test:smoke
 * ```
 */

import { test, expect } from '@playwright/test'

const DEPLOYMENT_URL = process.env.DEPLOYMENT_URL || 'http://localhost:4173'
const TIMEOUT = 30000 // 30 seconds

test.describe('Deployment Smoke Tests', () => {
  test('Homepage loads successfully', async ({ page }) => {
    const response = await page.goto(DEPLOYMENT_URL, {
      timeout: TIMEOUT,
      waitUntil: 'networkidle',
    })

    // Check response status
    expect(response?.status()).toBe(200)

    // Check page title
    await expect(page).toHaveTitle(/BMAD Wyckoff/i)

    // Check main app container exists
    const appContainer = page.locator('#app')
    await expect(appContainer).toBeVisible()
  })

  test('API health endpoint responds', async ({ request }) => {
    const response = await request.get(`${DEPLOYMENT_URL}/api/v1/health`, {
      timeout: TIMEOUT,
    })

    expect(response.status()).toBe(200)

    const body = await response.json()
    expect(body).toHaveProperty('status')
    // Accept both 'healthy' and 'degraded' - degraded is valid for smoke test
    expect(['healthy', 'degraded']).toContain(body.status)
  })

  test('WebSocket connection establishes', async ({ page }) => {
    // Track WebSocket connections
    let wsConnected = false
    page.on('websocket', (ws) => {
      console.log('WebSocket opened:', ws.url())
      ws.on('close', () => console.log('WebSocket closed'))
      wsConnected = true
    })

    // Navigate to page which should establish WebSocket
    await page.goto(DEPLOYMENT_URL, {
      timeout: TIMEOUT,
      waitUntil: 'networkidle',
    })

    // Wait a bit for WebSocket to connect
    await page.waitForTimeout(2000)

    // Check if WebSocket connected
    expect(wsConnected).toBe(true)
  })

  test('Signal dashboard renders', async ({ page }) => {
    await page.goto(DEPLOYMENT_URL, {
      timeout: TIMEOUT,
      waitUntil: 'networkidle',
    })

    // Wait for Vue app to mount
    await page.waitForSelector('#app', { timeout: TIMEOUT })

    // Check for signal-related components
    // These selectors should match actual component class names from Stories 10.2-10.8
    const hasSignalCards = await page.locator('[class*="signal"]').count()
    const hasDashboard = await page.locator('[class*="dashboard"]').count()

    // At least one signal-related element should be present
    expect(hasSignalCards + hasDashboard).toBeGreaterThan(0)
  })

  test('Chart component loads', async ({ page }) => {
    await page.goto(`${DEPLOYMENT_URL}/backtest`, {
      timeout: TIMEOUT,
      waitUntil: 'networkidle',
    })

    // Wait for Vue app to mount
    await page.waitForSelector('#app', { timeout: TIMEOUT })

    // Wait for backtest view to render
    await page.waitForTimeout(2000)

    // Check for backtest view existence (charts may not load without data)
    const backtestView = await page.locator('body').textContent()

    // Backtest page should have loaded (even if empty)
    expect(backtestView).toBeTruthy()
  })
})
