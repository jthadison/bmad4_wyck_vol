/**
 * Signal Toast Notifications E2E Tests (Story 19.8)
 *
 * End-to-end tests for signal toast notifications, audio alerts,
 * and browser notifications.
 */

import { test, expect } from '@playwright/test'

test.describe('Signal Toast Notifications', () => {
  test.beforeEach(async ({ page, context }) => {
    // Grant notification permissions
    await context.grantPermissions(['notifications'])

    // Navigate to dashboard
    await page.goto('http://localhost:5173')

    // Wait for WebSocket connection
    await page.waitForTimeout(1000)
  })

  test('should display toast notification when signal arrives', async ({
    page,
  }) => {
    // Simulate WebSocket message (in real scenario, backend sends this)
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

      const message = {
        type: 'signal:new',
        sequence_number: 1,
        data: mockSignal,
        timestamp: new Date().toISOString(),
      }

      // Trigger signal notification manually
      ;(window as Window & typeof globalThis).dispatchEvent(
        new CustomEvent('test:signal', { detail: message })
      )
    })

    // Wait for toast to appear
    const toast = page.locator('.signal-toast')
    await expect(toast).toBeVisible({ timeout: 1000 })

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

    // Trigger signal notification
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

      const message = {
        type: 'signal:new',
        sequence_number: 2,
        data: mockSignal,
        timestamp: new Date().toISOString(),
      }

      ;(window as Window & typeof globalThis).dispatchEvent(
        new CustomEvent('test:signal', { detail: message })
      )
    })

    const toast = page.locator('.signal-toast')
    await expect(toast).toBeVisible()

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

    // Trigger low confidence signal (70%)
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

      const message = {
        type: 'signal:new',
        sequence_number: 3,
        data: mockSignal,
        timestamp: new Date().toISOString(),
      }

      ;(window as Window & typeof globalThis).dispatchEvent(
        new CustomEvent('test:signal', { detail: message })
      )
    })

    // Wait a bit to ensure no toast appears
    await page.waitForTimeout(1000)

    // Toast should NOT be visible
    const toast = page.locator('.signal-toast')
    await expect(toast).not.toBeVisible()
  })

  test('should show pattern-specific styling', async ({ page }) => {
    // Test different pattern types
    const patterns = [
      { type: 'SPRING', class: 'spring' },
      { type: 'SOS', class: 'sos' },
      { type: 'LPS', class: 'lps' },
      { type: 'UTAD', class: 'utad' },
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

        const message = {
          type: 'signal:new',
          sequence_number: Math.random(),
          data: mockSignal,
          timestamp: new Date().toISOString(),
        }

        ;(window as Window & typeof globalThis).dispatchEvent(
          new CustomEvent('test:signal', { detail: message })
        )
      }, pattern.type)

      const toast = page.locator('.signal-toast').last()
      await expect(toast).toBeVisible()

      // Check for pattern-specific class
      const badge = toast.locator(`.pattern-badge.${pattern.class}`)
      await expect(badge).toBeVisible()

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

        const message = {
          type: 'signal:new',
          sequence_number: Math.random(),
          data: mockSignal,
          timestamp: new Date().toISOString(),
        }

        ;(window as Window & typeof globalThis).dispatchEvent(
          new CustomEvent('test:signal', { detail: message })
        )
      }, level.score)

      const toast = page.locator('.signal-toast').last()
      await expect(toast).toBeVisible()

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
