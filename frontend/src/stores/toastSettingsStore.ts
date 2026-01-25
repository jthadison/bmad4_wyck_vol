/**
 * Toast Settings Store
 *
 * Pinia store for managing signal toast notification preferences.
 * Handles sound alerts, browser notifications, and toast display settings.
 *
 * Story: 19.8 - Frontend Signal Toast Notifications
 */

import { defineStore } from 'pinia'
import { ref } from 'vue'

export interface ToastSettings {
  soundEnabled: boolean
  soundVolume: number // 0-100
  toastDuration: number // seconds
  browserNotificationsEnabled: boolean
  showOnlyHighConfidence: boolean // A+ and A only (confidence >= 85)
}

const DEFAULT_SETTINGS: ToastSettings = {
  soundEnabled: true,
  soundVolume: 80,
  toastDuration: 10,
  browserNotificationsEnabled: false,
  showOnlyHighConfidence: false,
}

const STORAGE_KEY = 'bmad_toast_settings'

export const useToastSettingsStore = defineStore('toastSettings', () => {
  // State
  const settings = ref<ToastSettings>({ ...DEFAULT_SETTINGS })

  // Actions
  function loadSettings(): void {
    // Guard for SSR/test environments where localStorage may not be available
    if (typeof window === 'undefined' || typeof localStorage === 'undefined') {
      settings.value = { ...DEFAULT_SETTINGS }
      return
    }

    try {
      const stored = localStorage.getItem(STORAGE_KEY)
      if (stored) {
        const parsed = JSON.parse(stored) as ToastSettings
        settings.value = { ...DEFAULT_SETTINGS, ...parsed }
      }
    } catch (error) {
      console.error('[ToastSettings] Failed to load settings:', error)
      settings.value = { ...DEFAULT_SETTINGS }
    }
  }

  function saveSettings(newSettings: Partial<ToastSettings>): void {
    settings.value = { ...settings.value, ...newSettings }

    // Guard for SSR/test environments
    if (typeof window === 'undefined' || typeof localStorage === 'undefined') {
      return
    }

    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(settings.value))
    } catch (error) {
      console.error('[ToastSettings] Failed to save settings:', error)
    }
  }

  function updateSoundEnabled(enabled: boolean): void {
    saveSettings({ soundEnabled: enabled })
  }

  function updateSoundVolume(volume: number): void {
    const clampedVolume = Math.max(0, Math.min(100, volume))
    saveSettings({ soundVolume: clampedVolume })
  }

  function updateToastDuration(duration: number): void {
    const clampedDuration = Math.max(3, Math.min(30, duration))
    saveSettings({ toastDuration: clampedDuration })
  }

  function updateBrowserNotifications(enabled: boolean): void {
    saveSettings({ browserNotificationsEnabled: enabled })
  }

  function updateHighConfidenceOnly(enabled: boolean): void {
    saveSettings({ showOnlyHighConfidence: enabled })
  }

  function resetToDefaults(): void {
    settings.value = { ...DEFAULT_SETTINGS }

    // Guard for SSR/test environments
    if (typeof window === 'undefined' || typeof localStorage === 'undefined') {
      return
    }

    try {
      localStorage.removeItem(STORAGE_KEY)
    } catch (error) {
      console.error('[ToastSettings] Failed to reset settings:', error)
    }
  }

  async function requestBrowserPermission(): Promise<boolean> {
    if (!('Notification' in window)) {
      console.warn('[ToastSettings] Browser notifications not supported')
      return false
    }

    if (Notification.permission === 'granted') {
      return true
    }

    if (Notification.permission === 'denied') {
      console.warn('[ToastSettings] Browser notification permission denied')
      return false
    }

    try {
      const permission = await Notification.requestPermission()
      const granted = permission === 'granted'
      if (granted) {
        updateBrowserNotifications(true)
      }
      return granted
    } catch (error) {
      console.error(
        '[ToastSettings] Failed to request notification permission:',
        error
      )
      return false
    }
  }

  // Initialize on store creation
  loadSettings()

  return {
    // State
    settings,

    // Actions
    loadSettings,
    saveSettings,
    updateSoundEnabled,
    updateSoundVolume,
    updateToastDuration,
    updateBrowserNotifications,
    updateHighConfidenceOnly,
    resetToDefaults,
    requestBrowserPermission,
  }
})
