/**
 * Toast Settings Store Unit Tests (Story 19.8)
 *
 * Tests for toast settings store actions and localStorage persistence.
 */

import { describe, it, expect, beforeEach, vi, afterEach } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { useToastSettingsStore } from '../toastSettingsStore'

describe('useToastSettingsStore', () => {
  let localStorageMock: { [key: string]: string }

  beforeEach(() => {
    setActivePinia(createPinia())

    // Mock localStorage
    localStorageMock = {}
    global.localStorage = {
      getItem: vi.fn((key: string) => localStorageMock[key] || null),
      setItem: vi.fn((key: string, value: string) => {
        localStorageMock[key] = value
      }),
      removeItem: vi.fn((key: string) => {
        delete localStorageMock[key]
      }),
      clear: vi.fn(() => {
        localStorageMock = {}
      }),
      key: vi.fn(),
      length: 0,
    }
  })

  afterEach(() => {
    vi.clearAllMocks()
  })

  describe('initialization', () => {
    it('should load default settings on initialization', () => {
      const store = useToastSettingsStore()

      expect(store.settings.soundEnabled).toBe(true)
      expect(store.settings.soundVolume).toBe(80)
      expect(store.settings.toastDuration).toBe(10)
      expect(store.settings.browserNotificationsEnabled).toBe(false)
      expect(store.settings.showOnlyHighConfidence).toBe(false)
    })

    it('should load settings from localStorage if available', () => {
      const savedSettings = {
        soundEnabled: false,
        soundVolume: 50,
        toastDuration: 15,
        browserNotificationsEnabled: true,
        showOnlyHighConfidence: true,
      }

      localStorageMock['bmad_toast_settings'] = JSON.stringify(savedSettings)

      const store = useToastSettingsStore()

      expect(store.settings.soundEnabled).toBe(false)
      expect(store.settings.soundVolume).toBe(50)
      expect(store.settings.toastDuration).toBe(15)
      expect(store.settings.browserNotificationsEnabled).toBe(true)
      expect(store.settings.showOnlyHighConfidence).toBe(true)
    })

    it('should use defaults if localStorage contains invalid JSON', () => {
      localStorageMock['bmad_toast_settings'] = 'invalid json'

      const store = useToastSettingsStore()

      expect(store.settings.soundEnabled).toBe(true)
      expect(store.settings.soundVolume).toBe(80)
    })
  })

  describe('saveSettings', () => {
    it('should save partial settings updates', () => {
      const store = useToastSettingsStore()

      store.saveSettings({ soundEnabled: false })

      expect(store.settings.soundEnabled).toBe(false)
      expect(store.settings.soundVolume).toBe(80) // Other settings unchanged
      expect(localStorage.setItem).toHaveBeenCalledWith(
        'bmad_toast_settings',
        JSON.stringify(store.settings)
      )
    })

    it('should save all settings to localStorage', () => {
      const store = useToastSettingsStore()

      const newSettings = {
        soundEnabled: false,
        soundVolume: 60,
        toastDuration: 5,
        browserNotificationsEnabled: true,
        showOnlyHighConfidence: true,
      }

      store.saveSettings(newSettings)

      expect(store.settings).toEqual(newSettings)
      expect(localStorage.setItem).toHaveBeenCalledWith(
        'bmad_toast_settings',
        JSON.stringify(newSettings)
      )
    })
  })

  describe('updateSoundEnabled', () => {
    it('should update sound enabled setting', () => {
      const store = useToastSettingsStore()

      store.updateSoundEnabled(false)

      expect(store.settings.soundEnabled).toBe(false)
      expect(localStorage.setItem).toHaveBeenCalled()
    })
  })

  describe('updateSoundVolume', () => {
    it('should update sound volume', () => {
      const store = useToastSettingsStore()

      store.updateSoundVolume(50)

      expect(store.settings.soundVolume).toBe(50)
    })

    it('should clamp volume to 0-100 range', () => {
      const store = useToastSettingsStore()

      store.updateSoundVolume(150)
      expect(store.settings.soundVolume).toBe(100)

      store.updateSoundVolume(-10)
      expect(store.settings.soundVolume).toBe(0)
    })
  })

  describe('updateToastDuration', () => {
    it('should update toast duration', () => {
      const store = useToastSettingsStore()

      store.updateToastDuration(20)

      expect(store.settings.toastDuration).toBe(20)
    })

    it('should clamp duration to 3-30 second range', () => {
      const store = useToastSettingsStore()

      store.updateToastDuration(60)
      expect(store.settings.toastDuration).toBe(30)

      store.updateToastDuration(1)
      expect(store.settings.toastDuration).toBe(3)
    })
  })

  describe('updateBrowserNotifications', () => {
    it('should update browser notifications setting', () => {
      const store = useToastSettingsStore()

      store.updateBrowserNotifications(true)

      expect(store.settings.browserNotificationsEnabled).toBe(true)
    })
  })

  describe('updateHighConfidenceOnly', () => {
    it('should update high confidence filter setting', () => {
      const store = useToastSettingsStore()

      store.updateHighConfidenceOnly(true)

      expect(store.settings.showOnlyHighConfidence).toBe(true)
    })
  })

  describe('resetToDefaults', () => {
    it('should reset all settings to defaults', () => {
      const store = useToastSettingsStore()

      // Change some settings
      store.saveSettings({
        soundEnabled: false,
        soundVolume: 20,
        toastDuration: 5,
        browserNotificationsEnabled: true,
        showOnlyHighConfidence: true,
      })

      // Reset
      store.resetToDefaults()

      expect(store.settings.soundEnabled).toBe(true)
      expect(store.settings.soundVolume).toBe(80)
      expect(store.settings.toastDuration).toBe(10)
      expect(store.settings.browserNotificationsEnabled).toBe(false)
      expect(store.settings.showOnlyHighConfidence).toBe(false)
      expect(localStorage.removeItem).toHaveBeenCalledWith(
        'bmad_toast_settings'
      )
    })
  })

  describe('requestBrowserPermission', () => {
    it('should return true if permission already granted', async () => {
      global.Notification = {
        permission: 'granted',
        requestPermission: vi.fn(),
      } as unknown as typeof Notification

      const store = useToastSettingsStore()
      const result = await store.requestBrowserPermission()

      expect(result).toBe(true)
      expect(Notification.requestPermission).not.toHaveBeenCalled()
    })

    it('should return false if permission denied', async () => {
      global.Notification = {
        permission: 'denied',
        requestPermission: vi.fn(),
      } as unknown as typeof Notification

      const store = useToastSettingsStore()
      const result = await store.requestBrowserPermission()

      expect(result).toBe(false)
    })

    it('should request permission and return result', async () => {
      global.Notification = {
        permission: 'default',
        requestPermission: vi.fn().mockResolvedValue('granted'),
      } as unknown as typeof Notification

      const store = useToastSettingsStore()
      const result = await store.requestBrowserPermission()

      expect(result).toBe(true)
      expect(Notification.requestPermission).toHaveBeenCalled()
      expect(store.settings.browserNotificationsEnabled).toBe(true)
    })

    it('should return false if Notification API not supported', async () => {
      const originalNotification = global.Notification
      // @ts-expect-error - intentionally setting to undefined
      global.Notification = undefined

      const store = useToastSettingsStore()
      const result = await store.requestBrowserPermission()

      expect(result).toBe(false)

      global.Notification = originalNotification
    })
  })
})
