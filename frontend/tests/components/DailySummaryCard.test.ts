/**
 * Unit Tests for DailySummaryCard Component (Story 10.3)
 *
 * Purpose:
 * --------
 * Tests for DailySummaryCard.vue component including:
 * - Component rendering with mock API data
 * - Summary metrics display (symbols, patterns, signals, heat)
 * - Suggested actions list rendering
 * - Loading and error states
 *
 * Test Coverage (AC: 8):
 * -----------------------
 * - Component renders with mock daily summary data
 * - All summary fields display correctly
 * - Action items list renders
 * - Mock API using Vitest functions
 *
 * Author: Story 10.3
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { mount, VueWrapper } from '@vue/test-utils'
import Big from 'big.js'
import DailySummaryCard from '@/components/DailySummaryCard.vue'
import type { DailySummary } from '@/types/daily-summary'

// Mock API client
vi.mock('@/services/api', () => ({
  apiClient: {
    get: vi.fn(),
  },
}))

import { apiClient } from '@/services/api'

describe('DailySummaryCard.vue', () => {
  let wrapper: VueWrapper

  // Mock daily summary data
  const mockSummary: DailySummary = {
    symbols_scanned: 15,
    symbols_in_watchlist: 20,
    patterns_detected: 23,
    signals_executed: 4,
    signals_rejected: 8,
    portfolio_heat_change: new Big('1.2'),
    suggested_actions: [
      'Review Campaign C-2024-03-15-AAPL: 2 positions approaching stops',
      'Portfolio heat at 7.8% - capacity for ~2 more signals',
    ],
    timestamp: '2024-03-15T14:30:00Z',
  }

  beforeEach(() => {
    // Clear localStorage before each test
    localStorage.clear()

    // Reset mocks
    vi.clearAllMocks()
  })

  afterEach(() => {
    if (wrapper) {
      wrapper.unmount()
    }
  })

  describe('Component Rendering (AC: 8)', () => {
    it('should render daily summary with all metrics', async () => {
      // Mock API to return summary
      vi.mocked(apiClient.get).mockResolvedValue(mockSummary)

      // Mount component
      wrapper = mount(DailySummaryCard)

      // Wait for API call and rendering
      await wrapper.vm.$nextTick()
      await new Promise((resolve) => setTimeout(resolve, 50))

      // Verify component is visible
      expect(wrapper.find('[role="region"]').exists()).toBe(true)

      // Verify metrics are displayed
      const text = wrapper.text()
      expect(text).toContain('15') // symbols_scanned
      expect(text).toContain('23') // patterns_detected
      expect(text).toContain('4') // signals_executed
      expect(text).toContain('8') // signals_rejected
      expect(text).toContain('+1.2%') // portfolio_heat_change
    })

    it('should display suggested actions list', async () => {
      vi.mocked(apiClient.get).mockResolvedValue(mockSummary)

      wrapper = mount(DailySummaryCard)
      await wrapper.vm.$nextTick()
      await new Promise((resolve) => setTimeout(resolve, 50))

      // Verify actions section exists
      expect(wrapper.text()).toContain('Suggested Actions')

      // Verify both actions are rendered
      expect(wrapper.text()).toContain('2 positions approaching stops')
      expect(wrapper.text()).toContain('capacity for ~2 more signals')

      // Verify action list items
      const actionItems = wrapper.findAll('[role="list"] li')
      expect(actionItems.length).toBe(2)
    })

    it('should format numbers with commas', async () => {
      const largeSummary = {
        ...mockSummary,
        symbols_scanned: 1234,
        patterns_detected: 5678,
      }

      vi.mocked(apiClient.get).mockResolvedValue(largeSummary)

      wrapper = mount(DailySummaryCard)
      await wrapper.vm.$nextTick()
      await new Promise((resolve) => setTimeout(resolve, 50))

      const text = wrapper.text()
      // Should have comma-formatted numbers
      expect(text).toContain('1,234')
      expect(text).toContain('5,678')
    })

    it('should display portfolio heat change with correct color', async () => {
      vi.mocked(apiClient.get).mockResolvedValue(mockSummary)

      wrapper = mount(DailySummaryCard)
      await wrapper.vm.$nextTick()
      await new Promise((resolve) => setTimeout(resolve, 50))

      // Positive heat change should be red (increased risk)
      const heatElement = wrapper.find('[role="group"][aria-label*="heat"]')
      expect(heatElement.exists()).toBe(true)

      // Check for red color class on positive value
      const heatValue = heatElement.find('.text-red-400')
      expect(heatValue.exists()).toBe(true)
      expect(heatValue.text()).toContain('+1.2%')
    })

    it('should display negative heat change in green', async () => {
      const negativeSummary = {
        ...mockSummary,
        portfolio_heat_change: new Big('-1.5'),
      }

      vi.mocked(apiClient.get).mockResolvedValue(negativeSummary)

      wrapper = mount(DailySummaryCard)
      await wrapper.vm.$nextTick()
      await new Promise((resolve) => setTimeout(resolve, 50))

      // Negative heat change should be green (decreased risk)
      const text = wrapper.text()
      expect(text).toContain('-1.5%')

      // Find heat element specifically
      const heatGroup = wrapper.find('[aria-label*="heat"]')
      expect(heatGroup.exists()).toBe(true)
      expect(heatGroup.html()).toContain('text-green-400')
    })

    it('should format timestamp to local time', async () => {
      vi.mocked(apiClient.get).mockResolvedValue(mockSummary)

      wrapper = mount(DailySummaryCard)
      await wrapper.vm.$nextTick()
      await new Promise((resolve) => setTimeout(resolve, 50))

      // Should contain timestamp footer
      const text = wrapper.text()
      expect(text).toContain('Last updated:')
    })
  })

  describe('Loading State (AC: 8)', () => {
    it('should display loading spinner while fetching data', async () => {
      // Mock API to delay response
      vi.mocked(apiClient.get).mockImplementation(
        () =>
          new Promise((resolve) => setTimeout(() => resolve(mockSummary), 1000))
      )

      wrapper = mount(DailySummaryCard)
      await wrapper.vm.$nextTick()

      // Should show loading spinner
      expect(wrapper.find('.pi-spinner').exists()).toBe(true)
      expect(wrapper.text()).toContain('Loading summary...')
    })
  })

  describe('Error State (AC: 8)', () => {
    it('should display error message when API fails', async () => {
      const errorMessage = 'Network error: Failed to fetch'

      // Mock API to reject
      vi.mocked(apiClient.get).mockRejectedValue(new Error(errorMessage))

      wrapper = mount(DailySummaryCard)
      await wrapper.vm.$nextTick()
      await new Promise((resolve) => setTimeout(resolve, 50))

      // Should display error alert
      expect(wrapper.find('[role="alert"]').exists()).toBe(true)
      expect(wrapper.text()).toContain('Failed to load summary')
      expect(wrapper.text()).toContain(errorMessage)
    })

    it('should display error icon in error state', async () => {
      vi.mocked(apiClient.get).mockRejectedValue(new Error('API Error'))

      wrapper = mount(DailySummaryCard)
      await wrapper.vm.$nextTick()
      await new Promise((resolve) => setTimeout(resolve, 50))

      // Should have exclamation triangle icon
      expect(wrapper.find('.pi-exclamation-triangle').exists()).toBe(true)
    })
  })

  describe('Empty Suggested Actions', () => {
    it('should not render actions section when empty', async () => {
      const noActionsSummary = {
        ...mockSummary,
        suggested_actions: [],
      }

      vi.mocked(apiClient.get).mockResolvedValue(noActionsSummary)

      wrapper = mount(DailySummaryCard)
      await wrapper.vm.$nextTick()
      await new Promise((resolve) => setTimeout(resolve, 50))

      // Should NOT have "Suggested Actions" heading
      expect(wrapper.text()).not.toContain('Suggested Actions')
    })
  })

  describe('Metrics Grid Layout (AC: 7)', () => {
    it('should render all 4 metric cards', async () => {
      vi.mocked(apiClient.get).mockResolvedValue(mockSummary)

      wrapper = mount(DailySummaryCard)
      await wrapper.vm.$nextTick()
      await new Promise((resolve) => setTimeout(resolve, 50))

      // Should have 4 metric cards
      const metricCards = wrapper.findAll('.grid > div[role="group"]')
      expect(metricCards.length).toBe(4)
    })

    it('should have responsive grid classes', async () => {
      vi.mocked(apiClient.get).mockResolvedValue(mockSummary)

      wrapper = mount(DailySummaryCard)
      await wrapper.vm.$nextTick()
      await new Promise((resolve) => setTimeout(resolve, 50))

      // Should have responsive grid (2 cols on mobile, 4 on desktop)
      const grid = wrapper.find('.grid')
      expect(grid.classes()).toContain('grid-cols-2')
      expect(grid.classes()).toContain('md:grid-cols-4')
    })
  })

  describe('Accessibility (AC: 7)', () => {
    it('should have proper ARIA labels', async () => {
      vi.mocked(apiClient.get).mockResolvedValue(mockSummary)

      wrapper = mount(DailySummaryCard)
      await wrapper.vm.$nextTick()
      await new Promise((resolve) => setTimeout(resolve, 50))

      // Main region
      expect(wrapper.find('[role="region"]').attributes('aria-label')).toBe(
        'Daily Trading Summary'
      )

      // Close button
      const closeButton = wrapper.find('[aria-label="Close daily summary"]')
      expect(closeButton.exists()).toBe(true)

      // Metric groups
      expect(
        wrapper.find('[aria-label="Symbols with data metric"]').exists()
      ).toBe(true)
      expect(
        wrapper.find('[aria-label="Patterns detected metric"]').exists()
      ).toBe(true)
    })

    it('should have proper role attributes', async () => {
      vi.mocked(apiClient.get).mockResolvedValue(mockSummary)

      wrapper = mount(DailySummaryCard)
      await wrapper.vm.$nextTick()
      await new Promise((resolve) => setTimeout(resolve, 50))

      // Suggested actions should be a list
      expect(wrapper.find('[role="list"]').exists()).toBe(true)
    })
  })

  describe('Big.js Integration (AC: Story notes)', () => {
    it('should handle portfolio_heat_change as Big object', async () => {
      vi.mocked(apiClient.get).mockResolvedValue(mockSummary)

      wrapper = mount(DailySummaryCard)
      await wrapper.vm.$nextTick()
      await new Promise((resolve) => setTimeout(resolve, 50))

      // Verify Big.js object is handled correctly
      expect(wrapper.vm.summary.portfolio_heat_change).toBeInstanceOf(Big)
    })

    it('should convert string portfolio_heat_change to Big', async () => {
      const stringSummary = {
        ...mockSummary,
        portfolio_heat_change: '2.5', // String instead of Big
      }

      vi.mocked(apiClient.get).mockResolvedValue(stringSummary)

      wrapper = mount(DailySummaryCard)
      await wrapper.vm.$nextTick()
      await new Promise((resolve) => setTimeout(resolve, 50))

      // Should convert to Big object
      expect(wrapper.vm.summary.portfolio_heat_change).toBeInstanceOf(Big)
      expect(wrapper.text()).toContain('+2.5%')
    })
  })
})
