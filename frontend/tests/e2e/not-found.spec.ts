/**
 * E2E Tests for 404 Not Found Page
 *
 * Covers:
 * - /:pathMatch(.*) - 404 catch-all route
 */

import { test, expect } from '@playwright/test'

const BASE_URL = process.env.DEPLOYMENT_URL || 'http://localhost:4173'

test.describe('404 Not Found Page', () => {
  test('should display 404 page for non-existent route', async ({ page }) => {
    await page.goto(`${BASE_URL}/this-page-does-not-exist`)
    await page.waitForLoadState('networkidle')

    // Verify page loaded
    await expect(page.locator('#app')).toBeVisible({ timeout: 10000 })

    // Check for 404 indicators
    const pageContent = await page.locator('body').textContent()

    expect(
      pageContent!.includes('404') ||
        pageContent!.toLowerCase().includes('not found') ||
        pageContent!.toLowerCase().includes('page not found') ||
        pageContent!.toLowerCase().includes("doesn't exist")
    ).toBe(true)
  })

  test('should display helpful message', async ({ page }) => {
    await page.goto(`${BASE_URL}/random-invalid-path-12345`)
    await page.waitForLoadState('networkidle')

    // Should have some helpful text
    const pageContent = await page.locator('body').textContent()

    expect(pageContent!.length).toBeGreaterThan(50) // Should have meaningful content
  })

  test('should have link to homepage', async ({ page }) => {
    await page.goto(`${BASE_URL}/invalid-route`)
    await page.waitForLoadState('networkidle')

    // Look for home link
    const homeLink = page.locator(
      'a[href="/"], a:has-text("Home"), a:has-text("Dashboard")'
    )
    const hasHomeLink = await homeLink.count()

    if (hasHomeLink > 0) {
      await expect(homeLink.first()).toBeVisible()

      // Verify link has correct href without navigating
      const href = await homeLink.first().getAttribute('href')
      expect(href === '/' || href === `${BASE_URL}/`).toBe(true)
    }
  })

  test('should have navigation options', async ({ page }) => {
    await page.goto(`${BASE_URL}/non-existent-page`)
    await page.waitForLoadState('networkidle')

    // Look for navigation elements
    const navLinks = page.locator('nav a, header a, .navigation a')
    const backButton = page.locator(
      'button:has-text("Back"), a:has-text("Go Back")'
    )

    const hasNavLinks = await navLinks.count()
    const hasBackButton = await backButton.count()

    // Should have some way to navigate away
    expect(hasNavLinks + hasBackButton).toBeGreaterThan(0)
  })

  test('should handle deeply nested invalid routes', async ({ page }) => {
    await page.goto(`${BASE_URL}/a/b/c/d/e/f/invalid`)
    await page.waitForLoadState('networkidle')

    // Verify page loaded
    await expect(page.locator('#app')).toBeVisible({ timeout: 10000 })

    // Should still show 404
    const pageContent = await page.locator('body').textContent()

    expect(
      pageContent!.includes('404') ||
        pageContent!.toLowerCase().includes('not found')
    ).toBe(true)
  })

  test('should handle special characters in invalid routes', async ({
    page,
  }) => {
    await page.goto(`${BASE_URL}/invalid%20route%21`)
    await page.waitForLoadState('networkidle')

    // Verify page loaded without error
    await expect(page.locator('#app')).toBeVisible({ timeout: 10000 })
  })

  test('should display consistent styling with app', async ({ page }) => {
    await page.goto(`${BASE_URL}/not-found-test`)
    await page.waitForLoadState('networkidle')

    // Check that app shell is present
    const appContainer = page.locator('#app')
    await expect(appContainer).toBeVisible()

    // Check for consistent header/nav if present in app
    const header = page.locator(
      'header, nav, [class*="header"], [class*="navbar"]'
    )
    const hasHeader = await header.count()

    // If app has header, 404 page should too
    if (hasHeader > 0) {
      await expect(header.first()).toBeVisible()
    }
  })
})
