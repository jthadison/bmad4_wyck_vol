/**
 * Notification Service (Story 10.9)
 *
 * Purpose:
 * --------
 * Manages toast notifications for WebSocket events.
 * Uses PrimeVue Toast component for non-intrusive notifications.
 *
 * Features:
 * ---------
 * - Auto-dismiss after 5 seconds
 * - Severity levels: info, success, warn, error
 * - Throttling: max 3 toasts per 10 seconds
 * - "View Details" button with navigation
 * - User preference for enable/disable (localStorage)
 *
 * Toast Types:
 * ------------
 * - signal:new: "New signal: SPRING on AAPL" (info)
 * - signal:executed: "Signal executed: AAPL" (success)
 * - portfolio:updated (>80% heat): "Portfolio heat at 82%" (warn)
 * - campaign:updated (>80% allocated): "Campaign C-123 at 85%" (warn)
 *
 * Integration:
 * ------------
 * - PrimeVue Toast: App.vue must have <Toast /> component
 * - WebSocket events: Subscribe to events and show toasts
 * - Router: Navigate to detail pages on "View Details" click
 *
 * Author: Story 10.9
 */

import type { ToastServiceMethods } from 'primevue/toastservice'

class NotificationService {
  private toast: ToastServiceMethods | null = null
  private toastQueue: number[] = [] // Timestamps of recent toasts for throttling
  private readonly maxToastsPerWindow = 3
  private readonly throttleWindowMs = 10000 // 10 seconds
  private readonly toastLifeMs = 5000 // 5 seconds

  /**
   * Initialize notification service with PrimeVue Toast.
   * Must be called in App.vue setup after toast is available.
   */
  initialize(toastInstance: ToastServiceMethods): void {
    this.toast = toastInstance
  }

  /**
   * Check if notifications are enabled in user preferences.
   */
  private isEnabled(): boolean {
    const pref = localStorage.getItem('notifications_enabled')
    return pref === null || pref === 'true' // Enabled by default
  }

  /**
   * Enable toast notifications.
   */
  enable(): void {
    localStorage.setItem('notifications_enabled', 'true')
  }

  /**
   * Disable toast notifications.
   */
  disable(): void {
    localStorage.setItem('notifications_enabled', 'false')
  }

  /**
   * Check if we can show more toasts (throttle check).
   */
  private canShowToast(): boolean {
    if (!this.isEnabled()) return false

    const now = Date.now()

    // Remove old timestamps outside the throttle window
    this.toastQueue = this.toastQueue.filter(
      (t) => now - t < this.throttleWindowMs
    )

    // Check if under limit
    if (this.toastQueue.length >= this.maxToastsPerWindow) {
      console.log(
        '[NotificationService] Toast throttled - too many recent toasts'
      )
      return false
    }

    // Add current timestamp
    this.toastQueue.push(now)
    return true
  }

  /**
   * Show info toast for new signal.
   *
   * @param patternType - Pattern type (e.g., "SPRING")
   * @param symbol - Ticker symbol (e.g., "AAPL")
   * @param signalId - Signal UUID for navigation
   */
  showNewSignal(patternType: string, symbol: string, signalId: string): void {
    if (!this.canShowToast() || !this.toast) return

    this.toast.add({
      severity: 'info',
      summary: 'New Signal',
      detail: `${patternType} on ${symbol}`,
      life: this.toastLifeMs,
      data: { signalId, action: 'viewSignal' },
    })
  }

  /**
   * Show success toast for executed signal.
   *
   * @param symbol - Ticker symbol (e.g., "AAPL")
   * @param signalId - Signal UUID for navigation
   */
  showSignalExecuted(symbol: string, signalId: string): void {
    if (!this.canShowToast() || !this.toast) return

    this.toast.add({
      severity: 'success',
      summary: 'Signal Executed',
      detail: `Signal executed: ${symbol}`,
      life: this.toastLifeMs,
      data: { signalId, action: 'viewSignal' },
    })
  }

