/**
 * E2E test for Gold (XAUUSD) and Silver (XAGUSD) in Scanner Add Symbol Modal
 *
 * Verifies that:
 * 1. The "Forex - Metals" group appears in the dropdown
 * 2. XAUUSD (Gold) is available as a selectable symbol
 * 3. XAGUSD (Silver) is available as a selectable symbol
 */

import { test, expect } from '@playwright/test'

test.describe('Scanner - Gold & Silver Symbol Addition', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/scanner')
  })

  test('should display Forex - Metals group with Gold and Silver in Add Symbol modal', async ({
    page,
  }) => {
    // Mock the watchlist to be empty so all symbols (including XAUUSD/XAGUSD)
    // appear in the Add Symbol dropdown — live watchlist may already contain metals
    await page.route('**/api/v1/scanner/watchlist', (route) => {
      route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: '[]',
      })
    })
    // Reload to pick up mocked empty watchlist
    await page.goto('/scanner')

    // Click the "Add Symbol" button to open modal
    await page.click('button:has-text("Add Symbol")')

    // Wait for modal to be visible
    await expect(page.locator('.p-dialog')).toBeVisible()

    // Open the MultiSelect dropdown to reveal symbol groups
    await page.click('.p-multiselect')
    await page.waitForTimeout(300)

    // Check for "Forex - Metals" group header
    const metalsGroup = page.locator('text=Forex - Metals')
    await expect(metalsGroup).toBeVisible()

    // Check for Gold (XAUUSD) option
    const goldOption = page.locator('text=XAUUSD')
    await expect(goldOption).toBeVisible()

    // Verify Gold name includes "Gold / US Dollar"
    const goldName = page.locator('text=Gold / US Dollar')
    await expect(goldName).toBeVisible()

    // Check for Silver (XAGUSD) option
    const silverOption = page.locator('text=XAGUSD')
    await expect(silverOption).toBeVisible()

    // Verify Silver name includes "Silver / US Dollar"
    const silverName = page.locator('text=Silver / US Dollar')
    await expect(silverName).toBeVisible()
  })

  test('should allow selecting and adding XAUUSD (Gold) to watchlist', async ({
    page,
  }) => {
    // Click the "Add Symbol" button
    await page.click('button:has-text("Add Symbol")')

    // Wait for modal
    await expect(page.locator('.p-dialog')).toBeVisible()

    // Open the MultiSelect dropdown to reveal symbols
    await page.click('.p-multiselect')
    await page.waitForTimeout(300)

    // Verify XAUUSD option is visible and selectable
    await expect(page.locator('text=XAUUSD').first()).toBeVisible()

    // Note: Actual watchlist add requires backend to be running - just verify UI presence
  })

  test('should allow selecting and adding XAGUSD (Silver) to watchlist', async ({
    page,
  }) => {
    // Click the "Add Symbol" button
    await page.click('button:has-text("Add Symbol")')

    // Wait for modal
    await expect(page.locator('.p-dialog')).toBeVisible()

    // Open the MultiSelect dropdown to reveal symbols
    await page.click('.p-multiselect')
    await page.waitForTimeout(300)

    // Verify XAGUSD option is visible and selectable
    await expect(page.locator('text=XAGUSD').first()).toBeVisible()

    // Note: Actual watchlist add requires backend to be running - just verify UI presence
  })

  test('should display both major forex pairs and metals in dropdown', async ({
    page,
  }) => {
    // Click the "Add Symbol" button
    await page.click('button:has-text("Add Symbol")')

    // Wait for modal
    await expect(page.locator('.p-dialog')).toBeVisible()

    // Open the MultiSelect dropdown to reveal symbol groups
    await page.click('.p-multiselect')
    await page.waitForTimeout(300)

    // Verify Forex - Majors group still exists
    await expect(page.locator('text=Forex - Majors')).toBeVisible()

    // Verify major pairs still present (e.g., EURUSD)
    await expect(page.locator('text=EURUSD')).toBeVisible()

    // Verify new Forex - Metals group exists
    await expect(page.locator('text=Forex - Metals')).toBeVisible()

    // Verify both metals present
    await expect(page.locator('text=XAUUSD')).toBeVisible()
    await expect(page.locator('text=XAGUSD')).toBeVisible()
  })
})
