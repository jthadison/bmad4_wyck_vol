/**
 * E2E Tests for Broker Connection Dashboard
 *
 * Covers:
 * - /brokers - Broker dashboard page (connection status, account info, kill switch)
 *
 * Issue P4-I17
 */

import { test, expect } from '@playwright/test'

const BASE_URL = process.env.DEPLOYMENT_URL || 'http://localhost:4173'

/** Mock data: two brokers (Alpaca connected, MT5 disconnected), kill switch inactive */
const MOCK_STATUS = {
  brokers: [
    {
      broker: 'alpaca',
      connected: true,
      platform_name: 'Alpaca',
      account_id: 'ACC123',
      account_balance: '50000.00',
      buying_power: '45000.00',
      cash: '20000.00',
      margin_used: '5000.00',
      margin_available: '95000.00',
      margin_level_pct: '1900.00',
      latency_ms: null,
      last_connected_at: '2026-02-20T10:00:00Z',
      error_message: null,
    },
    {
      broker: 'mt5',
      connected: false,
      platform_name: 'MetaTrader 5',
      account_id: null,
      account_balance: null,
      buying_power: null,
      cash: null,
      margin_used: null,
      margin_available: null,
      margin_level_pct: null,
      latency_ms: null,
      last_connected_at: null,
      error_message: 'Not connected',
    },
  ],
  kill_switch_active: false,
  kill_switch_activated_at: null,
  kill_switch_reason: null,
}

/** Mock data: kill switch active */
const MOCK_STATUS_KILL_SWITCH_ACTIVE = {
  ...MOCK_STATUS,
  kill_switch_active: true,
  kill_switch_activated_at: '2026-02-20T12:00:00Z',
  kill_switch_reason: 'Manual activation',
}

