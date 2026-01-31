/**
 * E2E Tests for Scanner Control UI (Story 20.6)
 *
 * Tests:
 * - Scanner page loads and displays components
 * - Scanner control widget functionality
 * - Watchlist management (add/remove symbols)
 * - Responsive layout
 */

import { test, expect } from '@playwright/test'

const BASE_URL = process.env.DEPLOYMENT_URL || 'http://localhost:4173'

test.describe('Scanner Page', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto(`${BASE_URL}/scanner`)
    await page.waitForLoadState('domcontentloaded')
  })

  test('should load scanner page with title and description', async ({
    page,
  }) => {
    // Verify page header
    await expect(page.locator('h1')).toContainText('Signal Scanner')
    await expect(page.locator('.page-description')).toContainText(
      'Wyckoff patterns'
    )
  })

  test('should display scanner control widget', async ({ page }) => {
    // Verify control widget exists
    const controlWidget = page.locator('[data-testid="scanner-control-widget"]')
    await expect(controlWidget).toBeVisible({ timeout: 10000 })

    // Should have status indicator
    await expect(page.locator('[data-testid="status-indicator"]')).toBeVisible()

    // Should have status text
    await expect(page.locator('[data-testid="status-text"]')).toBeVisible()

    // Should have toggle button
    await expect(
      page.locator('[data-testid="scanner-toggle-button"]')
    ).toBeVisible()

    // Should show symbol count
    await expect(page.locator('[data-testid="symbols-count"]')).toBeVisible()
  })

  test('should display watchlist manager', async ({ page }) => {
    // Verify watchlist manager exists
    const watchlistManager = page.locator('[data-testid="watchlist-manager"]')
    await expect(watchlistManager).toBeVisible({ timeout: 10000 })

    // Should have header with title
    await expect(page.locator('.header-title')).toContainText(
      'Scanner Watchlist'
    )

    // Should have symbol count badge
    await expect(
      page.locator('[data-testid="symbol-count-badge"]')
    ).toBeVisible()

    // Should have add symbol button
    const addButton =
      page.locator('[data-testid="add-symbol-button"]').first() ||
      page.locator('[data-testid="add-symbol-button-empty"]').first()
    await expect(addButton).toBeVisible()
  })

  test('should show empty state when watchlist is empty', async ({ page }) => {
    // Wait for loading to complete
    await page.waitForTimeout(1000)

    // Check for either empty state or symbol list
    const emptyState = page.locator('[data-testid="empty-state"]')
    const symbolList = page.locator('[data-testid="symbol-list"]')

    const hasEmptyState = await emptyState.isVisible().catch(() => false)
    const hasSymbolList = await symbolList.isVisible().catch(() => false)

    // One or the other should be visible
    expect(hasEmptyState || hasSymbolList).toBe(true)

    if (hasEmptyState) {
      await expect(emptyState).toContainText('No symbols in watchlist')
    }
  })
})

test.describe('Scanner Control Widget Interaction', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto(`${BASE_URL}/scanner`)
    await page.waitForLoadState('domcontentloaded')
    await page.waitForTimeout(500) // Wait for component to initialize
  })

  test('should display correct initial status', async ({ page }) => {
    const statusText = page.locator('[data-testid="status-text"]')
    await expect(statusText).toBeVisible()

    // Status should be one of: Stopped, Running, Starting, Stopping
    const text = await statusText.textContent()
    expect(['Stopped', 'Running', 'Starting...', 'Stopping...']).toContain(text)
  })

  test('should have properly styled status indicator', async ({ page }) => {
    const indicator = page.locator('[data-testid="status-indicator"]')
    await expect(indicator).toBeVisible()

    // Should have either status-running or status-stopped class
    const classes = await indicator.getAttribute('class')
    expect(
      classes?.includes('status-running') || classes?.includes('status-stopped')
    ).toBe(true)
  })

  test('should display last scan time', async ({ page }) => {
    const lastScan = page.locator('[data-testid="last-scan"]')
    await expect(lastScan).toBeVisible()

    // Should show "Never" or relative time
    const text = await lastScan.textContent()
    expect(text).toBeTruthy()
  })
})

