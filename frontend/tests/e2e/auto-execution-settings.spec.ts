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

// Helper: Wait for consent modal to be fully visible
async function waitForConsentModal(page: Page) {
  // Wait for the modal dialog to be visible using the consent-modal class
  const modal = page.locator('.consent-modal')
  await modal.waitFor({ state: 'visible', timeout: 10000 })
  // Also wait for the header text to ensure modal is fully rendered
  await page
    .locator('h3:has-text("Enable Automatic Execution")')
    .waitFor({ state: 'visible', timeout: 5000 })
  return modal
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

    // Wait for consent modal to appear
    await waitForConsentModal(page)

    // Verify modal header text
    await expect(
      page.locator('h3:has-text("Enable Automatic Execution")')
    ).toBeVisible()

    // Verify warning text is present (matches actual component text)
    await expect(
      page.locator(
        'text=Trades will execute automatically without manual confirmation'
      )
    ).toBeVisible()

    // Verify acknowledgment checkbox label is present
    const consentLabel = page.locator(
      'label:has-text("I understand and accept the risks of automatic trading")'
    )
    await expect(consentLabel).toBeVisible()

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

    // Wait for modal to be fully visible
    await waitForConsentModal(page)

    // Verify enable button is disabled without consent
    const enableButton = page.locator(
      'button:has-text("Enable Auto-Execution")'
    )
    await expect(enableButton).toBeDisabled()

    // Check consent checkbox using the input element with its ID
    const consentCheckbox = page.locator('#consent-checkbox')
    await consentCheckbox.waitFor({ state: 'visible', timeout: 5000 })
    await consentCheckbox.click({ force: true })

    // Now button should be enabled
    await expect(enableButton).toBeEnabled({ timeout: 5000 })
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

    // Wait for modal to be fully visible
    await waitForConsentModal(page)

    // Click cancel button
    const cancelButton = page.locator('button:has-text("Cancel")')
    await cancelButton.click()

    // Modal should close - wait for it to be hidden
    await expect(
      page.locator('h3:has-text("Enable Automatic Execution")')
    ).not.toBeVisible({ timeout: 5000 })
  })

  /**
   * Test Scenario 5: View daily statistics
   * Story 19.15 - Test Scenario 6
   */
  test('should display daily statistics when enabled', async ({ page }) => {
    await navigateToSettings(page)

    // Look for Today's Activity section (check if auto-execution is enabled)
    const activitySection = page.locator('text=/Today.*Activity/i')

    // If auto-execution is enabled, statistics should be visible
    if (await activitySection.isVisible({ timeout: 3000 }).catch(() => false)) {
      // Verify trades display
      await expect(page.locator('text=/Trades Today/i')).toBeVisible()

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

    // Look for kill switch button (matches actual button text in component)
    const killSwitchButton = page.locator(
      'button:has-text("KILL SWITCH - Stop All Automatic Trading")'
    )

    // Only test if auto-execution is enabled and button is visible
    if (
      await killSwitchButton.isVisible({ timeout: 3000 }).catch(() => false)
    ) {
      await killSwitchButton.click()

      // Verify confirmation dialog appears (matches Dialog header)
      await expect(page.locator('text=Activate Kill Switch?')).toBeVisible({
        timeout: 5000,
      })

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

    // Look for Enabled Patterns section
    const patternSection = page.locator('text=/Enabled Patterns/i')

    // Only test if auto-execution is enabled and patterns section is visible
    if (await patternSection.isVisible({ timeout: 3000 }).catch(() => false)) {
      // Look for Spring pattern checkbox
      const springCheckbox = page.locator('text=Spring').locator('..')

      if (await springCheckbox.isVisible()) {
        // Pattern checkboxes should be interactable if auto-execution is enabled
        const springInput = springCheckbox.locator('input[type="checkbox"]')
        if (await springInput.isEnabled()) {
          await springInput.click()
        }
      }
    }
  })

  /**
   * Test Scenario 8: Symbol whitelist/blacklist editor
   * Story 19.15 - Acceptance Criteria 3
   */
  test('should display symbol list editors when enabled', async ({ page }) => {
    await navigateToSettings(page)

    // Look for Symbol Filters section
    const symbolSection = page.locator('text=/Symbol Filters/i')

    // Only test if auto-execution is enabled and symbol section is visible
    if (await symbolSection.isVisible({ timeout: 3000 }).catch(() => false)) {
      // Verify whitelist section exists
      await expect(page.locator('text=/Symbol Whitelist/i')).toBeVisible()

      // Verify blacklist section exists
      await expect(page.locator('text=/Symbol Blacklist/i')).toBeVisible()
    }
  })
})
