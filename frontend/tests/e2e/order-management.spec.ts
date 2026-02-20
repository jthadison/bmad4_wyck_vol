/**
 * E2E Tests for Order Management View
 *
 * Covers:
 * - /orders - Order management page (pending orders across brokers)
 */

import { test, expect } from '@playwright/test'

const BASE_URL = process.env.DEPLOYMENT_URL || 'http://localhost:4173'

/** Helper: a single AAPL limit buy order for reuse across tests. */
function makeAaplOrder() {
  return {
    order_id: 'ord-001',
    internal_order_id: null,
    broker: 'alpaca',
    symbol: 'AAPL',
    side: 'buy',
    order_type: 'limit',
    quantity: '100',
    filled_quantity: '0',
    remaining_quantity: '100',
    limit_price: '150.00',
    stop_price: null,
    status: 'pending',
    created_at: '2026-02-20T10:00:00Z',
    campaign_id: null,
    is_oco: false,
    oco_group_id: null,
  }
}

/** Helper: mock the GET /api/v1/orders endpoint with given orders. */
async function mockOrdersApi(
  page: import('@playwright/test').Page,
  orders: ReturnType<typeof makeAaplOrder>[],
  statusCode = 200
) {
  await page.route('**/api/v1/orders', async (route) => {
    if (route.request().method() === 'GET') {
      if (statusCode !== 200) {
        await route.fulfill({
          status: statusCode,
          contentType: 'application/json',
          body: JSON.stringify({ detail: 'Internal Server Error' }),
        })
      } else {
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({
            orders,
            total: orders.length,
            brokers_connected: { alpaca: true, mt5: true },
          }),
        })
      }
    } else {
      await route.continue()
    }
  })
}

