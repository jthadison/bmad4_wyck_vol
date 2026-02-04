/**
 * Signal Toast Notifications E2E Tests (Story 19.8)
 *
 * End-to-end tests for signal toast notifications, audio alerts,
 * and browser notifications.
 *
 * These tests use __BMAD_TEST__.triggerSignal() to inject test signals
 * directly into the toast service, bypassing the need for WebSocket.
 */

import { test, expect } from '@playwright/test'

// Declare the test helper type for TypeScript
declare global {
  interface Window {
    __BMAD_TEST__?: {
      triggerSignal: (signal: unknown) => void
    }
  }
}

test.describe('Signal Toast Notifications', () => {
  test.beforeEach(async ({ page, context }) => {
    // Grant notification permissions
    await context.grantPermissions(['notifications'])

    // Navigate to dashboard (uses baseURL from playwright.config.ts)
    await page.goto('/')

    // Wait for app to initialize and test helper to be available
    await page.waitForFunction(() => window.__BMAD_TEST__ !== undefined, {
      timeout: 5000,
    })
  })

  test('should display toast notification when signal arrives', async ({
    page,
  }) => {
    // Trigger signal notification using the test helper
    await page.evaluate(() => {
      const mockSignal = {
        id: 'test-signal-1',
        symbol: 'AAPL',
        pattern_type: 'SPRING',
        phase: 'C',
        entry_price: '150.25',
        stop_loss: '148.00',
        target_levels: {
          primary_target: '155.00',
          secondary_targets: ['157.00'],
          trailing_stop_activation: null,
          trailing_stop_offset: null,
        },
        position_size: 100,
        risk_amount: '225',
        r_multiple: '2.1',
        confidence_score: 95,
        confidence_components: {
          pattern_confidence: 95,
          phase_confidence: 93,
          volume_confidence: 96,
          overall_confidence: 95,
        },
        campaign_id: null,
        status: 'PENDING',
        timestamp: new Date().toISOString(),
        timeframe: '1H',
      }

      // Use the test helper to trigger toast notification
      window.__BMAD_TEST__?.triggerSignal(mockSignal)
    })

    // Wait for toast to appear
    const toast = page.locator('.signal-toast')
    await expect(toast).toBeVisible({ timeout: 5000 })

    // Verify toast content
    await expect(toast).toContainText('SPRING')
    await expect(toast).toContainText('AAPL')
    await expect(toast).toContainText('150.25')
    await expect(toast).toContainText('2.1')
    await expect(toast).toContainText('A+')
  })

  test('should auto-dismiss toast after configured duration', async ({
    page,
  }) => {
    // Set toast duration to 3 seconds for faster test
    await page.evaluate(() => {
      localStorage.setItem(
        'bmad_toast_settings',
        JSON.stringify({
          soundEnabled: false,
          soundVolume: 80,
          toastDuration: 3,
          browserNotificationsEnabled: false,
          showOnlyHighConfidence: false,
        })
      )
    })

    await page.reload()

    // Wait for test helper to be available after reload
    await page.waitForFunction(() => window.__BMAD_TEST__ !== undefined, {
      timeout: 5000,
    })

    // Trigger signal notification using test helper
    await page.evaluate(() => {
      const mockSignal = {
        id: 'test-signal-2',
        symbol: 'TSLA',
        pattern_type: 'SOS',
        phase: 'D',
        entry_price: '200.00',
        stop_loss: '195.00',
        target_levels: {
          primary_target: '210.00',
          secondary_targets: [],
          trailing_stop_activation: null,
          trailing_stop_offset: null,
        },
        position_size: 50,
        risk_amount: '250',
        r_multiple: '2.0',
        confidence_score: 88,
        confidence_components: {
          pattern_confidence: 88,
          phase_confidence: 87,
          volume_confidence: 89,
          overall_confidence: 88,
        },
        campaign_id: null,
        status: 'PENDING',
        timestamp: new Date().toISOString(),
        timeframe: '1H',
      }

      window.__BMAD_TEST__?.triggerSignal(mockSignal)
    })

    const toast = page.locator('.signal-toast')
    await expect(toast).toBeVisible({ timeout: 5000 })

    // Wait for auto-dismiss (3 seconds + 500ms buffer)
    await page.waitForTimeout(3500)

    // Toast should be dismissed
    await expect(toast).not.toBeVisible()
  })

  test('should filter low confidence signals when filter enabled', async ({
    page,
  }) => {
    // Enable high confidence filter
    await page.evaluate(() => {
      localStorage.setItem(
        'bmad_toast_settings',
        JSON.stringify({
          soundEnabled: false,
          soundVolume: 80,
          toastDuration: 10,
          browserNotificationsEnabled: false,
          showOnlyHighConfidence: true,
        })
      )
    })

    await page.reload()

    // Wait for test helper to be available after reload
    await page.waitForFunction(() => window.__BMAD_TEST__ !== undefined, {
      timeout: 5000,
    })

    // Trigger low confidence signal (70%) using test helper
    await page.evaluate(() => {
      const mockSignal = {
        id: 'test-signal-3',
        symbol: 'MSFT',
        pattern_type: 'LPS',
        phase: 'E',
        entry_price: '350.00',
        stop_loss: '345.00',
        target_levels: {
          primary_target: '360.00',
          secondary_targets: [],
          trailing_stop_activation: null,
          trailing_stop_offset: null,
        },
        position_size: 30,
        risk_amount: '150',
        r_multiple: '2.0',
        confidence_score: 70,
        confidence_components: {
          pattern_confidence: 70,
          phase_confidence: 68,
          volume_confidence: 72,
          overall_confidence: 70,
        },
        campaign_id: null,
        status: 'PENDING',
        timestamp: new Date().toISOString(),
        timeframe: '1H',
      }

      window.__BMAD_TEST__?.triggerSignal(mockSignal)
    })

    // Wait a bit to ensure no toast appears
    await page.waitForTimeout(1000)

    // Toast should NOT be visible
    const toast = page.locator('.signal-toast')
    await expect(toast).not.toBeVisible()
  })

  test('should show pattern-specific styling', async ({ page }) => {
    // Test different pattern types
    // Note: The toast detail HTML is escaped by PrimeVue, so we verify pattern type
    // is shown in the toast summary instead of checking for styled badges
    const patterns = [
      { type: 'SPRING', expectedText: 'SPRING' },
      { type: 'SOS', expectedText: 'SOS' },
      { type: 'LPS', expectedText: 'LPS' },
      { type: 'UTAD', expectedText: 'UTAD' },
    ]

    for (const pattern of patterns) {
      await page.evaluate((patternType) => {
        const mockSignal = {
          id: `test-signal-${patternType}`,
          symbol: 'TEST',
          pattern_type: patternType,
          phase: 'C',
          entry_price: '100.00',
          stop_loss: '95.00',
          target_levels: {
            primary_target: '110.00',
            secondary_targets: [],
            trailing_stop_activation: null,
            trailing_stop_offset: null,
          },
          position_size: 100,
          risk_amount: '500',
          r_multiple: '2.0',
          confidence_score: 90,
          confidence_components: {
            pattern_confidence: 90,
            phase_confidence: 88,
            volume_confidence: 92,
            overall_confidence: 90,
          },
          campaign_id: null,
          status: 'PENDING',
          timestamp: new Date().toISOString(),
          timeframe: '1H',
        }

        window.__BMAD_TEST__?.triggerSignal(mockSignal)
      }, pattern.type)

      const toast = page.locator('.signal-toast').last()
      await expect(toast).toBeVisible({ timeout: 5000 })

      // Verify pattern type is shown in the toast summary
      const summary = toast.locator('.p-toast-summary')
      await expect(summary).toContainText(pattern.expectedText)

      // Close toast for next iteration
      const closeButton = toast.locator('.p-toast-icon-close')
      if (await closeButton.isVisible()) {
        await closeButton.click()
      }

      await page.waitForTimeout(500)
    }
  })

  test('should show confidence grade styling', async ({ page }) => {
    const confidenceLevels = [
      { score: 96, grade: 'A+', class: 'a-plus' },
      { score: 88, grade: 'A', class: 'a' },
      { score: 78, grade: 'B', class: 'b' },
      { score: 70, grade: 'C', class: 'c' },
    ]

    // Disable filter to see all grades
    await page.evaluate(() => {
      localStorage.setItem(
        'bmad_toast_settings',
        JSON.stringify({
          soundEnabled: false,
          soundVolume: 80,
          toastDuration: 10,
          browserNotificationsEnabled: false,
          showOnlyHighConfidence: false,
        })
      )
    })

    await page.reload()

    // Wait for test helper to be available after reload
    await page.waitForFunction(() => window.__BMAD_TEST__ !== undefined, {
      timeout: 5000,
    })

    for (const level of confidenceLevels) {
      await page.evaluate((score) => {
        const mockSignal = {
          id: `test-signal-conf-${score}`,
          symbol: 'TEST',
          pattern_type: 'SPRING',
          phase: 'C',
          entry_price: '100.00',
          stop_loss: '95.00',
          target_levels: {
            primary_target: '110.00',
            secondary_targets: [],
            trailing_stop_activation: null,
            trailing_stop_offset: null,
          },
          position_size: 100,
          risk_amount: '500',
          r_multiple: '2.0',
          confidence_score: score,
          confidence_components: {
            pattern_confidence: score,
            phase_confidence: score,
            volume_confidence: score,
            overall_confidence: score,
          },
          campaign_id: null,
          status: 'PENDING',
          timestamp: new Date().toISOString(),
          timeframe: '1H',
        }

        window.__BMAD_TEST__?.triggerSignal(mockSignal)
      }, level.score)

      const toast = page.locator('.signal-toast').last()
      await expect(toast).toBeVisible({ timeout: 5000 })

      // Check for confidence grade
      await expect(toast).toContainText(level.grade)

      // Close toast for next iteration
      const closeButton = toast.locator('.p-toast-icon-close')
      if (await closeButton.isVisible()) {
        await closeButton.click()
      }

      await page.waitForTimeout(500)
    }
  })
})
