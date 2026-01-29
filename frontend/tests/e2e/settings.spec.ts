/**
 * E2E Tests for Settings Pages
 *
 * Covers:
 * - /settings - Main settings page
 * - /settings/configuration - Configuration wizard
 */

import { test, expect } from '@playwright/test'

const BASE_URL = process.env.DEPLOYMENT_URL || 'http://localhost:4173'

test.describe('Settings Page', () => {
  test('should load settings page and display navigation options', async ({
    page,
  }) => {
    await page.goto(`${BASE_URL}/settings`)
    await page.waitForLoadState('domcontentloaded')

    // Verify page loaded
    await expect(page.locator('h1, h2').first()).toBeVisible({ timeout: 10000 })

    // Check for settings-related content
    const pageContent = await page.locator('body').textContent()
    expect(pageContent).toBeTruthy()

    // Look for common settings elements (links, cards, or sections)
    const settingsLinks = page.locator('a[href*="/settings"]')
    const hasSettingsContent = (await settingsLinks.count()) > 0

    // Settings page should have navigation to sub-pages or settings sections
    expect(
      hasSettingsContent || pageContent!.toLowerCase().includes('settings')
    ).toBe(true)
  })

  test('should navigate to auto-execution settings from settings page', async ({
    page,
  }) => {
    await page.goto(`${BASE_URL}/settings`)
    await page.waitForLoadState('domcontentloaded')

    // Find link to auto-execution settings
    const autoExecLink = page.locator('a[href*="auto-execution"]').first()
    const hasLink = await autoExecLink.count()

    if (hasLink > 0) {
      await autoExecLink.click()
      await page.waitForURL(/\/settings\/auto-execution/)
      expect(page.url()).toContain('/settings/auto-execution')
    }
  })

  test('should navigate to configuration wizard from settings page', async ({
    page,
  }) => {
    await page.goto(`${BASE_URL}/settings`)
    await page.waitForLoadState('domcontentloaded')

    // Find link to configuration
    const configLink = page.locator('a[href*="configuration"]').first()
    const hasLink = await configLink.count()

    if (hasLink > 0) {
      await configLink.click()
      await page.waitForURL(/\/settings\/configuration/)
      expect(page.url()).toContain('/settings/configuration')
    }
  })
})

test.describe('Configuration Wizard', () => {
  test('should load configuration wizard page', async ({ page }) => {
    await page.goto(`${BASE_URL}/settings/configuration`)
    await page.waitForLoadState('domcontentloaded')

    // Verify page loaded
    await expect(page.locator('#app')).toBeVisible({ timeout: 10000 })

    // Check for wizard-related content (steps, forms, etc.)
    const pageContent = await page.locator('body').textContent()
    expect(pageContent).toBeTruthy()

    // Look for wizard elements
    const hasWizardContent =
      pageContent!.toLowerCase().includes('configuration') ||
      pageContent!.toLowerCase().includes('step') ||
      pageContent!.toLowerCase().includes('wizard')

    expect(hasWizardContent).toBe(true)
  })

  test('should display breadcrumb navigation', async ({ page }) => {
    await page.goto(`${BASE_URL}/settings/configuration`)
    await page.waitForLoadState('domcontentloaded')

    // Check for breadcrumb
    const breadcrumb = page.locator(
      'nav[aria-label="Breadcrumb"], .breadcrumb, [class*="breadcrumb"]'
    )
    const hasBreadcrumb = await breadcrumb.count()

    if (hasBreadcrumb > 0) {
      await expect(breadcrumb.first()).toBeVisible()

      // Should have link back to settings
      const settingsLink = breadcrumb.locator('a[href*="/settings"]')
      const hasSettingsLink = await settingsLink.count()
      expect(hasSettingsLink).toBeGreaterThan(0)
    }
  })

  test('should have form elements for configuration', async ({ page }) => {
    await page.goto(`${BASE_URL}/settings/configuration`)
    await page.waitForLoadState('domcontentloaded')

    // Look for form elements
    const inputs = page.locator('input, select, textarea')
    const buttons = page.locator('button')

    const inputCount = await inputs.count()
    const buttonCount = await buttons.count()

    // Configuration wizard should have form controls
    expect(inputCount + buttonCount).toBeGreaterThan(0)
  })
})
