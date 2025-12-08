/**
 * Integration Tests for DailySummaryCard localStorage Behavior (Story 10.3)
 *
 * Purpose:
 * --------
 * Integration tests for DailySummaryCard.vue localStorage dismissal flow:
 * - Card shows on first load (old/missing localStorage)
 * - X click updates localStorage with current date
 * - Card hidden after dismissal same day
 * - Card reappears next day (mock date change)
 *
 * Test Coverage (AC: 9):
 * -----------------------
 * - localStorage dismissal state persistence
 * - Date-based visibility logic
 * - User interaction with close button
 * - Cross-session state management
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

describe('DailySummaryCard.vue - localStorage Integration (AC: 9)', () => {
  let wrapper: VueWrapper

  const STORAGE_KEY = 'daily_summary_last_viewed'

  // Mock daily summary data
  const mockSummary: DailySummary = {
    symbols_scanned: 15,
    patterns_detected: 23,
    signals_executed: 4,
    signals_rejected: 8,
    portfolio_heat_change: new Big('1.2'),
    suggested_actions: ['Test action'],
    timestamp: '2024-03-15T14:30:00Z',
  }

  // Helper to get today's date in YYYY-MM-DD format
  function getTodayDateString(): string {
    return new Date().toISOString().split('T')[0]
  }

  // Helper to get yesterday's date in YYYY-MM-DD format
  function getYesterdayDateString(): string {
    const yesterday = new Date()
    yesterday.setDate(yesterday.getDate() - 1)
    return yesterday.toISOString().split('T')[0]
  }

  beforeEach(() => {
    // Clear localStorage before each test
    localStorage.clear()

    // Mock API to return summary
    vi.mocked(apiClient.get).mockResolvedValue(mockSummary)

    // Reset mocks
    vi.clearAllMocks()
  })

  afterEach(() => {
    if (wrapper) {
      wrapper.unmount()
    }
  })

  describe('First Load Behavior (AC: 1, 2)', () => {
    it('should show card on first load (no localStorage entry)', async () => {
      // Ensure no localStorage entry
      expect(localStorage.getItem(STORAGE_KEY)).toBeNull()

      wrapper = mount(DailySummaryCard)
      await wrapper.vm.$nextTick()
      await new Promise((resolve) => setTimeout(resolve, 50))

      // Card should be visible
      expect(wrapper.vm.shouldShowCard).toBe(true)
      expect(wrapper.find('[role="region"]').exists()).toBe(true)
    })

    it('should show card when localStorage has old date', async () => {
      // Set localStorage to yesterday
      const yesterday = getYesterdayDateString()
      localStorage.setItem(STORAGE_KEY, yesterday)

      wrapper = mount(DailySummaryCard)
      await wrapper.vm.$nextTick()
      await new Promise((resolve) => setTimeout(resolve, 50))

      // Card should be visible
      expect(wrapper.vm.shouldShowCard).toBe(true)
      expect(wrapper.find('[role="region"]').exists()).toBe(true)
    })

    it('should NOT show card when localStorage has today date', async () => {
      // Set localStorage to today
      const today = getTodayDateString()
      localStorage.setItem(STORAGE_KEY, today)

      wrapper = mount(DailySummaryCard)
      await wrapper.vm.$nextTick()
      await new Promise((resolve) => setTimeout(resolve, 50))

      // Card should NOT be visible
      expect(wrapper.vm.shouldShowCard).toBe(false)
      expect(wrapper.find('[role="region"]').exists()).toBe(false)
    })
  })

  describe('Dismissal Behavior (AC: 2)', () => {
    it('should update localStorage when close button clicked', async () => {
      // Ensure clean state
      expect(localStorage.getItem(STORAGE_KEY)).toBeNull()

      wrapper = mount(DailySummaryCard)
      await wrapper.vm.$nextTick()
      await new Promise((resolve) => setTimeout(resolve, 50))

      // Card should be visible
      expect(wrapper.vm.shouldShowCard).toBe(true)

      // Click close button
      const closeButton = wrapper.find('[aria-label="Close daily summary"]')
      expect(closeButton.exists()).toBe(true)
      await closeButton.trigger('click')

      // localStorage should now have today's date
      const storedDate = localStorage.getItem(STORAGE_KEY)
      expect(storedDate).toBe(getTodayDateString())
    })

    it('should hide card after dismissal', async () => {
      wrapper = mount(DailySummaryCard)
      await wrapper.vm.$nextTick()
      await new Promise((resolve) => setTimeout(resolve, 50))

      // Card should be visible
      expect(wrapper.find('[role="region"]').exists()).toBe(true)

      // Click close button
      const closeButton = wrapper.find('[aria-label="Close daily summary"]')
      await closeButton.trigger('click')
      await wrapper.vm.$nextTick()

      // Card should now be hidden
      expect(wrapper.vm.shouldShowCard).toBe(false)
      expect(wrapper.find('[role="region"]').exists()).toBe(false)
    })

    it('should NOT reappear same day after dismissal', async () => {
      // First mount - card visible
      wrapper = mount(DailySummaryCard)
      await wrapper.vm.$nextTick()
      await new Promise((resolve) => setTimeout(resolve, 50))
      expect(wrapper.vm.shouldShowCard).toBe(true)

      // Dismiss card
      const closeButton = wrapper.find('[aria-label="Close daily summary"]')
      await closeButton.trigger('click')
      await wrapper.vm.$nextTick()
      expect(wrapper.vm.shouldShowCard).toBe(false)

      // Unmount
      wrapper.unmount()

      // Second mount (same day) - card should NOT appear
      wrapper = mount(DailySummaryCard)
      await wrapper.vm.$nextTick()
      await new Promise((resolve) => setTimeout(resolve, 50))
      expect(wrapper.vm.shouldShowCard).toBe(false)
      expect(wrapper.find('[role="region"]').exists()).toBe(false)
    })
  })

  describe('Next Day Behavior (AC: 2)', () => {
    it('should reappear next day (simulated date change)', async () => {
      // Simulate: User dismissed card "yesterday"
      const yesterday = getYesterdayDateString()
      localStorage.setItem(STORAGE_KEY, yesterday)

      // Mount component "today"
      wrapper = mount(DailySummaryCard)
      await wrapper.vm.$nextTick()
      await new Promise((resolve) => setTimeout(resolve, 50))

      // Card should be visible (yesterday !== today)
      expect(wrapper.vm.shouldShowCard).toBe(true)
      expect(wrapper.find('[role="region"]').exists()).toBe(true)
    })

    it('should fetch fresh summary data on next day', async () => {
      // Set localStorage to yesterday
      const yesterday = getYesterdayDateString()
      localStorage.setItem(STORAGE_KEY, yesterday)

      wrapper = mount(DailySummaryCard)
      await wrapper.vm.$nextTick()
      await new Promise((resolve) => setTimeout(resolve, 50))

      // Should have called API to fetch fresh data
      expect(apiClient.get).toHaveBeenCalledWith('/summary/daily')
      expect(apiClient.get).toHaveBeenCalledTimes(1)
    })
  })

  describe('localStorage Date Format (AC: 1)', () => {
    it('should store date in YYYY-MM-DD format', async () => {
      wrapper = mount(DailySummaryCard)
      await wrapper.vm.$nextTick()
      await new Promise((resolve) => setTimeout(resolve, 50))

      // Dismiss card
      const closeButton = wrapper.find('[aria-label="Close daily summary"]')
      await closeButton.trigger('click')

      // Check stored format
      const storedDate = localStorage.getItem(STORAGE_KEY)
      expect(storedDate).toMatch(/^\d{4}-\d{2}-\d{2}$/)
    })
  })

  describe('Cross-Session State (AC: 2)', () => {
    it('should persist dismissal state across component remounts', async () => {
      // First session - show and dismiss
      wrapper = mount(DailySummaryCard)
      await wrapper.vm.$nextTick()
      await new Promise((resolve) => setTimeout(resolve, 50))

      const closeButton = wrapper.find('[aria-label="Close daily summary"]')
      await closeButton.trigger('click')
      wrapper.unmount()

      // Second session - should NOT show
      wrapper = mount(DailySummaryCard)
      await wrapper.vm.$nextTick()
      await new Promise((resolve) => setTimeout(resolve, 50))

      expect(wrapper.vm.shouldShowCard).toBe(false)
    })

    it('should NOT fetch API if card should not be shown', async () => {
      // Set localStorage to today (already dismissed)
      const today = getTodayDateString()
      localStorage.setItem(STORAGE_KEY, today)

      wrapper = mount(DailySummaryCard)
      await wrapper.vm.$nextTick()
      await new Promise((resolve) => setTimeout(resolve, 50))

      // Should NOT have called API (card hidden)
      expect(apiClient.get).not.toHaveBeenCalled()
    })
  })

  describe('Edge Cases', () => {
    it('should handle malformed localStorage date gracefully', async () => {
      // Set malformed date
      localStorage.setItem(STORAGE_KEY, 'invalid-date')

      wrapper = mount(DailySummaryCard)
      await wrapper.vm.$nextTick()
      await new Promise((resolve) => setTimeout(resolve, 50))

      // Should treat as "not today" and show card
      expect(wrapper.vm.shouldShowCard).toBe(true)
    })

    it('should handle future dates in localStorage', async () => {
      // Set future date
      const future = new Date()
      future.setDate(future.getDate() + 7)
      const futureDate = future.toISOString().split('T')[0]
      localStorage.setItem(STORAGE_KEY, futureDate)

      wrapper = mount(DailySummaryCard)
      await wrapper.vm.$nextTick()
      await new Promise((resolve) => setTimeout(resolve, 50))

      // Should show card (future date !== today)
      expect(wrapper.vm.shouldShowCard).toBe(true)
    })

    it('should overwrite old localStorage date on dismissal', async () => {
      // Set old date
      localStorage.setItem(STORAGE_KEY, '2023-01-01')

      wrapper = mount(DailySummaryCard)
      await wrapper.vm.$nextTick()
      await new Promise((resolve) => setTimeout(resolve, 50))

      // Dismiss
      const closeButton = wrapper.find('[aria-label="Close daily summary"]')
      await closeButton.trigger('click')

      // Should now have today's date
      const storedDate = localStorage.getItem(STORAGE_KEY)
      expect(storedDate).toBe(getTodayDateString())
      expect(storedDate).not.toBe('2023-01-01')
    })
  })
})
