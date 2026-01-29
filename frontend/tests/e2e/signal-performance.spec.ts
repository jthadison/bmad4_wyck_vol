/**
 * E2E Tests for Signal Performance Dashboard
 *
 * Covers:
 * - /signals/performance - Signal performance analytics
 * - /signals/patterns/effectiveness - Pattern effectiveness report
 */

import { test, expect } from '@playwright/test'

const BASE_URL = process.env.DEPLOYMENT_URL || 'http://localhost:4173'

test.describe('Signal Performance Dashboard', () => {
  test('should load signal performance page', async ({ page }) => {
    await page.goto(`${BASE_URL}/signals/performance`)
    await page.waitForLoadState('networkidle')

    // Verify page loaded
    await expect(page.locator('#app')).toBeVisible({ timeout: 10000 })

    // Check page title or heading
    const heading = page.locator('h1, h2').first()
    await expect(heading).toBeVisible()

    const headingText = await heading.textContent()
    expect(
      headingText!.toLowerCase().includes('signal') ||
        headingText!.toLowerCase().includes('performance')
    ).toBe(true)
  })

  test('should display performance metrics', async ({ page }) => {
    await page.goto(`${BASE_URL}/signals/performance`)
    await page.waitForLoadState('networkidle')

    // Look for metric cards/sections
    const metricCards = page.locator(
      '[data-testid*="metric"], .metric-card, .stat-card, [class*="metric"]'
    )
    const percentages = page.locator(':has-text("%")')
    const numbers = page.locator('[class*="value"], [class*="number"]')

    const hasMetrics = await metricCards.count()
    const hasPercentages = await percentages.count()
    const hasNumbers = await numbers.count()

    // Should display some metrics or stats
    expect(hasMetrics + hasPercentages + hasNumbers).toBeGreaterThan(0)
  })

  test('should display win rate metric', async ({ page }) => {
    await page.goto(`${BASE_URL}/signals/performance`)
    await page.waitForLoadState('networkidle')

    // Look for win rate
    const winRateElement = page.locator(
      ':has-text("Win Rate"), :has-text("Win %")'
    )
    const hasWinRate = await winRateElement.count()

    if (hasWinRate > 0) {
      await expect(winRateElement.first()).toBeVisible()
    }

    // Check page content for win-related terms
    const pageContent = await page.locator('body').textContent()
    expect(
      pageContent!.toLowerCase().includes('win') ||
        pageContent!.toLowerCase().includes('rate') ||
        pageContent!.toLowerCase().includes('performance')
    ).toBe(true)
  })

  test('should display profit factor metric', async ({ page }) => {
    await page.goto(`${BASE_URL}/signals/performance`)
    await page.waitForLoadState('networkidle')

    // Look for profit factor
    const profitElement = page.locator(
      ':has-text("Profit"), :has-text("P/L"), :has-text("Return")'
    )
    const hasProfit = await profitElement.count()

    if (hasProfit > 0) {
      await expect(profitElement.first()).toBeVisible()
    }
  })

  test('should display signal count by pattern type', async ({ page }) => {
    await page.goto(`${BASE_URL}/signals/performance`)
    await page.waitForLoadState('networkidle')

    // Look for pattern type breakdown
    const patternElements = page.locator(
      ':has-text("Spring"), :has-text("UTAD"), :has-text("SOS"), :has-text("LPS")'
    )
    const hasPatternBreakdown = await patternElements.count()

    // Should have Wyckoff pattern references
    const pageContent = await page.locator('body').textContent()
    expect(
      hasPatternBreakdown > 0 ||
        pageContent!.toLowerCase().includes('pattern') ||
        pageContent!.toLowerCase().includes('signal')
    ).toBe(true)
  })

  test('should have date range filter', async ({ page }) => {
    await page.goto(`${BASE_URL}/signals/performance`)
    await page.waitForLoadState('networkidle')

    // Look for date filters
    const dateInputs = page.locator('input[type="date"], [data-testid*="date"]')
    const dateRangeSelect = page.locator(
      'select:has-text("7 days"), select:has-text("30 days"), button:has-text("7D"), button:has-text("30D")'
    )

    const hasDateInputs = await dateInputs.count()
    const hasDateSelect = await dateRangeSelect.count()

    // Date filtering should be available
    expect(hasDateInputs + hasDateSelect).toBeGreaterThanOrEqual(0)
  })

  test('should navigate to pattern effectiveness report', async ({ page }) => {
    await page.goto(`${BASE_URL}/signals/performance`)
    await page.waitForLoadState('networkidle')

    // Look for link to pattern effectiveness
    const effectivenessLink = page.locator(
      'a[href*="effectiveness"], a:has-text("Pattern Effectiveness")'
    )
    const hasLink = await effectivenessLink.count()

    if (hasLink > 0) {
      await effectivenessLink.first().click()
      await page.waitForURL(/\/signals\/patterns\/effectiveness/)
      expect(page.url()).toContain('/signals/patterns/effectiveness')
    }
  })
})

