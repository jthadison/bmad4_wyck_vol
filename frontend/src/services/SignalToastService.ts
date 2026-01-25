/**
 * Signal Toast Service
 *
 * Manages toast notifications, audio alerts, and browser notifications for trading signals.
 * Integrates with PrimeVue Toast, HTML5 Audio API, and Browser Notification API.
 *
 * Story: 19.8 - Frontend Signal Toast Notifications
 */

import type { ToastServiceMethods } from 'primevue/toastservice'
import type { Signal } from '@/types'
import { useToastSettingsStore } from '@/stores/toastSettingsStore'
import router from '@/router'

export interface SignalToastData {
  signal: Signal
  timestamp: string
}

export class SignalToastService {
  private toastService: ToastServiceMethods | null = null
  private audioElement: HTMLAudioElement | null = null
  private settingsStore = useToastSettingsStore()

  constructor() {
    this.initializeAudio()
  }

  /**
   * Initialize the toast service with PrimeVue instance
   */
  setToastService(service: ToastServiceMethods): void {
    this.toastService = service
  }

  /**
   * Initialize audio element for sound alerts
   */
  private initializeAudio(): void {
    try {
      this.audioElement = new Audio('/sounds/signal-alert.mp3')
      this.audioElement.volume = this.settingsStore.settings.soundVolume / 100
    } catch (error) {
      console.error('[SignalToastService] Failed to initialize audio:', error)
    }
  }

  /**
   * Handle incoming signal notification
   */
  async handleSignalNotification(signal: Signal): Promise<void> {
    // Check if we should show this signal based on confidence filter
    if (!this.shouldShowSignal(signal)) {
      return
    }

    // Play audio alert
    await this.playAudioAlert()

    // Show toast notification
    this.showToast(signal)

    // Show browser notification if tab not focused
    await this.showBrowserNotification(signal)
  }

  /**
   * Check if signal meets confidence threshold
   */
  private shouldShowSignal(signal: Signal): boolean {
    const { showOnlyHighConfidence } = this.settingsStore.settings

    if (!showOnlyHighConfidence) {
      return true
    }

    // A+ and A signals have confidence >= 85
    return signal.confidence_score >= 85
  }

  /**
   * Get confidence grade from score
   */
  private getConfidenceGrade(score: number): string {
    if (score >= 95) return 'A+'
    if (score >= 85) return 'A'
    if (score >= 75) return 'B'
    return 'C'
  }

  /**
   * Get CSS class for confidence grade
   */
  private getConfidenceClass(score: number): string {
    const grade = this.getConfidenceGrade(score)
    return grade.toLowerCase().replace('+', '-plus')
  }

  /**
   * Play audio alert
   */
  private async playAudioAlert(): Promise<void> {
    const { soundEnabled, soundVolume } = this.settingsStore.settings

    if (!soundEnabled || !this.audioElement) {
      return
    }

    try {
      this.audioElement.volume = soundVolume / 100
      this.audioElement.currentTime = 0
      await this.audioElement.play()
    } catch (error) {
      console.error('[SignalToastService] Failed to play audio:', error)
    }
  }

  /**
   * Show PrimeVue toast notification
   */
  private showToast(signal: Signal): void {
    if (!this.toastService) {
      console.error('[SignalToastService] Toast service not initialized')
      return
    }

    const confidenceGrade = this.getConfidenceGrade(signal.confidence_score)
    const { toastDuration } = this.settingsStore.settings

    // Create custom toast content as HTML
    const toastContent = this.buildToastContent(signal, confidenceGrade)

    this.toastService.add({
      severity: 'info',
      summary: `${signal.pattern_type}: ${signal.symbol}`,
      detail: toastContent,
      life: toastDuration * 1000,
      group: 'signal-notifications',
      closable: true,
      styleClass: 'signal-toast',
    })
  }

  /**
   * Build toast content HTML
   */
  private buildToastContent(signal: Signal, confidenceGrade: string): string {
    const confidenceClass = this.getConfidenceClass(signal.confidence_score)
    const patternClass = signal.pattern_type.toLowerCase()

    return `
      <div class="signal-toast-content" data-signal-id="${signal.id}">
        <div class="toast-header">
          <span class="pattern-badge ${patternClass}">${signal.pattern_type}</span>
          <span class="confidence ${confidenceClass}">${confidenceGrade}</span>
        </div>
        <div class="toast-body">
          <div class="price-row">
            <span>Entry: $${signal.entry_price}</span>
            <span>R: ${signal.r_multiple}x</span>
          </div>
        </div>
      </div>
    `
  }

  /**
   * Show browser notification if tab not focused
   */
  private async showBrowserNotification(signal: Signal): Promise<void> {
    const { browserNotificationsEnabled } = this.settingsStore.settings

    if (!browserNotificationsEnabled) {
      return
    }

    if (!('Notification' in window)) {
      return
    }

    if (Notification.permission !== 'granted') {
      return
    }

    // Only show browser notification if tab is not focused
    if (document.hasFocus()) {
      return
    }

    try {
      const confidenceGrade = this.getConfidenceGrade(signal.confidence_score)
      const notification = new Notification(
        `New ${signal.pattern_type}: ${signal.symbol}`,
        {
          body: `Entry: $${signal.entry_price} | Confidence: ${confidenceGrade}`,
          icon: '/icons/signal-icon.png',
          tag: signal.id, // Prevent duplicates
          requireInteraction: true,
        }
      )

      notification.onclick = () => {
        window.focus()
        router.push(`/signals/${signal.id}`)
        notification.close()
      }
    } catch (error) {
      console.error(
        '[SignalToastService] Failed to show browser notification:',
        error
      )
    }
  }

  /**
   * Navigate to signal details
   */
  navigateToSignal(signalId: string): void {
    router.push(`/signals/${signalId}`)
  }
}

// Export singleton instance
export const signalToastService = new SignalToastService()
