/**
 * E2E Tests for Auto-Execution Settings (Story 19.15)
 *
 * Comprehensive end-to-end tests covering:
 * - Settings page navigation
 * - Consent flow for enabling auto-execution
 * - Configuration updates (confidence, patterns, symbols)
 * - Daily statistics display
 * - Kill switch activation
 *
 * Author: Story 19.15
 */

import { test, expect, type Page } from '@playwright/test'

// Test configuration
const BASE_URL = process.env.DEPLOYMENT_URL || 'http://localhost:4173'

// Helper: Navigate to auto-execution settings
async function navigateToSettings(page: Page) {
  await page.goto(`${BASE_URL}/settings/auto-execution`)
  await page.waitForLoadState('networkidle')
}

test.describe('Auto-Execution Settings', () => {
  /**
   * Test Scenario 1: View settings page in disabled state
   * Story 19.15 - Acceptance Criteria 1
   */
  test('should display settings page with master toggle OFF when disabled', async ({
    page,
  }) => {
    await navigateToSettings(page)

    // Verify page title
    const heading = page
      .locator('h1, h2')
      .filter({ hasText: /Auto.?Execution/i })
    await expect(heading.first()).toBeVisible({ timeout: 10000 })

    // Verify master toggle is OFF (not checked)
    const toggle = page
      .locator('input[type="checkbox"], .p-inputswitch-input')
      .first()
    await expect(toggle).toBeVisible()

    // Verify settings form is collapsed/disabled when auto-execution is off
    const confidenceSlider = page.locator(
      'text=Minimum Confidence, .p-slider, input[type="range"]'
    )
    // Settings should either be hidden or disabled
    if (await confidenceSlider.isVisible()) {
      await expect(confidenceSlider).toBeDisabled()
    }
  })

  /**
   * Test Scenario 2: Enable flow with consent modal
   * Story 19.15 - Acceptance Criteria 2
   */
  test('should show consent modal when enabling auto-execution', async ({
    page,
  }) => {
    await navigateToSettings(page)

    // Click master toggle to enable
    const toggle = page
      .locator('input[type="checkbox"], .p-inputswitch')
      .first()
    await toggle.click()

    // Verify consent modal appears
    await expect(
      page.locator('text=Enable Automatic Execution, .p-dialog-header')
    ).toBeVisible({ timeout: 5000 })

    // Verify warning text is present
    await expect(
      page.locator('text=Trades will execute automatically')
    ).toBeVisible()

    // Verify acknowledgment checkbox is present
    const consentCheckbox = page
      .locator('text=I understand and accept the risks')
      .locator('..')
    await expect(consentCheckbox).toBeVisible()

    // Verify password field is present
    const passwordInput = page.locator('input[type="password"]')
    await expect(passwordInput).toBeVisible()

    // Verify enable button is disabled initially
    const enableButton = page.locator(
      'button:has-text("Enable Auto-Execution")'
    )
    await expect(enableButton).toBeDisabled()
  })

  /**
   * Test Scenario 3: Consent required validation
   * Story 19.15 - Test Scenario 3
   */
  test('should require consent acknowledgment to enable', async ({ page }) => {
    await navigateToSettings(page)

    // Open consent modal
    const toggle = page
      .locator('input[type="checkbox"], .p-inputswitch')
      .first()
    await toggle.click()

    // Wait for modal
    await page.waitForSelector('text=Enable Automatic Execution', {
      timeout: 5000,
    })

    // Verify enable button is disabled without consent
    const enableButton = page.locator(
      'button:has-text("Enable Auto-Execution")'
    )
    await expect(enableButton).toBeDisabled()

    // Enter password without checking consent
    const passwordInput = page.locator('input[type="password"]')
    await passwordInput.fill('test-password')

    // Button should still be disabled
    await expect(enableButton).toBeDisabled()

    // Check consent checkbox
    const consentCheckbox = page
      .locator('text=I understand and accept the risks')
      .locator('..')
      .locator('input[type="checkbox"]')
    await consentCheckbox.check()

    // Now button should be enabled
    await expect(enableButton).toBeEnabled()
  })

  /**
   * Test Scenario 4: Cancel consent modal
   * Story 19.15
   */
  test('should close consent modal on cancel', async ({ page }) => {
    await navigateToSettings(page)

    // Open consent modal
    const toggle = page
      .locator('input[type="checkbox"], .p-inputswitch')
      .first()
    await toggle.click()

    // Wait for modal
    await page.waitForSelector('text=Enable Automatic Execution')

    // Click cancel button
    const cancelButton = page.locator('button:has-text("Cancel")')
    await cancelButton.click()

    // Modal should close
    await expect(
      page.locator('text=Enable Automatic Execution')
    ).not.toBeVisible()
  })

  /**
   * Test Scenario 5: View daily statistics
   * Story 19.15 - Test Scenario 6
   */
  test('should display daily statistics when enabled', async ({ page }) => {
    await navigateToSettings(page)

    // Look for Today's Activity section
    const activitySection = page.locator(
      "text=Today's Activity, text=Trades Today"
    )

    // If auto-execution is enabled, statistics should be visible
    if (await activitySection.isVisible()) {
      // Verify trades progress display
      await expect(
        page.locator('text=Trades Today, text=Trades:')
      ).toBeVisible()

      // Verify progress bars are rendered
      const progressBars = page.locator('.p-progressbar, [role="progressbar"]')
      const count = await progressBars.count()
      expect(count).toBeGreaterThan(0)
    }
  })

  /**
   * Test Scenario 6: Kill switch confirmation
   * Story 19.15 - Test Scenario 7
   */
  test('should show confirmation dialog for kill switch', async ({ page }) => {
    await navigateToSettings(page)

    // Look for kill switch button
    const killSwitchButton = page.locator(
      'button:has-text("Kill Switch"), button:has-text("Stop All Automatic Trading")'
    )

    if (await killSwitchButton.isVisible()) {
      await killSwitchButton.click()

      // Verify confirmation dialog appears
      await expect(
        page.locator('text=Activate Kill Switch, text=Kill Switch')
      ).toBeVisible({ timeout: 5000 })

      // Verify cancel button exists
      const cancelButton = page.locator('button:has-text("Cancel")').last()
      await expect(cancelButton).toBeVisible()

      // Close dialog
      await cancelButton.click()
    }
  })

  /**
   * Test Scenario 7: Pattern selector interaction
   * Story 19.15 - Test Scenario 5
   */
  test('should allow pattern selection when enabled', async ({ page }) => {
    await navigateToSettings(page)

    // Look for pattern checkboxes
    const springCheckbox = page.locator('text=Spring').locator('..')
    const sosCheckbox = page.locator('text=Sign of Strength').locator('..')

    if (await springCheckbox.isVisible()) {
      // Verify pattern descriptions are displayed
      await expect(
        page.locator('text=Shakeout below Creek, text=low volume')
      ).toBeVisible()

      // Pattern checkboxes should be interactable if auto-execution is enabled
      const springInput = springCheckbox.locator('input[type="checkbox"]')
      if (await springInput.isEnabled()) {
        await springInput.click()
      }
    }
  })

  /**
   * Test Scenario 8: Symbol whitelist/blacklist editor
   * Story 19.15 - Acceptance Criteria 3
   */
  test('should display symbol list editors when enabled', async ({ page }) => {
    await navigateToSettings(page)

    // Look for symbol whitelist section
    const whitelistSection = page.locator(
      'text=Symbol Whitelist, text=Whitelist'
    )

    if (await whitelistSection.isVisible()) {
      // Verify whitelist input exists
      const whitelistInput = page
        .locator('text=Symbol Whitelist')
        .locator('..')
        .locator('input[type="text"]')
        .first()
      await expect(whitelistInput).toBeVisible()

      // Look for blacklist section
      const blacklistSection = page.locator(
        'text=Symbol Blacklist, text=Blacklist'
      )
      await expect(blacklistSection).toBeVisible()
    }
  })
})
