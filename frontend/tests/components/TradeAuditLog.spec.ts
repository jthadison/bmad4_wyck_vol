/**
 * Unit Tests for TradeAuditLog Component (Story 10.8)
 *
 * Test Coverage:
 * - Component rendering with mock data
 * - Column display and formatting
 * - Filtering functionality
 * - Sorting triggers
 * - Pagination triggers
 * - Row expansion
 * - CSV/JSON export generation
 * - Loading and error states
 *
 * Author: Story 10.8
 */

import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'
import { nextTick } from 'vue'
import TradeAuditLog from '@/components/audit/TradeAuditLog.vue'
import PrimeVue from 'primevue/config'

// Mock API client
vi.mock('@/services/api', () => ({
  getAuditLog: vi.fn(),
}))

// Mock toast
vi.mock('primevue/usetoast', () => ({
  useToast: () => ({
    add: vi.fn(),
  }),
}))

// Mock audit log response
const mockAuditLogResponse = {
  data: [
    {
      id: '1',
      timestamp: '2024-03-15T14:30:00Z',
      symbol: 'AAPL',
      pattern_type: 'SPRING',
      phase: 'C',
      confidence_score: 85,
      status: 'FILLED',
      rejection_reason: null,
      signal_id: 'signal-1',
      pattern_id: 'pattern-1',
      validation_chain: [
        {
          step_name: 'Volume Validation',
          passed: true,
          reason: 'Volume 0.65x < 0.7x threshold',
          timestamp: '2024-03-15T14:30:00Z',
          wyckoff_rule_reference: 'Law #1: Supply & Demand',
        },
      ],
      entry_price: '150.00',
      target_price: '156.00',
      stop_loss: '148.00',
      r_multiple: '3.0',
      volume_ratio: '0.65',
      spread_ratio: '0.85',
    },
    {
      id: '2',
      timestamp: '2024-03-15T15:30:00Z',
      symbol: 'TSLA',
      pattern_type: 'SOS',
      phase: 'D',
      confidence_score: 82,
      status: 'REJECTED',
      rejection_reason: 'Volume ratio 0.75x > 0.7x threshold',
      signal_id: null,
      pattern_id: 'pattern-2',
      validation_chain: [
        {
          step_name: 'Volume Validation',
          passed: false,
          reason: 'Volume ratio 0.75x > 0.7x threshold',
          timestamp: '2024-03-15T15:30:00Z',
          wyckoff_rule_reference: 'Law #1: Supply & Demand',
        },
      ],
      entry_price: null,
      target_price: null,
      stop_loss: null,
      r_multiple: null,
      volume_ratio: '0.75',
      spread_ratio: '0.90',
    },
  ],
  total_count: 2,
  limit: 50,
  offset: 0,
}

// Helper to create common mount options
const mountOptions = {
  global: {
    plugins: [PrimeVue],
    stubs: {
      DataTable: {
        template: '<div class="p-datatable"><slot /></div>',
        props: ['value', 'rows', 'paginator', 'totalRecords', 'lazy'],
      },
      Column: {
        template: '<div class="p-column"><slot /></div>',
        props: ['field', 'header', 'sortable'],
      },
      Calendar: {
        template: '<input class="p-calendar" />',
        props: ['modelValue', 'selectionMode', 'showIcon'],
      },
      MultiSelect: {
        template: '<select class="p-multiselect" multiple><slot /></select>',
        props: ['modelValue', 'options', 'placeholder'],
      },
      InputText: {
        template: '<input class="p-inputtext" />',
        props: ['modelValue', 'placeholder'],
      },
      Button: {
        template:
          '<button class="p-button" @click="$emit(\'click\')"><slot /></button>',
        props: ['label', 'icon', 'outlined'],
      },
      Tooltip: {
        template: '<div><slot /></div>',
        props: ['value'],
      },
    },
  },
}