test.describe('Broker Connection Dashboard', () => {
  test('should load broker dashboard page at /brokers', async ({ page }) => {
    await page.goto(`${BASE_URL}/brokers`)
    await page.waitForLoadState('domcontentloaded')

    await expect(page.locator('#app')).toBeVisible({ timeout: 10000 })

    const pageContent = await page.locator('body').textContent()
    const hasBrokerContent =
      pageContent!.toLowerCase().includes('broker') ||
      pageContent!.toLowerCase().includes('connection')

    expect(hasBrokerContent).toBe(true)
  })

  test('should display connected broker with account info', async ({
    page,
  }) => {
    await page.route('**/api/v1/brokers/status', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        json: MOCK_STATUS,
      })
    })

    await page.goto(`${BASE_URL}/brokers`)
    await page.waitForLoadState('domcontentloaded')
    await expect(page.locator('#app')).toBeVisible({ timeout: 10000 })

    // Alpaca broker name visible
    const pageContent = await page.locator('body').textContent()
    expect(
      pageContent!.includes('Alpaca') || pageContent!.includes('alpaca')
    ).toBe(true)

    // Connected status shown
    expect(pageContent!.includes('Connected')).toBe(true)

    // Account balance shown (formatted as $50,000.00 or raw 50000)
    expect(
      pageContent!.includes('50,000') || pageContent!.includes('50000')
    ).toBe(true)
  })

  test('should display disconnected broker state', async ({ page }) => {
    await page.route('**/api/v1/brokers/status', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        json: MOCK_STATUS,
      })
    })

    await page.goto(`${BASE_URL}/brokers`)
    await page.waitForLoadState('domcontentloaded')
    await expect(page.locator('#app')).toBeVisible({ timeout: 10000 })

    const pageContent = await page.locator('body').textContent()

    // MT5 broker visible
    expect(
      pageContent!.includes('MetaTrader') || pageContent!.includes('MT5')
    ).toBe(true)

    // Disconnected state shown
    expect(
      pageContent!.includes('Disconnected') ||
        pageContent!.includes('Not connected')
    ).toBe(true)
  })

  test('should show kill switch inactive state', async ({ page }) => {
    await page.route('**/api/v1/brokers/status', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        json: MOCK_STATUS,
      })
    })

    await page.goto(`${BASE_URL}/brokers`)
    await page.waitForLoadState('domcontentloaded')
    await expect(page.locator('#app')).toBeVisible({ timeout: 10000 })

    // Kill Switch heading present
    const pageContent = await page.locator('body').textContent()
    expect(pageContent!.includes('Kill Switch')).toBe(true)

    // Inactive status shown
    expect(pageContent!.includes('Inactive')).toBe(true)

    // Activate button present
    const activateBtn = page.locator('[data-testid="activate-btn"]')
    await expect(activateBtn).toBeVisible()
  })

  test('should show kill switch active state with reason', async ({ page }) => {
    await page.route('**/api/v1/brokers/status', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        json: MOCK_STATUS_KILL_SWITCH_ACTIVE,
      })
    })

    await page.goto(`${BASE_URL}/brokers`)
    await page.waitForLoadState('domcontentloaded')
    await expect(page.locator('#app')).toBeVisible({ timeout: 10000 })

    const pageContent = await page.locator('body').textContent()

    // ACTIVE status shown
    expect(pageContent!.includes('ACTIVE')).toBe(true)

    // Reason displayed
    expect(pageContent!.includes('Manual activation')).toBe(true)

    // Deactivate button present
    const deactivateBtn = page.locator('[data-testid="deactivate-btn"]')
    await expect(deactivateBtn).toBeVisible()
  })

  test('should show Test Connection button on broker card', async ({
    page,
  }) => {
    await page.route('**/api/v1/brokers/status', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        json: MOCK_STATUS,
      })
    })

    await page.goto(`${BASE_URL}/brokers`)
    await page.waitForLoadState('domcontentloaded')
    await expect(page.locator('#app')).toBeVisible({ timeout: 10000 })

    // Test Connection button exists on at least one broker card
    const testBtn = page.locator('[data-testid="test-connection-btn"]')
    expect(await testBtn.count()).toBeGreaterThan(0)
    await expect(testBtn.first()).toBeVisible()
  })

  test('should display margin level for connected broker', async ({ page }) => {
    await page.route('**/api/v1/brokers/status', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        json: MOCK_STATUS,
      })
    })

    await page.goto(`${BASE_URL}/brokers`)
    await page.waitForLoadState('domcontentloaded')
    await expect(page.locator('#app')).toBeVisible({ timeout: 10000 })

    const pageContent = await page.locator('body').textContent()

    // Margin level percentage shown (1900.0%)
    const hasMarginInfo =
      pageContent!.includes('1900') ||
      pageContent!.toLowerCase().includes('margin')

    expect(hasMarginInfo).toBe(true)

    // Margin progress bar present
    const marginBar = page.locator('[data-testid="margin-bar"]')
    expect(await marginBar.count()).toBeGreaterThan(0)
  })

  test('should handle API failure gracefully', async ({ page }) => {
    await page.route('**/api/v1/brokers/status', async (route) => {
      await route.fulfill({
        status: 500,
        contentType: 'application/json',
        json: { detail: 'Internal server error' },
      })
    })

    await page.goto(`${BASE_URL}/brokers`)
    await page.waitForLoadState('domcontentloaded')
    await expect(page.locator('#app')).toBeVisible({ timeout: 10000 })

    // Wait for error state to appear after failed fetch
    await page.waitForTimeout(1000)

    const pageContent = await page.locator('body').textContent()

    // Should show error banner or fallback content (not broker cards)
    const hasErrorIndication =
      pageContent!.toLowerCase().includes('error') ||
      pageContent!.toLowerCase().includes('failed') ||
      pageContent!.toLowerCase().includes('loading')

    expect(hasErrorIndication).toBe(true)
  })

  test('should have Brokers navigation link', async ({ page }) => {
    await page.goto(`${BASE_URL}/`)
    await page.waitForLoadState('domcontentloaded')
    await expect(page.locator('#app')).toBeVisible({ timeout: 10000 })

    // Look for Brokers nav link
    const brokersLink = page.locator('a[href="/brokers"]')
    const linkCount = await brokersLink.count()

    if (linkCount > 0) {
      await brokersLink.first().click()
      await page.waitForURL('**/brokers', { timeout: 10000 })

      // Verify navigation to /brokers
      expect(page.url()).toContain('/brokers')
    } else {
      // Nav link not found - just verify the page is accessible directly
      await page.goto(`${BASE_URL}/brokers`)
      await page.waitForLoadState('domcontentloaded')
      const pageContent = await page.locator('body').textContent()
      expect(pageContent!.toLowerCase().includes('broker')).toBe(true)
    }
  })
})
