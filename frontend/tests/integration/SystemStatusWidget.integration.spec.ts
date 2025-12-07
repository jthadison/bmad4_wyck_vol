import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { ref } from 'vue'
import SystemStatusWidget from '@/components/SystemStatusWidget.vue'
import { useSystemStatusStore } from '@/stores/systemStatusStore'

// Create mocks at module level
const mockSubscribe = vi.fn()
const mockUnsubscribe = vi.fn()
const mockConnectionStatus = ref<'connecting' | 'connected' | 'disconnected'>(
  'disconnected'
)
const mockIsConnected = ref(false)

// Mock useWebSocket composable
vi.mock('@/composables/useWebSocket', () => ({
  useWebSocket: () => ({
    isConnected: mockIsConnected,
    connectionStatus: mockConnectionStatus,
    subscribe: mockSubscribe,
    unsubscribe: mockUnsubscribe,
  }),
}))

// Mock API client
const mockApiGet = vi.fn().mockResolvedValue({
  status: 'operational',
  bars_analyzed: 100,
  patterns_detected: 5,
  signals_executed: 2,
})

vi.mock('@/services/api', () => ({
  apiClient: {
    get: mockApiGet,
  },
}))

describe('SystemStatusWidget Integration Tests', () => {
  let pinia: ReturnType<typeof createPinia>

  beforeEach(() => {
    pinia = createPinia()
    setActivePinia(pinia)
    vi.clearAllMocks()
    vi.clearAllTimers()
    vi.useFakeTimers()

    // Reset mock refs
    mockConnectionStatus.value = 'disconnected'
    mockIsConnected.value = false
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  describe('WebSocket Event Subscriptions', () => {
    it('subscribes to WebSocket events on mount', () => {
      mount(SystemStatusWidget, {
        global: {
          plugins: [pinia],
        },
      })

      expect(mockSubscribe).toHaveBeenCalledWith(
        'pattern_detected',
        expect.any(Function)
      )
      expect(mockSubscribe).toHaveBeenCalledWith(
        'signal_generated',
        expect.any(Function)
      )
      expect(mockSubscribe).toHaveBeenCalledWith(
        'system_status',
        expect.any(Function)
      )
      expect(mockSubscribe).toHaveBeenCalledWith('error', expect.any(Function))
    })

    it('unsubscribes from WebSocket events on unmount', () => {
      const wrapper = mount(SystemStatusWidget, {
        global: {
          plugins: [pinia],
        },
      })

      wrapper.unmount()

      expect(mockUnsubscribe).toHaveBeenCalledWith(
        'pattern_detected',
        expect.any(Function)
      )
      expect(mockUnsubscribe).toHaveBeenCalledWith(
        'signal_generated',
        expect.any(Function)
      )
      expect(mockUnsubscribe).toHaveBeenCalledWith(
        'system_status',
        expect.any(Function)
      )
      expect(mockUnsubscribe).toHaveBeenCalledWith(
        'error',
        expect.any(Function)
      )
    })
  })

  describe('Pattern Detection Events', () => {
    it('increments pattern count when pattern_detected event received', async () => {
      const wrapper = mount(SystemStatusWidget, {
        global: {
          plugins: [pinia],
        },
      })

      const store = useSystemStatusStore()
      const initialCount = store.patternsDetected

      // Get the pattern_detected handler
      const patternHandler = mockSubscribe.mock.calls.find(
        (call) => call[0] === 'pattern_detected'
      )?.[1]

      expect(patternHandler).toBeDefined()

      // Simulate pattern detected event
      patternHandler?.()

      await wrapper.vm.$nextTick()

      expect(store.patternsDetected).toBe(initialCount + 1)
    })

    it('updates last update timestamp on pattern detection', async () => {
      const wrapper = mount(SystemStatusWidget, {
        global: {
          plugins: [pinia],
        },
      })

      const store = useSystemStatusStore()
      const beforeTimestamp = store.lastUpdateTimestamp

      // Get the pattern_detected handler
      const patternHandler = mockSubscribe.mock.calls.find(
        (call) => call[0] === 'pattern_detected'
      )?.[1]

      // Simulate pattern detected event
      patternHandler?.()

      await wrapper.vm.$nextTick()

      expect(store.lastUpdateTimestamp).not.toBe(beforeTimestamp)
      expect(store.lastUpdateTimestamp).toBeInstanceOf(Date)
    })
  })

  describe('Signal Generation Events', () => {
    it('increments signal count when signal_generated event received', async () => {
      const wrapper = mount(SystemStatusWidget, {
        global: {
          plugins: [pinia],
        },
      })

      const store = useSystemStatusStore()
      const initialCount = store.signalsExecuted

      // Get the signal_generated handler
      const signalHandler = mockSubscribe.mock.calls.find(
        (call) => call[0] === 'signal_generated'
      )?.[1]

      expect(signalHandler).toBeDefined()

      // Simulate signal generated event
      signalHandler?.()

      await wrapper.vm.$nextTick()

      expect(store.signalsExecuted).toBe(initialCount + 1)
    })

    it('updates last update timestamp on signal generation', async () => {
      const wrapper = mount(SystemStatusWidget, {
        global: {
          plugins: [pinia],
        },
      })

      const store = useSystemStatusStore()
      const beforeTimestamp = store.lastUpdateTimestamp

      // Get the signal_generated handler
      const signalHandler = mockSubscribe.mock.calls.find(
        (call) => call[0] === 'signal_generated'
      )?.[1]

      // Simulate signal generated event
      signalHandler?.()

      await wrapper.vm.$nextTick()

      expect(store.lastUpdateTimestamp).not.toBe(beforeTimestamp)
      expect(store.lastUpdateTimestamp).toBeInstanceOf(Date)
    })
  })

  describe('System Status Events', () => {
    it('updates statistics from system_status event', async () => {
      const wrapper = mount(SystemStatusWidget, {
        global: {
          plugins: [pinia],
        },
      })

      const store = useSystemStatusStore()

      // Get the system_status handler
      const statusHandler = mockSubscribe.mock.calls.find(
        (call) => call[0] === 'system_status'
      )?.[1]

      expect(statusHandler).toBeDefined()

      // Simulate system_status event
      statusHandler?.({
        type: 'system_status',
        data: {
          bars_analyzed: 5000,
          patterns_detected: 150,
          signals_executed: 30,
          status: 'operational',
        },
      })

      await wrapper.vm.$nextTick()

      expect(store.barsAnalyzed).toBe(5000)
      expect(store.patternsDetected).toBe(150)
      expect(store.signalsExecuted).toBe(30)
      expect(store.systemStatus).toBe('operational')
    })

    it('updates overnight summary from system_status event', async () => {
      const wrapper = mount(SystemStatusWidget, {
        global: {
          plugins: [pinia],
        },
      })

      const store = useSystemStatusStore()

      // Get the system_status handler
      const statusHandler = mockSubscribe.mock.calls.find(
        (call) => call[0] === 'system_status'
      )?.[1]

      const testDate = new Date('2024-03-13T08:00:00Z')

      // Simulate system_status event with overnight summary
      statusHandler?.({
        type: 'system_status',
        data: {
          bars_analyzed: 1000,
          patterns_detected: 50,
          signals_executed: 10,
          overnight_summary: {
            barsProcessed: 10000,
            patternsDetected: 200,
            signalsGenerated: 50,
            errorsEncountered: 3,
            lastRunTime: testDate,
          },
        },
      })

      await wrapper.vm.$nextTick()

      expect(store.overnightSummary.barsProcessed).toBe(10000)
      expect(store.overnightSummary.patternsDetected).toBe(200)
      expect(store.overnightSummary.signalsGenerated).toBe(50)
      expect(store.overnightSummary.errorsEncountered).toBe(3)
    })
  })

  describe('Error Events', () => {
    it('adds error to issue log when error event received', async () => {
      const wrapper = mount(SystemStatusWidget, {
        global: {
          plugins: [pinia],
        },
      })

      const store = useSystemStatusStore()

      // Get the error handler
      const errorHandler = mockSubscribe.mock.calls.find(
        (call) => call[0] === 'error'
      )?.[1]

      expect(errorHandler).toBeDefined()

      // Simulate error event
      errorHandler?.({
        type: 'error',
        error: 'Database connection failed',
        timestamp: new Date().toISOString(),
      })

      await wrapper.vm.$nextTick()

      expect(store.issueLog.length).toBeGreaterThan(0)
      expect(store.issueLog[0].severity).toBe('error')
      expect(store.issueLog[0].message).toContain('Database connection failed')
    })

    it('updates system status to error when error event received', async () => {
      const wrapper = mount(SystemStatusWidget, {
        global: {
          plugins: [pinia],
        },
      })

      const store = useSystemStatusStore()
      store.updateConnectionStatus('connected')
      store.updateSystemStatus('operational')

      // Get the error handler
      const errorHandler = mockSubscribe.mock.calls.find(
        (call) => call[0] === 'error'
      )?.[1]

      // Simulate error event
      errorHandler?.({
        type: 'error',
        message: 'Critical system error',
      })

      await wrapper.vm.$nextTick()

      expect(store.systemStatus).toBe('error')
    })
  })

  describe('REST API Polling', () => {
    it('polls system status on mount', async () => {
      mount(SystemStatusWidget, {
        global: {
          plugins: [pinia],
        },
      })

      await flushPromises()

      expect(mockApiGet).toHaveBeenCalledWith('/health')
    })

    it('polls every 2 seconds', async () => {
      mount(SystemStatusWidget, {
        global: {
          plugins: [pinia],
        },
      })

      await flushPromises()
      const initialCallCount = mockApiGet.mock.calls.length

      // Advance time by 2 seconds
      vi.advanceTimersByTime(2000)
      await flushPromises()

      // Should have polled again
      expect(mockApiGet.mock.calls.length).toBeGreaterThan(initialCallCount)
    })

    it('stops polling when component unmounts', async () => {
      const wrapper = mount(SystemStatusWidget, {
        global: {
          plugins: [pinia],
        },
      })

      await flushPromises()
      const callCountBeforeUnmount = mockApiGet.mock.calls.length

      wrapper.unmount()

      // Advance time - should not poll after unmount
      vi.advanceTimersByTime(10000)
      await flushPromises()

      // Call count should not increase after unmount
      expect(mockApiGet.mock.calls.length).toBe(callCountBeforeUnmount)
    })
  })

  describe('Component Re-rendering on WebSocket Updates', () => {
    it('re-renders when pattern count increases', async () => {
      const wrapper = mount(SystemStatusWidget, {
        global: {
          plugins: [pinia],
        },
      })

      const store = useSystemStatusStore()
      store.updateConnectionStatus('connected')

      const initialText = wrapper.text()

      // Increment pattern count
      store.incrementPatternCount()
      await wrapper.vm.$nextTick()

      const updatedText = wrapper.text()

      // Text should have changed due to re-render
      expect(updatedText).not.toBe(initialText)
    })

    it('re-renders when system status changes', async () => {
      const wrapper = mount(SystemStatusWidget, {
        global: {
          plugins: [pinia],
        },
      })

      const store = useSystemStatusStore()
      store.updateConnectionStatus('connected')
      store.updateSystemStatus('operational')
      await wrapper.vm.$nextTick()

      const operationalIcon = wrapper.find('.pi-check-circle')
      expect(operationalIcon.exists()).toBe(true)

      // Change to error status
      store.updateSystemStatus('error')
      await wrapper.vm.$nextTick()

      const errorIcon = wrapper.find('.pi-times-circle')
      expect(errorIcon.exists()).toBe(true)
      expect(wrapper.find('.pi-check-circle').exists()).toBe(false)
    })
  })
})