  /**
   * Show error toast for rejected signal.
   *
   * @param symbol - Ticker symbol (e.g., "AAPL")
   * @param reason - Rejection reason
   * @param signalId - Signal UUID for navigation
   */
  showSignalRejected(symbol: string, reason: string, signalId: string): void {
    if (!this.canShowToast() || !this.toast) return

    this.toast.add({
      severity: 'error',
      summary: 'Signal Rejected',
      detail: `${symbol}: ${reason}`,
      life: this.toastLifeMs,
      data: { signalId, action: 'viewSignal' },
    })
  }

  /**
   * Show warning toast for high portfolio heat.
   *
   * @param heatPercentage - Portfolio heat percentage
   */
  showPortfolioHeatWarning(heatPercentage: number): void {
    if (!this.canShowToast() || !this.toast) return

    // Only show if heat > 80%
    if (heatPercentage <= 80) return

    this.toast.add({
      severity: 'warn',
      summary: 'Portfolio Heat Warning',
      detail: `Portfolio heat at ${heatPercentage.toFixed(1)}%`,
      life: this.toastLifeMs,
      data: { action: 'viewRiskDashboard' },
    })
  }

  /**
   * Show warning toast for high campaign allocation.
   *
   * @param campaignId - Campaign UUID
   * @param riskPercentage - Campaign risk percentage
   */
  showCampaignHeatWarning(campaignId: string, riskPercentage: number): void {
    if (!this.canShowToast() || !this.toast) return

    // Only show if campaign risk > 80%
    if (riskPercentage <= 80) return

    this.toast.add({
      severity: 'warn',
      summary: 'Campaign Risk Warning',
      detail: `Campaign ${campaignId.slice(0, 8)} at ${riskPercentage.toFixed(
        1
      )}%`,
      life: this.toastLifeMs,
      data: { campaignId, action: 'viewCampaign' },
    })
  }

  /**
   * Show info toast for pattern detected.
   *
   * @param patternType - Pattern type (e.g., "SPRING")
   * @param symbol - Ticker symbol
   * @param patternId - Pattern UUID for navigation
   */
  showPatternDetected(
    patternType: string,
    symbol: string,
    patternId: string
  ): void {
    if (!this.canShowToast() || !this.toast) return

    this.toast.add({
      severity: 'info',
      summary: 'Pattern Detected',
      detail: `${patternType} detected on ${symbol}`,
      life: this.toastLifeMs,
      data: { patternId, action: 'viewPattern' },
    })
  }

  /**
   * Show generic info toast.
   */
  showInfo(summary: string, detail: string): void {
    if (!this.canShowToast() || !this.toast) return

    this.toast.add({
      severity: 'info',
      summary,
      detail,
      life: this.toastLifeMs,
    })
  }

  /**
   * Show generic success toast.
   */
  showSuccess(summary: string, detail: string): void {
    if (!this.canShowToast() || !this.toast) return

    this.toast.add({
      severity: 'success',
      summary,
      detail,
      life: this.toastLifeMs,
    })
  }

  /**
   * Show generic warning toast.
   */
  showWarning(summary: string, detail: string): void {
    if (!this.canShowToast() || !this.toast) return

    this.toast.add({
      severity: 'warn',
      summary,
      detail,
      life: this.toastLifeMs,
    })
  }

  /**
   * Show generic error toast.
   */
  showError(summary: string, detail: string): void {
    if (!this.canShowToast() || !this.toast) return

    this.toast.add({
      severity: 'error',
      summary,
      detail,
      life: this.toastLifeMs,
    })
  }

  /**
   * Clear all toasts.
   */
  clearAll(): void {
    if (this.toast) {
      this.toast.removeAllGroups()
    }
  }
}

// Singleton instance
export const notificationService = new NotificationService()

export default notificationService
