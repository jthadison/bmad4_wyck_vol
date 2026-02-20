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
    // Verify page header - use more specific selector for scanner page title
    await expect(
      page.locator('.scanner-view h1, .page-header h1').first()
    ).toContainText('Signal Scanner')
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

  test('should show empty state or symbol list', async ({ page }) => {
    // Wait for loading to complete
    await page.waitForTimeout(2000)

    // Check for either empty state, symbol list, or loading state
    const emptyState = page.locator('[data-testid="empty-state"]')
    const symbolList = page.locator('[data-testid="symbol-list"]')
    const loadingState = page.locator('.loading-state')

    const hasEmptyState = await emptyState.isVisible().catch(() => false)
    const hasSymbolList = await symbolList.isVisible().catch(() => false)
    const isLoading = await loadingState.isVisible().catch(() => false)

    // One of these states should be present (loading counts as valid initial state)
    // In e2e without a running backend, we may see loading state
    expect(hasEmptyState || hasSymbolList || isLoading).toBe(true)
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
    await page.waitForTimeout(1000)
  })

  test('should have add symbol button visible', async ({ page }) => {
    // Add button should be visible (either in header or empty state)
    const addButton = page.locator(
      '[data-testid="add-symbol-button"], [data-testid="add-symbol-button-empty"]'
    )
    await expect(addButton.first()).toBeVisible({ timeout: 10000 })
  })

  test('should open modal when add button clicked (requires backend)', async ({
    page,
  }) => {
    // Wait for add button - try empty state button first (doesn't require loading)
    const emptyButton = page.locator('[data-testid="add-symbol-button-empty"]')
    const headerButton = page.locator(
      '[data-testid="add-symbol-button"]:not([disabled])'
    )

    // Check which button is available
    const hasEmptyButton = await emptyButton.isVisible().catch(() => false)
    const hasHeaderButton = await headerButton.isVisible().catch(() => false)

    if (!hasEmptyButton && !hasHeaderButton) {
      // Skip test if no enabled button available (no backend)
      test.skip()
      return
    }

    const addButton = hasEmptyButton ? emptyButton : headerButton
    await addButton.click()

    // Modal should appear - PrimeVue Dialog uses role="dialog"
    const modal = page.locator(
      '[role="dialog"], [data-testid="add-symbol-modal"]'
    )
    await expect(modal.first()).toBeVisible({ timeout: 5000 })
  })

  test('should have input field in modal (requires backend)', async ({
    page,
  }) => {
    // Check for enabled button
    const emptyButton = page.locator('[data-testid="add-symbol-button-empty"]')
    const headerButton = page.locator(
      '[data-testid="add-symbol-button"]:not([disabled])'
    )

    const hasEmptyButton = await emptyButton.isVisible().catch(() => false)
    const hasHeaderButton = await headerButton.isVisible().catch(() => false)

    if (!hasEmptyButton && !hasHeaderButton) {
      test.skip()
      return
    }

    const addButton = hasEmptyButton ? emptyButton : headerButton
    await addButton.click()

    // Modal should have MultiSelect control with filter input
    const modal = page.locator('[role="dialog"]')
    await expect(modal.first()).toBeVisible({ timeout: 5000 })

    // Open MultiSelect dropdown (panel is a portal outside dialog DOM, use page scope)
    await modal.locator('.p-multiselect').click()
    const input = page.locator('.p-multiselect-filter').first()
    await expect(input).toBeVisible({ timeout: 3000 })
  })

  test('should close modal with Escape key (requires backend)', async ({
    page,
  }) => {
    // Check for enabled button
    const emptyButton = page.locator('[data-testid="add-symbol-button-empty"]')
    const headerButton = page.locator(
      '[data-testid="add-symbol-button"]:not([disabled])'
    )

    const hasEmptyButton = await emptyButton.isVisible().catch(() => false)
    const hasHeaderButton = await headerButton.isVisible().catch(() => false)

    if (!hasEmptyButton && !hasHeaderButton) {
      test.skip()
      return
    }

    const addButton = hasEmptyButton ? emptyButton : headerButton
    await addButton.click()

    // Modal should be visible
    const modal = page.locator('[role="dialog"]')
    await expect(modal.first()).toBeVisible({ timeout: 5000 })

    // Press Escape to close
    await page.keyboard.press('Escape')

    // Modal should be gone
    await expect(modal.first()).not.toBeVisible({ timeout: 5000 })
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

    // Page should load - use specific selector
    await expect(
      page.locator('.scanner-view h1, .page-header h1').first()
    ).toContainText('Signal Scanner')
  })
})

test.describe('Responsive Layout', () => {
  test('should display two-column layout on desktop', async ({ page }) => {
    await page.setViewportSize({ width: 1200, height: 800 })
    await page.goto(`${BASE_URL}/scanner`)
    await page.waitForLoadState('domcontentloaded')

    // Both main components should be visible
    const controlWidget = page.locator('[data-testid="scanner-control-widget"]')
    const watchlistManager = page.locator('[data-testid="watchlist-manager"]')

    await expect(controlWidget).toBeVisible()
    await expect(watchlistManager).toBeVisible()
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
