/**
 * Tests for EventFeedPanel Component (Story 16.3b)
 *
 * Test Coverage:
 * - Component rendering
 * - Empty state display
 * - Event display and formatting
 * - Filtering functionality
 * - Auto-scroll toggle
 * - Event detail dialog
 * - WebSocket event handling
 * - Clear events functionality
 *
 * Author: Story 16.3b
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'

// Mock functions must be declared at the top level BEFORE vi.mock
const mockSubscribe = vi.fn()
const mockUnsubscribe = vi.fn()

vi.mock('@/services/websocketService', () => ({
  websocketService: {
    connectionStatus: { value: 'connected' },
    lastMessageTime: { value: null },
    reconnectAttemptsCount: { value: 0 },
    isConnected: () => true,
    subscribe: (...args: unknown[]) => mockSubscribe(...args),
    unsubscribe: (...args: unknown[]) => mockUnsubscribe(...args),
    connect: vi.fn(),
    disconnect: vi.fn(),
    reconnectNow: vi.fn(),
    getLastSequenceNumber: () => 0,
    getConnectionId: () => 'test-conn-id',
  },
}))

import EventFeedPanel from '@/components/campaigns/EventFeedPanel.vue'

// Mock PrimeVue components
vi.mock('primevue/dropdown', () => ({
  default: {
    name: 'Dropdown',
    template: '<select data-testid="filter-dropdown"><slot /></select>',
    props: [
      'modelValue',
      'options',
      'optionLabel',
      'optionValue',
      'placeholder',
    ],
  },
}))

vi.mock('primevue/dialog', () => ({
  default: {
    name: 'Dialog',
    template:
      '<div v-if="visible" class="dialog" data-testid="detail-dialog"><slot /></div>',
    props: ['visible', 'header', 'modal', 'draggable', 'style'],
  },
}))

vi.mock('primevue/badge', () => ({
  default: {
    name: 'Badge',
    template:
      '<span class="badge" data-testid="event-badge">{{ value }}</span>',
    props: ['value', 'severity'],
  },
}))

describe('EventFeedPanel', () => {
  beforeEach(() => {
    vi.useFakeTimers()
    vi.clearAllMocks()
  })

  afterEach(() => {
    vi.useRealTimers()
    vi.clearAllMocks()
  })

  function mountComponent(options = {}) {
    return mount(EventFeedPanel, {
      global: {
        stubs: {
          Dialog: {
            name: 'Dialog',
            template:
              '<div v-if="visible" class="dialog" data-testid="detail-dialog"><slot /></div>',
            props: ['visible', 'header', 'modal', 'draggable', 'style'],
          },
        },
      },
      ...options,
    })
  }

  describe('component rendering', () => {
    it('should render component with title', () => {
      const wrapper = mountComponent()
      expect(wrapper.exists()).toBe(true)
      expect(wrapper.find('h2').text()).toBe('Event Feed')
    })

    it('should render filter dropdown', () => {
      const wrapper = mountComponent()
      const dropdown = wrapper.find('[data-testid="filter-dropdown"]')
      expect(dropdown.exists()).toBe(true)
    })

    it('should render auto-scroll toggle button', () => {
      const wrapper = mountComponent()
      const autoScrollBtn = wrapper.findAll('.control-btn')[0]
      expect(autoScrollBtn.exists()).toBe(true)
      expect(autoScrollBtn.classes()).toContain('active')
    })

    it('should render clear events button', () => {
      const wrapper = mountComponent()
      const clearBtn = wrapper.findAll('.control-btn')[1]
      expect(clearBtn.exists()).toBe(true)
    })
  })

  describe('empty state', () => {
    it('should display empty state when no events', () => {
      const wrapper = mountComponent()
      const emptyState = wrapper.find('.empty-state')
      expect(emptyState.exists()).toBe(true)
      expect(wrapper.text()).toContain('No events yet')
    })

    it('should show hint text in empty state', () => {
      const wrapper = mountComponent()
      expect(wrapper.text()).toContain('Events will appear as they occur')
    })
  })

  describe('event display', () => {
    it('should display events after receiving WebSocket message', async () => {
      const wrapper = mountComponent()

      // Get the campaign:created handler that was registered
      const createHandler = mockSubscribe.mock.calls.find(
        (call) => call[0] === 'campaign:created'
      )?.[1]

      expect(createHandler).toBeDefined()

      // Simulate receiving an event
      createHandler({
        type: 'campaign:created',
        data: { symbol: 'AAPL', campaign_id: 'CAMP-001' },
        timestamp: new Date().toISOString(),
        sequence_number: 1,
      })

      await flushPromises()

      const eventItems = wrapper.findAll('.event-item')
      expect(eventItems.length).toBe(1)
      expect(wrapper.text()).toContain('AAPL')
    })

    it('should display correct icon for campaign:created events', async () => {
      const wrapper = mountComponent()

      const createHandler = mockSubscribe.mock.calls.find(
        (call) => call[0] === 'campaign:created'
      )?.[1]

      createHandler({
        type: 'campaign:created',
        data: { symbol: 'AAPL' },
        timestamp: new Date().toISOString(),
        sequence_number: 1,
      })

      await flushPromises()

      const eventIcon = wrapper.find('.event-icon i')
      expect(eventIcon.classes()).toContain('pi-plus-circle')
    })

    it('should display correct icon for signal:new events', async () => {
      const wrapper = mountComponent()

      const signalHandler = mockSubscribe.mock.calls.find(
        (call) => call[0] === 'signal:new'
      )?.[1]

      signalHandler({
        type: 'signal:new',
        data: { symbol: 'TSLA', pattern_type: 'SPRING' },
        timestamp: new Date().toISOString(),
        sequence_number: 1,
      })

      await flushPromises()

      const eventIcon = wrapper.find('.event-icon i')
      expect(eventIcon.classes()).toContain('pi-bolt')
    })

    it('should format relative time correctly', async () => {
      const wrapper = mountComponent()

      const createHandler = mockSubscribe.mock.calls.find(
        (call) => call[0] === 'campaign:created'
      )?.[1]

      createHandler({
        type: 'campaign:created',
        data: { symbol: 'AAPL' },
        timestamp: new Date().toISOString(),
        sequence_number: 1,
      })

      await flushPromises()

      expect(wrapper.text()).toContain('just now')
    })

    it('should limit events to MAX_EVENTS (100)', async () => {
      const wrapper = mountComponent()

      const createHandler = mockSubscribe.mock.calls.find(
        (call) => call[0] === 'campaign:created'
      )?.[1]

      // Add 110 events
      for (let i = 0; i < 110; i++) {
        createHandler({
          type: 'campaign:created',
          data: { symbol: `SYM${i}` },
          timestamp: new Date().toISOString(),
          sequence_number: i,
        })
      }

      await flushPromises()

      // Check internal state - should be limited to 100
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      expect((wrapper.vm as any).events.length).toBe(100)
    })
  })

  describe('filtering', () => {
    it('should filter events by type', async () => {
      const wrapper = mountComponent()

      // Add different event types
      const createHandler = mockSubscribe.mock.calls.find(
        (call) => call[0] === 'campaign:created'
      )?.[1]
      const updateHandler = mockSubscribe.mock.calls.find(
        (call) => call[0] === 'campaign:updated'
      )?.[1]

      createHandler({
        type: 'campaign:created',
        data: { symbol: 'AAPL' },
        timestamp: new Date().toISOString(),
        sequence_number: 1,
      })

      updateHandler({
        type: 'campaign:updated',
        data: { symbol: 'TSLA' },
        timestamp: new Date().toISOString(),
        sequence_number: 2,
      })

      await flushPromises()

      // Initially shows all events
      expect(wrapper.findAll('.event-item').length).toBe(2)

      // Filter to only show created events
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      ;(wrapper.vm as any).selectedFilter = 'campaign:created'
      await flushPromises()

      expect(wrapper.findAll('.event-item').length).toBe(1)
      expect(wrapper.text()).toContain('AAPL')
      expect(wrapper.text()).not.toContain('TSLA')
    })
  })

  describe('auto-scroll toggle', () => {
    it('should toggle auto-scroll on button click', async () => {
      const wrapper = mountComponent()

      const autoScrollBtn = wrapper.findAll('.control-btn')[0]

      // Initially active
      expect(autoScrollBtn.classes()).toContain('active')

      // Click to toggle off
      await autoScrollBtn.trigger('click')
      expect(autoScrollBtn.classes()).not.toContain('active')

      // Click to toggle on
      await autoScrollBtn.trigger('click')
      expect(autoScrollBtn.classes()).toContain('active')
    })
  })

  describe('clear events', () => {
    it('should clear all events on button click', async () => {
      const wrapper = mountComponent()

      // Add an event first
      const createHandler = mockSubscribe.mock.calls.find(
        (call) => call[0] === 'campaign:created'
      )?.[1]

      createHandler({
        type: 'campaign:created',
        data: { symbol: 'AAPL' },
        timestamp: new Date().toISOString(),
        sequence_number: 1,
      })

      await flushPromises()
      expect(wrapper.findAll('.event-item').length).toBe(1)

      // Click clear button
      const clearBtn = wrapper.findAll('.control-btn')[1]
      await clearBtn.trigger('click')

      expect(wrapper.findAll('.event-item').length).toBe(0)
      expect(wrapper.find('.empty-state').exists()).toBe(true)
    })
  })

  describe('event detail dialog', () => {
    it('should open dialog on event click', async () => {
      const wrapper = mountComponent()

      // Add an event
      const createHandler = mockSubscribe.mock.calls.find(
        (call) => call[0] === 'campaign:created'
      )?.[1]

      createHandler({
        type: 'campaign:created',
        data: { symbol: 'AAPL' },
        timestamp: new Date().toISOString(),
        sequence_number: 1,
      })

      await flushPromises()

      // Click on the event
      const eventItem = wrapper.find('.event-item')
      await eventItem.trigger('click')

      // Check that selectedEvent is set
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      expect((wrapper.vm as any).showDetailDialog).toBe(true)
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      expect((wrapper.vm as any).selectedEvent).not.toBeNull()
    })
  })

  describe('WebSocket integration', () => {
    it('should subscribe to all event types on mount', () => {
      mountComponent()

      expect(mockSubscribe).toHaveBeenCalledWith(
        'campaign:created',
        expect.any(Function)
      )
      expect(mockSubscribe).toHaveBeenCalledWith(
        'campaign:updated',
        expect.any(Function)
      )
      expect(mockSubscribe).toHaveBeenCalledWith(
        'campaign:invalidated',
        expect.any(Function)
      )
      expect(mockSubscribe).toHaveBeenCalledWith(
        'signal:new',
        expect.any(Function)
      )
      expect(mockSubscribe).toHaveBeenCalledWith(
        'pattern_detected',
        expect.any(Function)
      )
    })

    it('should unsubscribe from all event types on unmount', () => {
      const wrapper = mountComponent()

      wrapper.unmount()

      expect(mockUnsubscribe).toHaveBeenCalledWith(
        'campaign:created',
        expect.any(Function)
      )
      expect(mockUnsubscribe).toHaveBeenCalledWith(
        'campaign:updated',
        expect.any(Function)
      )
      expect(mockUnsubscribe).toHaveBeenCalledWith(
        'campaign:invalidated',
        expect.any(Function)
      )
      expect(mockUnsubscribe).toHaveBeenCalledWith(
        'signal:new',
        expect.any(Function)
      )
      expect(mockUnsubscribe).toHaveBeenCalledWith(
        'pattern_detected',
        expect.any(Function)
      )
    })
  })

  describe('event count badge', () => {
    it('should display correct event count', async () => {
      const wrapper = mountComponent()

      const createHandler = mockSubscribe.mock.calls.find(
        (call) => call[0] === 'campaign:created'
      )?.[1]

      createHandler({
        type: 'campaign:created',
        data: { symbol: 'AAPL' },
        timestamp: new Date().toISOString(),
        sequence_number: 1,
      })

      createHandler({
        type: 'campaign:created',
        data: { symbol: 'TSLA' },
        timestamp: new Date().toISOString(),
        sequence_number: 2,
      })

      await flushPromises()

      expect(wrapper.text()).toContain('2 events')
    })

    it('should use singular "event" for one event', async () => {
      const wrapper = mountComponent()

      const createHandler = mockSubscribe.mock.calls.find(
        (call) => call[0] === 'campaign:created'
      )?.[1]

      createHandler({
        type: 'campaign:created',
        data: { symbol: 'AAPL' },
        timestamp: new Date().toISOString(),
        sequence_number: 1,
      })

      await flushPromises()

      expect(wrapper.text()).toContain('1 event')
      expect(wrapper.text()).not.toContain('1 events')
    })
  })

  describe('event color coding', () => {
    it('should apply correct color class for created events', async () => {
      const wrapper = mountComponent()

      const createHandler = mockSubscribe.mock.calls.find(
        (call) => call[0] === 'campaign:created'
      )?.[1]

      createHandler({
        type: 'campaign:created',
        data: { symbol: 'AAPL' },
        timestamp: new Date().toISOString(),
        sequence_number: 1,
      })

      await flushPromises()

      const eventItem = wrapper.find('.event-item')
      expect(eventItem.classes()).toContain('event-created')
    })

    it('should apply correct color class for invalidated events', async () => {
      const wrapper = mountComponent()

      const invalidateHandler = mockSubscribe.mock.calls.find(
        (call) => call[0] === 'campaign:invalidated'
      )?.[1]

      invalidateHandler({
        type: 'campaign:invalidated',
        data: { symbol: 'AAPL' },
        timestamp: new Date().toISOString(),
        sequence_number: 1,
      })

      await flushPromises()

      const eventItem = wrapper.find('.event-item')
      expect(eventItem.classes()).toContain('event-invalidated')
    })
  })
})