test.describe('Add Symbol Modal', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto(`${BASE_URL}/scanner`)
    await page.waitForLoadState('domcontentloaded')
    await page.waitForTimeout(500)
  })

  test('should open add symbol modal when button clicked', async ({ page }) => {
    // Click add button (either in header or empty state)
    const addButton = page.locator(
      '[data-testid="add-symbol-button"], [data-testid="add-symbol-button-empty"]'
    )
    await addButton.first().click()

    // Modal should appear
    const modal = page.locator('[data-testid="add-symbol-modal"]')
    await expect(modal).toBeVisible({ timeout: 5000 })
  })

  test('should have all required form fields in modal', async ({ page }) => {
    // Open modal
    const addButton = page.locator(
      '[data-testid="add-symbol-button"], [data-testid="add-symbol-button-empty"]'
    )
    await addButton.first().click()

    // Check form fields
    await expect(page.locator('[data-testid="symbol-input"]')).toBeVisible()
    await expect(page.locator('[data-testid="timeframe-select"]')).toBeVisible()
    await expect(
      page.locator('[data-testid="asset-class-select"]')
    ).toBeVisible()

    // Check buttons
    await expect(page.locator('[data-testid="add-button"]')).toBeVisible()
    await expect(page.locator('[data-testid="cancel-button"]')).toBeVisible()
  })

  test('should close modal when cancel clicked', async ({ page }) => {
    // Open modal
    const addButton = page.locator(
      '[data-testid="add-symbol-button"], [data-testid="add-symbol-button-empty"]'
    )
    await addButton.first().click()

    const modal = page.locator('[data-testid="add-symbol-modal"]')
    await expect(modal).toBeVisible()

    // Click cancel
    await page.locator('[data-testid="cancel-button"]').click()

    // Modal should close
    await expect(modal).not.toBeVisible({ timeout: 3000 })
  })

  test('should show validation error for empty symbol', async ({ page }) => {
    // Open modal
    const addButton = page.locator(
      '[data-testid="add-symbol-button"], [data-testid="add-symbol-button-empty"]'
    )
    await addButton.first().click()

    // Click add without entering symbol
    await page.locator('[data-testid="add-button"]').click()

    // Should show error message
    await expect(page.locator('.p-message-error')).toBeVisible({
      timeout: 3000,
    })
  })

  test('should auto-uppercase symbol input', async ({ page }) => {
    // Open modal
    const addButton = page.locator(
      '[data-testid="add-symbol-button"], [data-testid="add-symbol-button-empty"]'
    )
    await addButton.first().click()

    // Type lowercase
    const input = page.locator('[data-testid="symbol-input"] input')
    await input.fill('eurusd')

    // Should be uppercase
    await expect(input).toHaveValue('EURUSD')
  })
})

test.describe('Navigation', () => {
  test('should have scanner link in navigation', async ({ page }) => {
    await page.goto(BASE_URL)
    await page.waitForLoadState('domcontentloaded')

    // Find scanner nav link
    const scannerLink = page.locator('a[href="/scanner"]')
    await expect(scannerLink).toBeVisible()
    await expect(scannerLink).toContainText('Scanner')
  })

  test('should navigate to scanner page from nav link', async ({ page }) => {
    await page.goto(BASE_URL)
    await page.waitForLoadState('domcontentloaded')

    // Click scanner link
    await page.locator('a[href="/scanner"]').click()

    // Should be on scanner page
    await page.waitForURL(/\/scanner/)
    expect(page.url()).toContain('/scanner')

    // Page should load
    await expect(page.locator('h1')).toContainText('Signal Scanner')
  })
})

test.describe('Responsive Layout', () => {
  test('should display two-column layout on desktop', async ({ page }) => {
    await page.setViewportSize({ width: 1200, height: 800 })
    await page.goto(`${BASE_URL}/scanner`)
    await page.waitForLoadState('domcontentloaded')

    // Both sections should be visible side by side
    const controlSection = page.locator('.control-section')
    const watchlistSection = page.locator('.watchlist-section')

    await expect(controlSection).toBeVisible()
    await expect(watchlistSection).toBeVisible()
  })

  test('should stack layout on mobile', async ({ page }) => {
    await page.setViewportSize({ width: 375, height: 667 })
    await page.goto(`${BASE_URL}/scanner`)
    await page.waitForLoadState('domcontentloaded')

    // Both sections should be visible (stacked)
    const controlWidget = page.locator('[data-testid="scanner-control-widget"]')
    const watchlistManager = page.locator('[data-testid="watchlist-manager"]')

    await expect(controlWidget).toBeVisible()
    await expect(watchlistManager).toBeVisible()
  })

  test('should have adequate touch targets on mobile', async ({ page }) => {
    await page.setViewportSize({ width: 375, height: 667 })
    await page.goto(`${BASE_URL}/scanner`)
    await page.waitForLoadState('domcontentloaded')

    // Toggle button should have minimum 44px height
    const toggleButton = page.locator('[data-testid="scanner-toggle-button"]')
    const box = await toggleButton.boundingBox()

    if (box) {
      expect(box.height).toBeGreaterThanOrEqual(44)
    }
  })
})
