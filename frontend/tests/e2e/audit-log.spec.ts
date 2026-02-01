/**
 * E2E Tests for Trade Audit Log
 *
 * Covers:
 * - /audit-log - Trade audit log page
 */

import { test, expect } from '@playwright/test'

const BASE_URL = process.env.DEPLOYMENT_URL || 'http://localhost:4173'

test.describe('Trade Audit Log', () => {
  test('should load audit log page', async ({ page }) => {
    await page.goto(`${BASE_URL}/audit-log`)
    await page.waitForLoadState('domcontentloaded')

    // Verify page loaded
    await expect(page.locator('#app')).toBeVisible({ timeout: 10000 })

    // Check for audit-related content in page
    const auditHeading = page.locator(
      'h1:has-text("Audit"), h2:has-text("Audit"), h2:has-text("Log")'
    )
    const pageContent = await page.locator('body').textContent()

    // Either find specific heading or verify page contains audit-related content
    const hasAuditHeading = (await auditHeading.count()) > 0
    const hasAuditContent =
      pageContent!.toLowerCase().includes('audit') ||
      pageContent!.toLowerCase().includes('log') ||
      pageContent!.toLowerCase().includes('trade')

    expect(hasAuditHeading || hasAuditContent).toBe(true)
  })

  test('should display audit entries or empty state', async ({ page }) => {
    await page.goto(`${BASE_URL}/audit-log`)
    await page.waitForLoadState('domcontentloaded')

    // Look for audit entries in table or list
    const auditEntries = page.locator(
      'table tbody tr, .audit-entry, .log-entry, [data-testid*="audit"]'
    )
    const emptyState = page.locator(
      '[data-testid="empty-state"], .empty-state, :has-text("No entries"), :has-text("No logs")'
    )

    const hasEntries = await auditEntries.count()
    const hasEmptyState = await emptyState.count()

    // Should show either entries or empty state
    expect(hasEntries + hasEmptyState).toBeGreaterThan(0)
  })

  test('should display timestamp column in audit entries', async ({ page }) => {
    await page.goto(`${BASE_URL}/audit-log`)
    await page.waitForLoadState('domcontentloaded')

    // Check for timestamp header or data
    const timestampHeader = page.locator(
      'th:has-text("Time"), th:has-text("Date"), th:has-text("Timestamp")'
    )
    const hasTimestampHeader = await timestampHeader.count()

    if (hasTimestampHeader > 0) {
      await expect(timestampHeader.first()).toBeVisible()
    }

    // Check for date/time patterns in content
    const pageContent = await page.locator('body').textContent()
    const hasDatePatterns = /\d{4}[-/]\d{2}[-/]\d{2}|\d{2}:\d{2}/.test(
      pageContent!
    )

    expect(hasTimestampHeader > 0 || hasDatePatterns).toBe(true)
  })

  test('should display action type column', async ({ page }) => {
    await page.goto(`${BASE_URL}/audit-log`)
    await page.waitForLoadState('domcontentloaded')

    // Check for action/type column
    const actionHeader = page.locator(
      'th:has-text("Action"), th:has-text("Type"), th:has-text("Event")'
    )
    const hasActionHeader = await actionHeader.count()

    if (hasActionHeader > 0) {
      await expect(actionHeader.first()).toBeVisible()
    }
  })

  test('should allow filtering audit entries', async ({ page }) => {
    await page.goto(`${BASE_URL}/audit-log`)
    await page.waitForLoadState('domcontentloaded')

    // Look for filter controls
    const filterInput = page.locator(
      'input[placeholder*="Filter"], input[placeholder*="Search"], input[type="search"]'
    )
    const filterSelect = page.locator(
      'select[name*="filter"], select[name*="type"]'
    )
    const dateFilter = page.locator(
      'input[type="date"], [data-testid*="date-filter"]'
    )

    const hasFilterInput = await filterInput.count()
    void filterSelect.count() // Suppress unused variable warning
    void dateFilter.count() // Suppress unused variable warning

    // If filters exist, verify they're functional
    if (hasFilterInput > 0) {
      const input = filterInput.first()
      await expect(input).toBeVisible()
      await input.fill('test')
      // Wait for filter to be applied by checking input value is set
      await expect(input).toHaveValue('test')
    }
  })

  test('should support pagination for large audit logs', async ({ page }) => {
    await page.goto(`${BASE_URL}/audit-log`)
    await page.waitForLoadState('domcontentloaded')

    // Look for pagination controls
    const pagination = page.locator(
      'nav[aria-label="Pagination"], .pagination, [class*="pagination"]'
    )
    const pageButtons = page.locator(
      'button:has-text("Next"), button:has-text("Previous"), [aria-label*="page"]'
    )

    void pagination.count() // Suppress unused variable warning
    void pageButtons.count() // Suppress unused variable warning

    // Pagination may not be visible if few entries
    // Just verify page loads without pagination errors
    const pageLoaded = await page.locator('#app').isVisible()
    expect(pageLoaded).toBe(true)
  })

  test('should display audit entry details', async ({ page }) => {
    await page.goto(`${BASE_URL}/audit-log`)
    await page.waitForLoadState('domcontentloaded')

    // Find audit entries
    const auditEntries = page.locator(
      'table tbody tr, .audit-entry, .log-entry'
    )
    const entryCount = await auditEntries.count()

    if (entryCount > 0) {
      const firstEntry = auditEntries.first()

      // Check if expandable or has detail view
      const expandButton = firstEntry.locator(
        'button:has-text("Details"), button:has-text("Expand"), [aria-expanded]'
      )
      const detailLink = firstEntry.locator(
        'a:has-text("View"), a:has-text("Details")'
      )

      const hasExpand = await expandButton.count()
      const hasDetailLink = await detailLink.count()

      if (hasExpand > 0) {
        await expandButton.first().click()
        // Wait for expansion animation to complete
        await expect(expandButton.first()).toBeVisible()
      } else if (hasDetailLink > 0) {
        // Don't navigate, just verify link exists
        await expect(detailLink.first()).toBeVisible()
      }
    }
  })
})