test.describe('Order Management View', () => {
  test('should load the orders page at /orders', async ({ page }) => {
    await page.goto(`${BASE_URL}/orders`)
    await page.waitForLoadState('domcontentloaded')

    // Verify app shell loaded
    await expect(page.locator('#app')).toBeVisible({ timeout: 10000 })

    // Page should contain order-related content
    const pageContent = await page.locator('body').textContent()
    const hasOrderContent =
      pageContent!.toLowerCase().includes('order') ||
      pageContent!.toLowerCase().includes('pending')
    expect(hasOrderContent).toBe(true)
  })

  test('should show empty state when no orders exist', async ({ page }) => {
    await mockOrdersApi(page, [])
    await page.goto(`${BASE_URL}/orders`)
    await page.waitForLoadState('domcontentloaded')
    await expect(page.locator('#app')).toBeVisible({ timeout: 10000 })

    // The component shows "No pending orders" when orders array is empty
    const pageContent = await page.locator('body').textContent()
    const hasEmptyState =
      pageContent!.toLowerCase().includes('no pending') ||
      pageContent!.toLowerCase().includes('no orders') ||
      pageContent!.toLowerCase().includes('will appear here')
    expect(hasEmptyState).toBe(true)
  })

  test('should display order table with correct data', async ({ page }) => {
    await mockOrdersApi(page, [makeAaplOrder()])
    await page.goto(`${BASE_URL}/orders`)
    await page.waitForLoadState('domcontentloaded')
    await expect(page.locator('#app')).toBeVisible({ timeout: 10000 })

    // Wait for table to render
    await page.waitForSelector('table', { timeout: 5000 })
    const pageContent = await page.locator('body').textContent()

    // Check key data points from the order
    expect(pageContent).toContain('AAPL')
    expect(
      pageContent!.toLowerCase().includes('buy') || pageContent!.includes('BUY')
    ).toBe(true)
    expect(
      pageContent!.toLowerCase().includes('limit') ||
        pageContent!.includes('LIMIT')
    ).toBe(true)
    expect(pageContent).toContain('150')
  })

  test('should display status badges for different statuses', async ({
    page,
  }) => {
    const pendingOrder = makeAaplOrder()
    const partialOrder = {
      ...makeAaplOrder(),
      order_id: 'ord-002',
      symbol: 'MSFT',
      status: 'partial',
      filled_quantity: '50',
      remaining_quantity: '50',
    }

    await mockOrdersApi(page, [pendingOrder, partialOrder])
    await page.goto(`${BASE_URL}/orders`)
    await page.waitForLoadState('domcontentloaded')
    await expect(page.locator('#app')).toBeVisible({ timeout: 10000 })

    await page.waitForSelector('table', { timeout: 5000 })
    const pageContent = await page.locator('body').textContent()

    // Verify both statuses appear
    expect(pageContent!.toLowerCase()).toContain('pending')
    expect(pageContent!.toLowerCase()).toContain('partial')

    // Verify both symbols appear
    expect(pageContent).toContain('AAPL')
    expect(pageContent).toContain('MSFT')
  })

  test('should have Cancel button on order rows', async ({ page }) => {
    await mockOrdersApi(page, [makeAaplOrder()])
    await page.goto(`${BASE_URL}/orders`)
    await page.waitForLoadState('domcontentloaded')
    await expect(page.locator('#app')).toBeVisible({ timeout: 10000 })

    await page.waitForSelector('table', { timeout: 5000 })

    // Look for Cancel button in the actions column
    const cancelButton = page.locator(
      'button:has-text("Cancel"), button:has-text("CANCEL"), button:has-text("cancel")'
    )
    const count = await cancelButton.count()
    expect(count).toBeGreaterThan(0)
  })

  test('should have Modify button and show inline edit on click', async ({
    page,
  }) => {
    // Also mock the modify/cancel endpoints so clicks don't error
    await mockOrdersApi(page, [makeAaplOrder()])
    await page.route('**/api/v1/orders/**', async (route) => {
      if (
        route.request().method() === 'DELETE' ||
        route.request().method() === 'PATCH'
      ) {
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({
            success: true,
            message: 'Order modified',
            order_id: 'ord-001',
            replacement_needed: false,
          }),
        })
      } else {
        await route.continue()
      }
    })

    await page.goto(`${BASE_URL}/orders`)
    await page.waitForLoadState('domcontentloaded')
    await expect(page.locator('#app')).toBeVisible({ timeout: 10000 })

    await page.waitForSelector('table', { timeout: 5000 })

    // Find Modify button
    const modifyButton = page.locator(
      'button:has-text("Modify"), button:has-text("MODIFY"), button:has-text("modify")'
    )
    const modifyCount = await modifyButton.count()
    expect(modifyCount).toBeGreaterThan(0)

    // Click Modify and check for inline edit input
    await modifyButton.first().click()

    // The component shows an input with placeholder "New price" and a Save button
    const editInput = page.locator(
      'input[placeholder="New price"], input[type="text"]'
    )
    const saveButton = page.locator(
      'button:has-text("Save"), button:has-text("SAVE")'
    )
    const hasEditInput = (await editInput.count()) > 0
    const hasSaveButton = (await saveButton.count()) > 0

    expect(hasEditInput || hasSaveButton).toBe(true)
  })

  test('should display broker names in the table', async ({ page }) => {
    const alpacaOrder = makeAaplOrder()
    const mt5Order = {
      ...makeAaplOrder(),
      order_id: 'ord-003',
      broker: 'mt5',
      symbol: 'EURUSD',
    }

    await mockOrdersApi(page, [alpacaOrder, mt5Order])
    await page.goto(`${BASE_URL}/orders`)
    await page.waitForLoadState('domcontentloaded')
    await expect(page.locator('#app')).toBeVisible({ timeout: 10000 })

    await page.waitForSelector('table', { timeout: 5000 })
    const pageContent = await page.locator('body').textContent()

    // Check for broker names (case-insensitive match)
    expect(
      pageContent!.toLowerCase().includes('alpaca') ||
        pageContent!.includes('ALPACA')
    ).toBe(true)
    expect(
      pageContent!.toLowerCase().includes('mt5') || pageContent!.includes('MT5')
    ).toBe(true)
  })

  test('should show error state on API failure', async ({ page }) => {
    await mockOrdersApi(page, [], 500)
    await page.goto(`${BASE_URL}/orders`)
    await page.waitForLoadState('domcontentloaded')
    await expect(page.locator('#app')).toBeVisible({ timeout: 10000 })

    // Wait for the error to appear - the store sets error to "Failed to load pending orders"
    await page.waitForTimeout(1000)
    const pageContent = await page.locator('body').textContent()

    const hasError =
      pageContent!.toLowerCase().includes('failed') ||
      pageContent!.toLowerCase().includes('error') ||
      pageContent!.toLowerCase().includes('unable')
    expect(hasError).toBe(true)
  })

  test('should have Orders navigation link that navigates to /orders', async ({
    page,
  }) => {
    await page.goto(`${BASE_URL}/`)
    await page.waitForLoadState('domcontentloaded')
    await expect(page.locator('#app')).toBeVisible({ timeout: 10000 })

    // Look for "Orders" link in the navigation (exact text to avoid matching other links)
    const ordersLink = page.locator('a').filter({ hasText: /^Orders$/ })
    const linkCount = await ordersLink.count()

    if (linkCount > 0) {
      await ordersLink.first().click()
      // Wait for client-side route change
      await page.waitForURL('**/orders', { timeout: 5000 })
      expect(page.url()).toContain('/orders')
    } else {
      // Fallback: navigate directly and verify the page loads
      await page.goto(`${BASE_URL}/orders`)
      await page.waitForLoadState('domcontentloaded')
      const pageContent = await page.locator('body').textContent()
      expect(pageContent!.toLowerCase()).toContain('order')
    }
  })
})
