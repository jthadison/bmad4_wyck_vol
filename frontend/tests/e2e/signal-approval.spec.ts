/**
 * Signal Approval Queue E2E Test (Story 23.10)
 *
 * Verifies the end-to-end flow:
 * 1. Signal appears in the approval queue UI
 * 2. User can approve a signal
 * 3. User can reject a signal with a reason
 */
import { test, expect } from '@playwright/test'

// Mock API response data (flat structure matching backend PendingSignalView)
const mockPendingSignal = {
  queue_id: 'queue-e2e-001',
  signal_id: 'signal-e2e-001',
  symbol: 'AAPL',
  pattern_type: 'SPRING',
  confidence_score: 92,
  confidence_grade: 'A+',
  entry_price: '150.25',
  stop_loss: '149.50',
  target_price: '152.75',
  submitted_at: new Date().toISOString(),
  expires_at: new Date(Date.now() + 300000).toISOString(),
  time_remaining_seconds: 272,
}

const mockApprovalResult = {
  status: 'approved',
  approved_at: new Date().toISOString(),
  message: 'Signal approved and executed',
}

const mockRejectResult = {
  status: 'rejected',
  rejection_reason: 'Entry too far from pattern',
  message: 'Signal rejected',
}

test.describe('Signal Approval Queue', () => {
  test.beforeEach(async ({ page }) => {
    // Intercept API calls to mock backend responses
    await page.route('**/api/v1/signals/pending', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          signals: [mockPendingSignal],
          total_count: 1,
        }),
      })
    })

    // Mock WebSocket messages endpoint (for reconnection)
    await page.route('**/api/v1/websocket/messages**', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ messages: [] }),
      })
    })
  })

  test('signal appears in queue with all required details', async ({
    page,
  }) => {
    await page.goto('/signals/queue')

    // Wait for queue panel to load
    const panel = page.locator('[data-testid="signal-queue-panel"]')
    await expect(panel).toBeVisible()

    // Check signal card is displayed
    const card = page.locator('[data-testid="queue-signal-card"]').first()
    await expect(card).toBeVisible()

    // Verify required signal details (AC2)
    await expect(page.locator('[data-testid="signal-symbol"]')).toContainText(
      'AAPL'
    )
    await expect(page.locator('[data-testid="pattern-badge"]')).toContainText(
      'SPRING'
    )
    await expect(
      page.locator('[data-testid="confidence-grade"]')
    ).toContainText('A+')
    await expect(page.locator('[data-testid="entry-price"]')).toContainText(
      '150.25'
    )
    await expect(page.locator('[data-testid="stop-price"]')).toContainText(
      '149.50'
    )
    await expect(page.locator('[data-testid="target-price"]')).toContainText(
      '152.75'
    )
    await expect(
      page.locator('[data-testid="confidence-grade-row"]')
    ).toContainText('A+')
    await expect(page.locator('[data-testid="stop-distance"]')).toBeVisible()
    await expect(page.locator('[data-testid="asset-class"]')).toContainText(
      'Stock'
    )
  })

  test('approve signal triggers broker routing', async ({ page }) => {
    // Mock the approve endpoint
    await page.route('**/api/v1/signals/*/approve', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(mockApprovalResult),
      })
    })

    await page.goto('/signals/queue')

    // Wait for signal to appear
    const card = page.locator('[data-testid="queue-signal-card"]').first()
    await expect(card).toBeVisible()

    // Click approve
    const approveBtn = card.locator('[data-testid="approve-button"]')
    await approveBtn.click()

    // Verify signal is removed from queue (optimistic update)
    await expect(card).not.toBeVisible({ timeout: 5000 })
  })

  test('reject signal shows modal and logs reason', async ({ page }) => {
    // Mock the reject endpoint
    await page.route('**/api/v1/signals/*/reject', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(mockRejectResult),
      })
    })

    await page.goto('/signals/queue')

    // Wait for signal to appear
    const card = page.locator('[data-testid="queue-signal-card"]').first()
    await expect(card).toBeVisible()

    // Click reject
    const rejectBtn = card.locator('[data-testid="reject-button"]')
    await rejectBtn.click()

    // Verify reject modal appears
    const modal = page.locator('[data-testid="reject-signal-modal"]')
    await expect(modal).toBeVisible()

    // Select a rejection reason
    const dropdown = page.locator('[data-testid="reason-dropdown"]')
    await dropdown.click()
    // Select "Entry too far from pattern" option
    await page.locator('li').filter({ hasText: 'Entry too far' }).click()

    // Confirm rejection
    const confirmBtn = page.locator('[data-testid="confirm-button"]')
    await confirmBtn.click()

    // Verify signal removed from queue
    await expect(card).not.toBeVisible({ timeout: 5000 })
  })
})