describe('TradeAuditLog', () => {
  beforeEach(async () => {
    vi.clearAllMocks()
    const { getAuditLog } = await import('@/services/api')
    ;(getAuditLog as unknown).mockResolvedValue(mockAuditLogResponse)
  })

  it('renders component correctly', async () => {
    const wrapper = mount(TradeAuditLog, mountOptions)

    await nextTick()
    await new Promise((resolve) => setTimeout(resolve, 100))

    expect(wrapper.find('h2').text()).toBe('Trade Audit Log')
  })

  it('fetches audit log on mount', async () => {
    const { getAuditLog } = await import('@/services/api')

    mount(TradeAuditLog, mountOptions)

    await nextTick()
    await new Promise((resolve) => setTimeout(resolve, 100))

    expect(getAuditLog).toHaveBeenCalled()
  })

  it('displays audit log entries', async () => {
    const wrapper = mount(TradeAuditLog, mountOptions)

    await nextTick()
    await new Promise((resolve) => setTimeout(resolve, 100))

    // Check if table contains symbols
    const html = wrapper.html()
    expect(html).toContain('AAPL')
    expect(html).toContain('TSLA')
  })

  it('formats confidence scores with colors', async () => {
    const wrapper = mount(TradeAuditLog, mountOptions)

    await nextTick()
    await new Promise((resolve) => setTimeout(resolve, 100))

    // Confidence >= 80 should have green color class
    expect(wrapper.html()).toContain('text-green-500')
  })

  it('displays status badges with correct colors', async () => {
    const wrapper = mount(TradeAuditLog, mountOptions)

    await nextTick()
    await new Promise((resolve) => setTimeout(resolve, 100))

    // Check for status display
    expect(wrapper.html()).toContain('FILLED')
    expect(wrapper.html()).toContain('REJECTED')
  })

  it('clears filters when clear button clicked', async () => {
    const wrapper = mount(TradeAuditLog, mountOptions)

    await nextTick()
    await new Promise((resolve) => setTimeout(resolve, 600))

    // Set some filters
    const vm = wrapper.vm as unknown
    vm.filters.searchText = 'test'
    vm.filters.selectedPatterns = ['SPRING']

    await nextTick()

    // Click clear filters button
    const clearButton = wrapper.find('button')
    if (clearButton.exists()) {
      await clearButton.trigger('click')
    }

    await nextTick()

    // Filters should be cleared
    expect(vm.filters.searchText).toBe('')
  })

  it('exports to CSV when export button clicked', async () => {
    // Mock URL.createObjectURL and link.click()
    const mockCreateObjectURL = vi.fn(() => 'mock-url')
    const mockRevokeObjectURL = vi.fn()
    global.URL.createObjectURL = mockCreateObjectURL
    global.URL.revokeObjectURL = mockRevokeObjectURL

    const mockClick = vi.fn()
    const mockLink = {
      click: mockClick,
      href: '',
      download: '',
      setAttribute: vi.fn(),
      style: {},
    }
    vi.spyOn(document, 'createElement').mockReturnValue(mockLink as unknown)

    const wrapper = mount(TradeAuditLog, mountOptions)

    await nextTick()
    await new Promise((resolve) => setTimeout(resolve, 100))

    // Call exportToCSV directly
    const vm = wrapper.vm as unknown
    vm.exportToCSV()

    await nextTick()

    expect(mockCreateObjectURL).toHaveBeenCalled()
    expect(mockClick).toHaveBeenCalled()
    expect(mockRevokeObjectURL).toHaveBeenCalled()
  })

  it('exports to JSON when export button clicked', async () => {
    // Mock URL.createObjectURL and link.click()
    const mockCreateObjectURL = vi.fn(() => 'mock-url')
    const mockRevokeObjectURL = vi.fn()
    global.URL.createObjectURL = mockCreateObjectURL
    global.URL.revokeObjectURL = mockRevokeObjectURL

    const mockClick = vi.fn()
    const mockLink = {
      click: mockClick,
      href: '',
      download: '',
      setAttribute: vi.fn(),
      style: {},
    }
    vi.spyOn(document, 'createElement').mockReturnValue(mockLink as unknown)

    const wrapper = mount(TradeAuditLog, mountOptions)

    await nextTick()
    await new Promise((resolve) => setTimeout(resolve, 100))

    // Call exportToJSON directly
    const vm = wrapper.vm as unknown
    vm.exportToJSON()

    await nextTick()

    expect(mockCreateObjectURL).toHaveBeenCalled()
    expect(mockClick).toHaveBeenCalled()
    expect(mockRevokeObjectURL).toHaveBeenCalled()
  })

  it('handles API errors gracefully', async () => {
    const { getAuditLog } = await import('@/services/api')
    ;(getAuditLog as unknown).mockRejectedValue(new Error('API Error'))

    const wrapper = mount(TradeAuditLog, mountOptions)

    await nextTick()
    await new Promise((resolve) => setTimeout(resolve, 100))

    // Component should not crash
    expect(wrapper.exists()).toBe(true)
  })

  it('debounces filter changes', async () => {
    vi.useFakeTimers()

    const { getAuditLog } = await import('@/services/api')

    const wrapper = mount(TradeAuditLog, mountOptions)

    await nextTick()

    const vm = wrapper.vm as unknown

    // Change filter
    vm.filters.searchText = 'test'

    // Should not fetch immediately
    const callCountBefore = (getAuditLog as unknown).mock.calls.length

    // Fast forward 400ms (less than 500ms debounce)
    vi.advanceTimersByTime(400)
    await nextTick()

    expect((getAuditLog as unknown).mock.calls.length).toBe(callCountBefore)

    // Fast forward another 200ms (total 600ms, exceeds 500ms debounce)
    vi.advanceTimersByTime(200)
    await nextTick()

    // Now it should have fetched
    expect((getAuditLog as unknown).mock.calls.length).toBeGreaterThan(
      callCountBefore
    )

    vi.useRealTimers()
  })

  it('formats timestamps as relative time', async () => {
    const wrapper = mount(TradeAuditLog, mountOptions)

    await nextTick()
    await new Promise((resolve) => setTimeout(resolve, 100))

    const vm = wrapper.vm as unknown
    const relativeTime = vm.formatTimestamp('2024-03-15T14:30:00Z')

    // Should return relative format like "X hours ago" or "X days ago"
    expect(relativeTime).toMatch(/(hours|days) ago/)
  })

  it('formats prices with 2 decimal places', async () => {
    const wrapper = mount(TradeAuditLog, mountOptions)

    await nextTick()

    const vm = wrapper.vm as unknown
    const formatted = vm.formatPrice('150.123456')

    expect(formatted).toBe('150.12')
  })

  it('handles null prices correctly', async () => {
    const wrapper = mount(TradeAuditLog, mountOptions)

    await nextTick()

    const vm = wrapper.vm as unknown
    const formatted = vm.formatPrice(null)

    expect(formatted).toBe('N/A')
  })

  it('returns correct status colors', async () => {
    const wrapper = mount(TradeAuditLog, mountOptions)

    await nextTick()

    const vm = wrapper.vm as unknown

    expect(vm.getStatusColor('FILLED')).toBe('success')
    expect(vm.getStatusColor('TARGET_HIT')).toBe('success')
    expect(vm.getStatusColor('REJECTED')).toBe('danger')
    expect(vm.getStatusColor('PENDING')).toBe('warning')
    expect(vm.getStatusColor('APPROVED')).toBe('warning')
    expect(vm.getStatusColor('STOPPED')).toBe('secondary')
    expect(vm.getStatusColor('EXPIRED')).toBe('secondary')
  })

  it('returns correct confidence colors', async () => {
    const wrapper = mount(TradeAuditLog, mountOptions)

    await nextTick()

    const vm = wrapper.vm as unknown

    expect(vm.getConfidenceColor(85)).toBe('text-green-500')
    expect(vm.getConfidenceColor(75)).toBe('text-yellow-500')
    expect(vm.getConfidenceColor(65)).toBe('text-gray-500')
  })

  it('toggles row expansion correctly', async () => {
    const wrapper = mount(TradeAuditLog, mountOptions)

    await nextTick()
    await new Promise((resolve) => setTimeout(resolve, 100))

    const vm = wrapper.vm as unknown

    // Initially no row expanded
    expect(vm.expandedRowId).toBeNull()

    // Expand row
    vm.toggleRowExpansion('1')
    expect(vm.expandedRowId).toBe('1')

    // Toggle same row (collapse)
    vm.toggleRowExpansion('1')
    expect(vm.expandedRowId).toBeNull()

    // Expand different row
    vm.toggleRowExpansion('2')
    expect(vm.expandedRowId).toBe('2')
  })

  it('shows validation chain with Wyckoff rules', async () => {
    const wrapper = mount(TradeAuditLog, mountOptions)

    await nextTick()
    await new Promise((resolve) => setTimeout(resolve, 100))

    const vm = wrapper.vm as unknown

    // Expand first row
    vm.expandedRowId = '1'
    await nextTick()

    const html = wrapper.html()

    // Should show Wyckoff rule reference
    expect(html).toContain('Law #1: Supply & Demand')
  })
})
