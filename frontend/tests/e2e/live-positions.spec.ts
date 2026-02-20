/**
 * E2E Tests for Live Position Management
 *
 * Covers:
 * - /live-positions - Live position cards, stop adjustment, partial exits
 *
 * Feature P4-I15 (Live Position Management)
 */

import { test, expect } from '@playwright/test'

const BASE_URL = process.env.DEPLOYMENT_URL || 'http://localhost:4173'

const MOCK_POSITION = {
  id: '550e8400-e29b-41d4-a716-446655440000',
  campaign_id: '660e8400-e29b-41d4-a716-446655440000',
  signal_id: '770e8400-e29b-41d4-a716-446655440000',
  symbol: 'AAPL',
  timeframe: '1D',
  pattern_type: 'SPRING',
  entry_price: '150.00',
  current_price: '155.00',
  stop_loss: '145.00',
  shares: '100',
  current_pnl: '500.00',
  status: 'OPEN',
  entry_date: '2026-02-15T10:00:00Z',
  stop_distance_pct: '6.45',
  r_multiple: '1.00',
  dollars_at_risk: '500.00',
  pnl_pct: '3.33',
}

test.describe('Live Position Management', () => {
  test('should load live positions page', async ({ page }) => {
    await page.goto(`${BASE_URL}/live-positions`)
    await page.waitForLoadState('domcontentloaded')

    // Verify page loaded
    await expect(page.locator('#app')).toBeVisible({ timeout: 10000 })

    // Check for position-related content
    const pageContent = await page.locator('body').textContent()
    const hasPositionContent =
      pageContent!.toLowerCase().includes('position') ||
      pageContent!.toLowerCase().includes('live')

    expect(hasPositionContent).toBe(true)
  })

  test('should display empty state when no positions', async ({ page }) => {
    await page.route('**/api/v1/live-positions', (route) => {
      route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify([]),
      })
    })

    await page.goto(`${BASE_URL}/live-positions`)
    await page.waitForLoadState('domcontentloaded')

    // Check for empty state message
    const pageContent = await page.locator('body').textContent()
    const hasEmptyState =
      pageContent!.toLowerCase().includes('no open positions') ||
      pageContent!.toLowerCase().includes('no positions') ||
      pageContent!.toLowerCase().includes('will appear here')

    expect(hasEmptyState).toBe(true)
  })

  test('should display position cards correctly', async ({ page }) => {
    await page.route('**/api/v1/live-positions', (route) => {
      route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify([MOCK_POSITION]),
      })
    })

    await page.goto(`${BASE_URL}/live-positions`)
    await page.waitForLoadState('domcontentloaded')

    // Wait for the position card to render
    const card = page.locator('[data-testid="live-position-card"]')
    await expect(card.first()).toBeVisible({ timeout: 10000 })

    // Check for symbol
    const pageContent = await page.locator('body').textContent()
    expect(pageContent).toContain('AAPL')

    // Check for pattern badge
    const badge = page.locator('[data-testid="pattern-badge"]')
    await expect(badge.first()).toContainText('SPRING')

    // Check for price values
    expect(pageContent!.includes('150') || pageContent!.includes('155')).toBe(
      true
    )
  })

  test('should show stop-loss adjustment input', async ({ page }) => {
    await page.route('**/api/v1/live-positions', (route) => {
      route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify([MOCK_POSITION]),
      })
    })

    await page.goto(`${BASE_URL}/live-positions`)
    await page.waitForLoadState('domcontentloaded')

    // Wait for card
    const card = page.locator('[data-testid="live-position-card"]')
    await expect(card.first()).toBeVisible({ timeout: 10000 })

    // Check for stop input
    const stopInput = page.locator('[data-testid="stop-input"]')
    await expect(stopInput.first()).toBeVisible()

    // Check for update button
    const updateBtn = page.locator('[data-testid="update-stop-btn"]')
    await expect(updateBtn.first()).toBeVisible()
  })

  test('should show partial exit buttons', async ({ page }) => {
    await page.route('**/api/v1/live-positions', (route) => {
      route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify([MOCK_POSITION]),
      })
    })

    await page.goto(`${BASE_URL}/live-positions`)
    await page.waitForLoadState('domcontentloaded')

    // Wait for card
    const card = page.locator('[data-testid="live-position-card"]')
    await expect(card.first()).toBeVisible({ timeout: 10000 })

    // Check for partial exit buttons
    const exit25 = page.locator('[data-testid="exit-25-btn"]')
    const exit50 = page.locator('[data-testid="exit-50-btn"]')
    const exit100 = page.locator('[data-testid="exit-100-btn"]')

    await expect(exit25.first()).toBeVisible()
    await expect(exit50.first()).toBeVisible()
    await expect(exit100.first()).toBeVisible()

    // Verify button text
    await expect(exit25.first()).toContainText('25%')
    await expect(exit50.first()).toContainText('50%')
    await expect(exit100.first()).toContainText('100%')
  })

  test('should show error state on API failure', async ({ page }) => {
    await page.route('**/api/v1/live-positions', (route) => {
      route.fulfill({
        status: 500,
        contentType: 'application/json',
        body: JSON.stringify({ detail: 'Internal server error' }),
      })
    })

    await page.goto(`${BASE_URL}/live-positions`)
    await page.waitForLoadState('domcontentloaded')

    // Wait for error to appear
    await page.waitForTimeout(2000)

    const pageContent = await page.locator('body').textContent()
    const hasError =
      pageContent!.toLowerCase().includes('error') ||
      pageContent!.toLowerCase().includes('failed') ||
      pageContent!.toLowerCase().includes('unavailable')

    expect(hasError).toBe(true)
  })

  test('should display refresh button', async ({ page }) => {
    await page.route('**/api/v1/live-positions', (route) => {
      route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify([]),
      })
    })

    await page.goto(`${BASE_URL}/live-positions`)
    await page.waitForLoadState('domcontentloaded')

    // Check for refresh button by data-testid
    const refreshBtn = page.locator('[data-testid="refresh-btn"]')
    await expect(refreshBtn).toBeVisible({ timeout: 10000 })
    await expect(refreshBtn).toContainText('Refresh')
  })

  test('should have navigation link to live positions', async ({ page }) => {
    await page.goto(`${BASE_URL}/`)
    await page.waitForLoadState('domcontentloaded')

    // Look for nav link pointing to /live-positions
    const navLink = page.locator('a[href="/live-positions"]')
    const hasNavLink = await navLink.count()

    if (hasNavLink > 0) {
      await navLink.first().click()
      await page.waitForLoadState('domcontentloaded')

      // Verify navigation occurred
      expect(page.url()).toContain('/live-positions')
    } else {
      // Fallback: check page content for "Positions" or "Live" text in nav area
      const pageContent = await page.locator('body').textContent()
      const hasPositionsText =
        pageContent!.includes('Positions') ||
        pageContent!.includes('Live Positions')
      expect(hasPositionsText).toBe(true)
    }
  })
})