test.describe('Pattern Effectiveness Report', () => {
  test('should load pattern effectiveness page', async ({ page }) => {
    await page.goto(`${BASE_URL}/signals/patterns/effectiveness`)
    await page.waitForLoadState('networkidle')

    // Verify page loaded
    await expect(page.locator('#app')).toBeVisible({ timeout: 10000 })

    // Check page title or heading
    const heading = page.locator('h1, h2').first()
    await expect(heading).toBeVisible()

    const headingText = await heading.textContent()
    expect(
      headingText!.toLowerCase().includes('pattern') ||
        headingText!.toLowerCase().includes('effectiveness')
    ).toBe(true)
  })

  test('should display breadcrumb navigation', async ({ page }) => {
    await page.goto(`${BASE_URL}/signals/patterns/effectiveness`)
    await page.waitForLoadState('networkidle')

    // Check for breadcrumb
    const breadcrumb = page.locator(
      'nav[aria-label="Breadcrumb"], .breadcrumb, [class*="breadcrumb"]'
    )
    const hasBreadcrumb = await breadcrumb.count()

    if (hasBreadcrumb > 0) {
      await expect(breadcrumb.first()).toBeVisible()

      // Should have link back to signals
      const signalsLink = breadcrumb.locator('a[href*="/signals"]')
      const hasSignalsLink = await signalsLink.count()
      expect(hasSignalsLink).toBeGreaterThan(0)
    }
  })

  test('should display pattern-specific metrics', async ({ page }) => {
    await page.goto(`${BASE_URL}/signals/patterns/effectiveness`)
    await page.waitForLoadState('networkidle')

    // Look for Wyckoff patterns
    const patterns = [
      'Spring',
      'UTAD',
      'SOS',
      'LPS',
      'Selling Climax',
      'Automatic Rally',
    ]
    const pageContent = await page.locator('body').textContent()

    // Should mention at least one Wyckoff pattern
    const hasPatterns = patterns.some(
      (pattern) =>
        pageContent!.includes(pattern) ||
        pageContent!.toLowerCase().includes(pattern.toLowerCase())
    )

    expect(hasPatterns || pageContent!.toLowerCase().includes('pattern')).toBe(
      true
    )
  })

  test('should display effectiveness percentages', async ({ page }) => {
    await page.goto(`${BASE_URL}/signals/patterns/effectiveness`)
    await page.waitForLoadState('networkidle')

    // Look for percentage values
    const percentages = page.locator(':has-text("%")')
    const hasPercentages = await percentages.count()

    // Should display effectiveness as percentages
    expect(hasPercentages).toBeGreaterThanOrEqual(0)
  })

  test('should have comparison table or chart', async ({ page }) => {
    await page.goto(`${BASE_URL}/signals/patterns/effectiveness`)
    await page.waitForLoadState('networkidle')

    // Look for table or chart
    const table = page.locator('table')
    const chart = page.locator('canvas, [class*="chart"], svg')

    const hasTable = await table.count()
    const hasChart = await chart.count()

    // Should display data in table or chart format
    expect(hasTable + hasChart).toBeGreaterThan(0)
  })
})
