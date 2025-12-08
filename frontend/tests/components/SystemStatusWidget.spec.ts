import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import SystemStatusWidget from '@/components/SystemStatusWidget.vue'
import { useSystemStatusStore } from '@/stores/systemStatusStore'

// Mock useWebSocket composable
vi.mock('@/composables/useWebSocket', () => ({
  useWebSocket: vi.fn(() => ({
    isConnected: { value: true },
    connectionStatus: { value: 'connected' },
    subscribe: vi.fn(),
    unsubscribe: vi.fn(),
  })),
}))

// Mock API client for polling
vi.mock('@/services/api', () => ({
  apiClient: {
    get: vi.fn().mockResolvedValue({
      status: 'operational',
      bars_analyzed: 100,
      patterns_detected: 5,
      signals_executed: 2,
    }),
  },
}))

describe('SystemStatusWidget.vue', () => {
  let pinia: ReturnType<typeof createPinia>

  beforeEach(() => {
    pinia = createPinia()
    setActivePinia(pinia)
    vi.clearAllMocks()
    vi.clearAllTimers()
    vi.useFakeTimers()
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  describe('Rendering', () => {
    it('renders the widget with default state', () => {
      const wrapper = mount(SystemStatusWidget, {
        global: {
          plugins: [pinia],
        },
      })

      expect(wrapper.find('[aria-label="System Status Widget"]').exists()).toBe(
        true
      )
      expect(wrapper.text()).toContain('DISCONNECTED')
    })

    it('displays operational status with green indicator', async () => {
      const wrapper = mount(SystemStatusWidget, {
        global: {
          plugins: [pinia],
        },
      })

      const store = useSystemStatusStore()
      store.updateConnectionStatus('connected')
      store.updateSystemStatus('operational')

      await wrapper.vm.$nextTick()

      expect(wrapper.text()).toContain('OPERATIONAL')
      expect(wrapper.find('.pi-check-circle').exists()).toBe(true)
    })

    it('displays warning status with yellow indicator', async () => {
      const wrapper = mount(SystemStatusWidget, {
        global: {
          plugins: [pinia],
        },
      })

      const store = useSystemStatusStore()
      store.updateConnectionStatus('connected')
      store.updateSystemStatus('warning')

      await wrapper.vm.$nextTick()

      expect(wrapper.text()).toContain('WARNING')
      expect(wrapper.find('.pi-exclamation-triangle').exists()).toBe(true)
    })

    it('displays error status with red indicator', async () => {
      const wrapper = mount(SystemStatusWidget, {
        global: {
          plugins: [pinia],
        },
      })

      const store = useSystemStatusStore()
      store.updateConnectionStatus('connected')
      store.updateSystemStatus('error')

      await wrapper.vm.$nextTick()

      expect(wrapper.text()).toContain('ERROR')
      expect(wrapper.find('.pi-times-circle').exists()).toBe(true)
    })

    it('displays DISCONNECTED when WebSocket is offline', async () => {
      const wrapper = mount(SystemStatusWidget, {
        global: {
          plugins: [pinia],
        },
      })

      const store = useSystemStatusStore()
      store.updateConnectionStatus('disconnected')

      await wrapper.vm.$nextTick()

      expect(wrapper.text()).toContain('DISCONNECTED')
      expect(wrapper.find('.pi-wifi-slash').exists()).toBe(true)
    })
  })

  describe('Real-time Statistics', () => {
    it('displays bars analyzed count', async () => {
      const wrapper = mount(SystemStatusWidget, {
        global: {
          plugins: [pinia],
        },
      })

      const store = useSystemStatusStore()
      store.updateConnectionStatus('connected')
      store.updateStatistics({ barsAnalyzed: 12345 })

      await wrapper.vm.$nextTick()

      expect(wrapper.text()).toContain('12,345')
    })

    it('displays patterns detected count', async () => {
      const wrapper = mount(SystemStatusWidget, {
        global: {
          plugins: [pinia],
        },
      })

      const store = useSystemStatusStore()
      store.updateConnectionStatus('connected')
      store.updateStatistics({ patternsDetected: 42 })

      await wrapper.vm.$nextTick()

      expect(wrapper.text()).toContain('42')
    })

    it('displays signals executed count', async () => {
      const wrapper = mount(SystemStatusWidget, {
        global: {
          plugins: [pinia],
        },
      })

      const store = useSystemStatusStore()
      store.updateConnectionStatus('connected')
      store.updateStatistics({ signalsExecuted: 7 })

      await wrapper.vm.$nextTick()

      expect(wrapper.text()).toContain('7')
    })

    it('does not display statistics when disconnected', async () => {
      const wrapper = mount(SystemStatusWidget, {
        global: {
          plugins: [pinia],
        },
      })

      const store = useSystemStatusStore()
      store.updateConnectionStatus('disconnected')

      await wrapper.vm.$nextTick()

      // Statistics grid should not be visible
      expect(wrapper.findAll('.grid').length).toBe(0)
    })
  })

  describe('Expandable Hover Functionality', () => {
    it('expands on mouse enter', async () => {
      const wrapper = mount(SystemStatusWidget, {
        global: {
          plugins: [pinia],
        },
      })

      const widget = wrapper.find('[aria-label="System Status Widget"]')
      await widget.trigger('mouseenter')

      expect(wrapper.vm.isExpanded).toBe(true)
    })

    it('collapses on mouse leave', async () => {
      const wrapper = mount(SystemStatusWidget, {
        global: {
          plugins: [pinia],
        },
      })

      const widget = wrapper.find('[aria-label="System Status Widget"]')
      await widget.trigger('mouseenter')
      await widget.trigger('mouseleave')

      expect(wrapper.vm.isExpanded).toBe(false)
    })

    it('shows overnight summary when expanded', async () => {
      const wrapper = mount(SystemStatusWidget, {
        global: {
          plugins: [pinia],
        },
      })

      const store = useSystemStatusStore()
      store.updateOvernightSummary({
        barsProcessed: 5000,
        patternsDetected: 100,
        signalsGenerated: 25,
        errorsEncountered: 2,
        lastRunTime: new Date('2024-03-13T08:00:00Z'),
      })

      const widget = wrapper.find('[aria-label="System Status Widget"]')
      await widget.trigger('mouseenter')
      await wrapper.vm.$nextTick()

      expect(wrapper.text()).toContain('Overnight Summary')
      expect(wrapper.text()).toContain('5,000')
      expect(wrapper.text()).toContain('100')
      expect(wrapper.text()).toContain('25')
    })

    it('shows issue log when expanded', async () => {
      const wrapper = mount(SystemStatusWidget, {
        global: {
          plugins: [pinia],
        },
      })

      const store = useSystemStatusStore()
      store.addIssue({
        timestamp: new Date(),
        severity: 'error',
        message: 'Test error message',
      })

      const widget = wrapper.find('[aria-label="System Status Widget"]')
      await widget.trigger('mouseenter')
      await wrapper.vm.$nextTick()

      expect(wrapper.text()).toContain('Recent Issues')
      expect(wrapper.text()).toContain('Test error message')
    })

    it('displays no issues message when issue log is empty', async () => {
      const wrapper = mount(SystemStatusWidget, {
        global: {
          plugins: [pinia],
        },
      })

      const widget = wrapper.find('[aria-label="System Status Widget"]')
      await widget.trigger('mouseenter')
      await wrapper.vm.$nextTick()

      expect(wrapper.text()).toContain('No issues reported')
    })

    it('allows clearing issues', async () => {
      const wrapper = mount(SystemStatusWidget, {
        global: {
          plugins: [pinia],
        },
      })

      const store = useSystemStatusStore()
      store.addIssue({
        timestamp: new Date(),
        severity: 'warning',
        message: 'Test warning',
      })

      const widget = wrapper.find('[aria-label="System Status Widget"]')
      await widget.trigger('mouseenter')
      await wrapper.vm.$nextTick()

      const clearButton = wrapper.find('[aria-label="Clear all issues"]')
      await clearButton.trigger('click')

      expect(store.issueLog.length).toBe(0)
      expect(wrapper.text()).toContain('No issues reported')
    })
  })

  describe('Last Update Timestamp', () => {
    it('displays "Never" when no update has occurred', async () => {
      const wrapper = mount(SystemStatusWidget, {
        global: {
          plugins: [pinia],
        },
      })

      await wrapper.vm.$nextTick()

      expect(wrapper.text()).toContain('Never')
    })

    it('displays relative time after update', async () => {
      const wrapper = mount(SystemStatusWidget, {
        global: {
          plugins: [pinia],
        },
      })

      const store = useSystemStatusStore()
      store.updateStatistics({ barsAnalyzed: 100 })

      await wrapper.vm.$nextTick()

      expect(wrapper.text()).toContain('Just now')
    })
  })

  describe('Accessibility', () => {
    it('has proper ARIA labels', () => {
      const wrapper = mount(SystemStatusWidget, {
        global: {
          plugins: [pinia],
        },
      })

      expect(wrapper.find('[role="complementary"]').exists()).toBe(true)
      expect(wrapper.find('[aria-label="System Status Widget"]').exists()).toBe(
        true
      )
    })

    it('has ARIA live region for status announcements', () => {
      const wrapper = mount(SystemStatusWidget, {
        global: {
          plugins: [pinia],
        },
      })

      expect(wrapper.find('[role="status"]').exists()).toBe(true)
      expect(wrapper.find('[aria-live="assertive"]').exists()).toBe(true)
    })

    it('announces connection changes to screen readers', async () => {
      const wrapper = mount(SystemStatusWidget, {
        global: {
          plugins: [pinia],
        },
      })

      const store = useSystemStatusStore()

      // Update system status to trigger announcement
      store.updateConnectionStatus('connected')
      store.updateSystemStatus('error')

      await wrapper.vm.$nextTick()

      const liveRegion = wrapper.find('[role="status"]')
      // Check that aria status message is present (will contain error announcement)
      expect(liveRegion.text()).toBeTruthy()
    })

    it('announces critical status changes to screen readers', async () => {
      const wrapper = mount(SystemStatusWidget, {
        global: {
          plugins: [pinia],
        },
      })

      const store = useSystemStatusStore()
      store.updateConnectionStatus('connected')
      store.updateSystemStatus('operational')
      await wrapper.vm.$nextTick()

      store.updateSystemStatus('error')
      await wrapper.vm.$nextTick()

      const liveRegion = wrapper.find('[role="status"]')
      expect(liveRegion.text()).toContain('error')
    })

    it('supports keyboard navigation (escape key)', async () => {
      const wrapper = mount(SystemStatusWidget, {
        global: {
          plugins: [pinia],
        },
      })

      // Expand widget
      const widget = wrapper.find('[aria-label="System Status Widget"]')
      await widget.trigger('mouseenter')
      expect(wrapper.vm.isExpanded).toBe(true)

      // Press escape to collapse
      await widget.trigger('keydown.escape')
      expect(wrapper.vm.isExpanded).toBe(false)
    })
  })

  describe('Number Formatting', () => {
    it('formats large numbers with commas', async () => {
      const wrapper = mount(SystemStatusWidget, {
        global: {
          plugins: [pinia],
        },
      })

      const store = useSystemStatusStore()
      store.updateConnectionStatus('connected')
      store.updateStatistics({
        barsAnalyzed: 1234567,
        patternsDetected: 9876,
        signalsExecuted: 543,
      })

      await wrapper.vm.$nextTick()

      expect(wrapper.text()).toContain('1,234,567')
      expect(wrapper.text()).toContain('9,876')
      expect(wrapper.text()).toContain('543')
    })
  })

  describe('Issue Severity Styling', () => {
    it('applies error styling to error issues', async () => {
      const wrapper = mount(SystemStatusWidget, {
        global: {
          plugins: [pinia],
        },
      })

      const store = useSystemStatusStore()
      store.addIssue({
        timestamp: new Date(),
        severity: 'error',
        message: 'Critical error',
      })

      const widget = wrapper.find('[aria-label="System Status Widget"]')
      await widget.trigger('mouseenter')
      await wrapper.vm.$nextTick()

      expect(wrapper.find('.pi-times-circle').exists()).toBe(true)
      expect(wrapper.find('.border-red-500').exists()).toBe(true)
    })

    it('applies warning styling to warning issues', async () => {
      const wrapper = mount(SystemStatusWidget, {
        global: {
          plugins: [pinia],
        },
      })

      const store = useSystemStatusStore()
      store.addIssue({
        timestamp: new Date(),
        severity: 'warning',
        message: 'Warning message',
      })

      const widget = wrapper.find('[aria-label="System Status Widget"]')
      await widget.trigger('mouseenter')
      await wrapper.vm.$nextTick()

      expect(wrapper.find('.pi-exclamation-triangle').exists()).toBe(true)
      expect(wrapper.find('.border-yellow-500').exists()).toBe(true)
    })

    it('applies info styling to info issues', async () => {
      const wrapper = mount(SystemStatusWidget, {
        global: {
          plugins: [pinia],
        },
      })

      const store = useSystemStatusStore()
      store.addIssue({
        timestamp: new Date(),
        severity: 'info',
        message: 'Info message',
      })

      const widget = wrapper.find('[aria-label="System Status Widget"]')
      await widget.trigger('mouseenter')
      await wrapper.vm.$nextTick()

      expect(wrapper.find('.pi-info-circle').exists()).toBe(true)
      expect(wrapper.find('.border-blue-500').exists()).toBe(true)
    })
  })
})
