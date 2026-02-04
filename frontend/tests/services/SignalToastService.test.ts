/**
 * Signal Toast Service Unit Tests (Story 19.8)
 *
 * Tests for signal toast notifications, audio alerts, and browser notifications.
 */

import { describe, it, expect, beforeEach, vi, afterEach } from 'vitest'
import { SignalToastService } from '@/services/SignalToastService'
import type { Signal } from '@/types'
import { setActivePinia, createPinia } from 'pinia'

// Mock the router
vi.mock('@/router', () => ({
  default: {
    push: vi.fn(),
  },
}))

describe('SignalToastService', () => {
  let service: SignalToastService
  let mockToastService: { add: ReturnType<typeof vi.fn> }
  let mockAudioElement: {
    play: ReturnType<typeof vi.fn>
    volume: number
    currentTime: number
    addEventListener: ReturnType<typeof vi.fn>
    removeEventListener: ReturnType<typeof vi.fn>
  }

  const createMockSignal = (confidenceScore: number): Signal => ({
    id: 'signal-123',
    symbol: 'AAPL',
    pattern_type: 'SPRING',
    phase: 'C',
    entry_price: '150.25',
    stop_loss: '148.00',
    target_levels: {
      primary_target: '155.00',
      secondary_targets: ['157.00', '160.00'],
      trailing_stop_activation: null,
      trailing_stop_offset: null,
    },
    position_size: 100,
    risk_amount: '225',
    r_multiple: '2.1',
    confidence_score: confidenceScore,
    confidence_components: {
      pattern_confidence: 90,
      phase_confidence: 85,
      volume_confidence: 90,
      overall_confidence: confidenceScore,
    },
    campaign_id: null,
    status: 'PENDING',
    timestamp: '2024-03-13T10:00:00Z',
    timeframe: '1H',
  })

  beforeEach(() => {
    setActivePinia(createPinia())

    // Mock toast service
    mockToastService = {
      add: vi.fn(),
    }

    // Mock audio element with all required methods
    mockAudioElement = {
      play: vi.fn().mockResolvedValue(undefined),
      volume: 0.8,
      currentTime: 0,
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
    }

    // Mock Audio constructor using vi.stubGlobal for proper browser API mocking
    vi.stubGlobal(
      'Audio',
      vi.fn(() => mockAudioElement)
    )

    // Mock document.hasFocus
    vi.stubGlobal('document', {
      ...document,
      hasFocus: vi.fn(() => true),
    })

    // Mock Notification API
    vi.stubGlobal('Notification', {
      permission: 'default',
      requestPermission: vi.fn(),
    })

    service = new SignalToastService()
  })

  afterEach(() => {
    vi.clearAllMocks()
    vi.unstubAllGlobals()
  })

  describe('setToastService', () => {
    it('should set the toast service instance', async () => {
      service.setToastService(mockToastService)

      // Verify by attempting to show a toast
      const signal = createMockSignal(90)
      await service.handleSignalNotification(signal)

      expect(mockToastService.add).toHaveBeenCalled()
    })
  })

  describe('handleSignalNotification', () => {
    beforeEach(() => {
      service.setToastService(mockToastService)
    })

    it('should show toast for high confidence signal', async () => {
      const signal = createMockSignal(95)

      await service.handleSignalNotification(signal)

      expect(mockToastService.add).toHaveBeenCalledWith(
        expect.objectContaining({
          severity: 'info',
          summary: 'SPRING: AAPL',
          closable: true,
          styleClass: 'signal-toast',
        })
      )
    })

    it('should filter low confidence signals when showOnlyHighConfidence is enabled', async () => {
      const { useToastSettingsStore } = await import(
        '@/stores/toastSettingsStore'
      )
      const settingsStore = useToastSettingsStore()
      settingsStore.updateHighConfidenceOnly(true)

      const lowConfidenceSignal = createMockSignal(70)

      await service.handleSignalNotification(lowConfidenceSignal)

      expect(mockToastService.add).not.toHaveBeenCalled()
    })

    it('should show low confidence signals when filter is disabled', async () => {
      const { useToastSettingsStore } = await import(
        '@/stores/toastSettingsStore'
      )
      const settingsStore = useToastSettingsStore()
      settingsStore.updateHighConfidenceOnly(false)

      const lowConfidenceSignal = createMockSignal(70)

      await service.handleSignalNotification(lowConfidenceSignal)

      expect(mockToastService.add).toHaveBeenCalled()
    })

    it('should play audio alert when sound is enabled', async () => {
      const { useToastSettingsStore } = await import(
        '@/stores/toastSettingsStore'
      )
      const settingsStore = useToastSettingsStore()
      settingsStore.updateSoundEnabled(true)

      const signal = createMockSignal(90)

      await service.handleSignalNotification(signal)

      expect(mockAudioElement.play).toHaveBeenCalled()
    })

    it('should not play audio alert when sound is disabled', async () => {
      const { useToastSettingsStore } = await import(
        '@/stores/toastSettingsStore'
      )
      const settingsStore = useToastSettingsStore()
      settingsStore.updateSoundEnabled(false)

      const signal = createMockSignal(90)

      await service.handleSignalNotification(signal)

      expect(mockAudioElement.play).not.toHaveBeenCalled()
    })

    it('should respect volume setting when playing audio', async () => {
      const { useToastSettingsStore } = await import(
        '@/stores/toastSettingsStore'
      )
      const settingsStore = useToastSettingsStore()
      settingsStore.updateSoundEnabled(true)
      settingsStore.updateSoundVolume(50)

      const signal = createMockSignal(90)

      await service.handleSignalNotification(signal)

      expect(mockAudioElement.play).toHaveBeenCalled()
      expect(mockAudioElement.volume).toBe(0.5) // 50% = 0.5
    })
  })

  describe('confidence grade calculation', () => {
    beforeEach(() => {
      service.setToastService(mockToastService)
    })

    it('should assign A+ grade for confidence >= 95', async () => {
      const signal = createMockSignal(96)

      await service.handleSignalNotification(signal)

      const callArg = mockToastService.add.mock.calls[0][0]
      expect(callArg.detail).toContain('A+')
      expect(callArg.detail).toContain('a-plus')
    })

    it('should assign A grade for confidence >= 85', async () => {
      const signal = createMockSignal(88)

      await service.handleSignalNotification(signal)

      const callArg = mockToastService.add.mock.calls[0][0]
      expect(callArg.detail).toContain('>A<')
    })

    it('should assign B grade for confidence >= 75', async () => {
      const signal = createMockSignal(78)

      await service.handleSignalNotification(signal)

      const callArg = mockToastService.add.mock.calls[0][0]
      expect(callArg.detail).toContain('>B<')
    })

    it('should assign C grade for confidence < 75', async () => {
      const signal = createMockSignal(70)

      await service.handleSignalNotification(signal)

      const callArg = mockToastService.add.mock.calls[0][0]
      expect(callArg.detail).toContain('>C<')
    })
  })

  describe('toast content', () => {
    beforeEach(() => {
      service.setToastService(mockToastService)
    })

    it('should include signal data in toast content', async () => {
      const signal = createMockSignal(90)

      await service.handleSignalNotification(signal)

      const callArg = mockToastService.add.mock.calls[0][0]
      const detail = callArg.detail

      expect(detail).toContain('SPRING')
      expect(detail).toContain('150.25') // entry price
      expect(detail).toContain('2.1') // r_multiple
      expect(detail).toContain('signal-123') // signal id in data attribute
    })

    it('should use correct pattern badge class', async () => {
      const signal = createMockSignal(90)

      await service.handleSignalNotification(signal)

      const callArg = mockToastService.add.mock.calls[0][0]
      expect(callArg.detail).toContain('pattern-badge spring')
    })
  })

  describe('browser notifications', () => {
    beforeEach(() => {
      service.setToastService(mockToastService)
    })

    it('should not show browser notification when tab is focused', async () => {
      const { useToastSettingsStore } = await import(
        '@/stores/toastSettingsStore'
      )
      const settingsStore = useToastSettingsStore()
      settingsStore.updateBrowserNotifications(true)

      const mockNotificationConstructor = vi.fn()
      mockNotificationConstructor.permission = 'granted'
      vi.stubGlobal('Notification', mockNotificationConstructor)

      vi.stubGlobal('document', {
        ...document,
        hasFocus: vi.fn(() => true),
      })

      const signal = createMockSignal(90)

      await service.handleSignalNotification(signal)

      expect(mockNotificationConstructor).not.toHaveBeenCalled()
    })

    it('should show browser notification when tab is not focused', async () => {
      const { useToastSettingsStore } = await import(
        '@/stores/toastSettingsStore'
      )
      const settingsStore = useToastSettingsStore()
      settingsStore.updateBrowserNotifications(true)

      vi.stubGlobal('document', {
        ...document,
        hasFocus: vi.fn(() => false),
      })

      const mockNotificationInstance = {
        onclick: null,
        close: vi.fn(),
      }
      const mockNotificationConstructor = vi.fn(() => mockNotificationInstance)
      mockNotificationConstructor.permission = 'granted'
      vi.stubGlobal('Notification', mockNotificationConstructor)

      const signal = createMockSignal(90)

      await service.handleSignalNotification(signal)

      expect(mockNotificationConstructor).toHaveBeenCalledWith(
        'New SPRING: AAPL',
        expect.objectContaining({
          body: expect.stringContaining('150.25'),
          tag: 'signal-123',
          requireInteraction: true,
        })
      )
    })

    it('should not show browser notification when permission not granted', async () => {
      const { useToastSettingsStore } = await import(
        '@/stores/toastSettingsStore'
      )
      const settingsStore = useToastSettingsStore()
      settingsStore.updateBrowserNotifications(true)

      vi.stubGlobal('document', {
        ...document,
        hasFocus: vi.fn(() => false),
      })

      const mockNotificationConstructor = vi.fn()
      mockNotificationConstructor.permission = 'default'
      vi.stubGlobal('Notification', mockNotificationConstructor)

      const signal = createMockSignal(90)

      await service.handleSignalNotification(signal)

      expect(mockNotificationConstructor).not.toHaveBeenCalled()
    })
  })

  describe('toast lifecycle', () => {
    beforeEach(() => {
      service.setToastService(mockToastService)
    })

    it('should use configured toast duration', async () => {
      const { useToastSettingsStore } = await import(
        '@/stores/toastSettingsStore'
      )
      const settingsStore = useToastSettingsStore()
      settingsStore.updateToastDuration(15)

      const signal = createMockSignal(90)

      await service.handleSignalNotification(signal)

      const callArg = mockToastService.add.mock.calls[0][0]
      expect(callArg.life).toBe(15000) // 15 seconds in ms
    })
  })
})
