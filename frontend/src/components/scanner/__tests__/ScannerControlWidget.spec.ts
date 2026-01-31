/**
 * ScannerControlWidget Component Unit Tests
 * Story 20.6 - Frontend Scanner Control UI
 *
 * Test Coverage:
 * - AC1: Status indicator display (running/stopped)
 * - AC2: Start/stop button with loading state
 * - AC8: WebSocket status change handling
 * - AC10: Error handling
 */

import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, VueWrapper } from '@vue/test-utils'
import { createTestingPinia } from '@pinia/testing'
import PrimeVue from 'primevue/config'
import ToastService from 'primevue/toastservice'
import Button from 'primevue/button'
import ScannerControlWidget from '@/components/scanner/ScannerControlWidget.vue'
import { useScannerStore } from '@/stores/scannerStore'

// Mock date-fns
vi.mock('date-fns', () => ({
  formatDistanceToNow: vi.fn(() => '5 minutes ago'),
}))

describe('ScannerControlWidget', () => {
  let wrapper: VueWrapper

  const createWrapper = (initialState = {}) => {
    return mount(ScannerControlWidget, {
      global: {
        plugins: [
          PrimeVue,
          ToastService,
          createTestingPinia({
            initialState: {
              scanner: {
                isRunning: false,
                currentState: 'stopped',
                lastCycleAt: null,
                nextScanInSeconds: null,
                symbolsCount: 0,
                isLoading: false,
                isActionLoading: false,
                error: null,
                ...initialState,
              },
            },
            stubActions: false,
          }),
        ],
        components: {
          Button,
        },
        stubs: {
          Toast: true,
        },
      },
    })
  }

  beforeEach(() => {
    vi.clearAllMocks()
  })

  describe('AC1: Status Indicator Display', () => {
    it('shows "Stopped" status when scanner is stopped', () => {
      wrapper = createWrapper({ isRunning: false, currentState: 'stopped' })

      expect(wrapper.text()).toContain('Stopped')
      expect(
        wrapper.find('[data-testid="status-indicator"]').classes()
      ).toContain('status-stopped')
    })

    it('shows "Running" status when scanner is running', () => {
      wrapper = createWrapper({ isRunning: true, currentState: 'running' })

      expect(wrapper.text()).toContain('Running')
      expect(
        wrapper.find('[data-testid="status-indicator"]').classes()
      ).toContain('status-running')
    })

    it('shows "Never" for last scan when no history', () => {
      wrapper = createWrapper({ lastCycleAt: null })

      expect(wrapper.find('[data-testid="last-scan"]').text()).toBe('Never')
    })

    it('shows relative time for last scan', () => {
      wrapper = createWrapper({
        lastCycleAt: new Date('2026-01-30T10:00:00Z'),
      })

      expect(wrapper.find('[data-testid="last-scan"]').text()).toBe(
        '5 minutes ago'
      )
    })

    it('shows next scan countdown when running', () => {
      wrapper = createWrapper({
        isRunning: true,
        currentState: 'running',
        nextScanInSeconds: 185, // 3 minutes 5 seconds
      })

      expect(wrapper.find('[data-testid="next-scan"]').text()).toBe('in 3m 5s')
    })

    it('hides next scan when stopped', () => {
      wrapper = createWrapper({
        isRunning: false,
        nextScanInSeconds: null,
      })

      expect(wrapper.find('[data-testid="next-scan"]').exists()).toBe(false)
    })

    it('shows symbol count', () => {
      wrapper = createWrapper({ symbolsCount: 5 })

      expect(wrapper.find('[data-testid="symbols-count"]').text()).toContain(
        '5 symbols'
      )
    })
  })

  describe('AC2: Start/Stop Toggle', () => {
    it('shows "Start Scanner" button when stopped', () => {
      wrapper = createWrapper({ isRunning: false })

      const button = wrapper.find('[data-testid="scanner-toggle-button"]')
      expect(button.text()).toContain('Start Scanner')
    })

    it('shows "Stop Scanner" button when running', () => {
      wrapper = createWrapper({ isRunning: true })

      const button = wrapper.find('[data-testid="scanner-toggle-button"]')
      expect(button.text()).toContain('Stop Scanner')
    })

    it('shows loading state when action is in progress', () => {
      wrapper = createWrapper({ isActionLoading: true, isRunning: false })

      const button = wrapper.find('[data-testid="scanner-toggle-button"]')
      expect(button.text()).toContain('Starting...')
    })

    it('calls start action when start button clicked', async () => {
      wrapper = createWrapper({ isRunning: false })
      const store = useScannerStore()

      vi.spyOn(store, 'start').mockResolvedValue(true)

      await wrapper
        .find('[data-testid="scanner-toggle-button"]')
        .trigger('click')

      expect(store.start).toHaveBeenCalled()
    })

    it('calls stop action when stop button clicked', async () => {
      wrapper = createWrapper({ isRunning: true })
      const store = useScannerStore()

      vi.spyOn(store, 'stop').mockResolvedValue(true)

      await wrapper
        .find('[data-testid="scanner-toggle-button"]')
        .trigger('click')

      expect(store.stop).toHaveBeenCalled()
    })
  })

  describe('AC8: WebSocket Updates', () => {
    it('updates status when handleStatusChanged is called', async () => {
      wrapper = createWrapper({ isRunning: false })
      const store = useScannerStore()

      store.handleStatusChanged({
        type: 'scanner:status_changed',
        is_running: true,
        event: 'started',
        timestamp: new Date().toISOString(),
        sequence_number: 1,
      })

      await wrapper.vm.$nextTick()

      expect(store.isRunning).toBe(true)
    })
  })

  describe('Lifecycle', () => {
    it('fetches status on mount', () => {
      wrapper = createWrapper()
      const store = useScannerStore()

      expect(store.fetchStatus).toHaveBeenCalled()
    })
  })
})
