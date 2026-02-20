/**
 * VolumeProfileByPhase Component Unit Tests (P3-F13)
 *
 * Test Coverage:
 * - Renders loading state
 * - Renders with mock data in combined mode
 * - Toggles between combined and per-phase modes
 * - Shows correct number of phase cards in per-phase mode
 * - Displays legend with phase colors
 * - Shows error state on fetch failure
 */

import { describe, it, expect, afterEach, vi, beforeEach } from 'vitest'
import { mount, VueWrapper, flushPromises } from '@vue/test-utils'
import VolumeProfileByPhase from '@/components/charts/VolumeProfileByPhase.vue'
import type { VolumeProfileResponse } from '@/types/volume-profile'

// Mock the service
vi.mock('@/services/volumeProfileService', () => ({
  fetchVolumeProfile: vi.fn(),
}))

import { fetchVolumeProfile } from '@/services/volumeProfileService'
const mockFetch = vi.mocked(fetchVolumeProfile)

// Helper: create mock volume profile response
function createMockResponse(
  overrides?: Partial<VolumeProfileResponse>
): VolumeProfileResponse {
  const bins = Array.from({ length: 5 }, (_, i) => ({
    price_level: 100 + i * 2,
    price_low: 99 + i * 2,
    price_high: 101 + i * 2,
    volume: 1000 * (i + 1),
    pct_of_phase_volume: 0.2,
    is_poc: i === 2,
    in_value_area: i >= 1 && i <= 3,
  }))

  return {
    symbol: 'TEST',
    timeframe: '1d',
    price_range_low: 99,
    price_range_high: 111,
    bin_width: 2.4,
    num_bins: 5,
    phases: [
      {
        phase: 'A',
        bins,
        poc_price: 104,
        total_volume: 15000,
        bar_count: 30,
        value_area_low: 101,
        value_area_high: 107,
      },
      {
        phase: 'B',
        bins,
        poc_price: 106,
        total_volume: 25000,
        bar_count: 70,
        value_area_low: 103,
        value_area_high: 109,
      },
      {
        phase: 'C',
        bins,
        poc_price: 102,
        total_volume: 8000,
        bar_count: 30,
        value_area_low: 100,
        value_area_high: 105,
      },
    ],
    combined: {
      phase: 'COMBINED',
      bins,
      poc_price: 105,
      total_volume: 48000,
      bar_count: 130,
      value_area_low: 101,
      value_area_high: 109,
    },
    current_price: 106.5,
    data_source: 'MOCK' as const,
    ...overrides,
  }
}

describe('VolumeProfileByPhase.vue', () => {
  let wrapper: VueWrapper

  afterEach(() => {
    if (wrapper) {
      wrapper.unmount()
    }
    vi.clearAllMocks()
  })

  describe('Loading State', () => {
    it('should show loading message while fetching', async () => {
      // Make fetch never resolve
      mockFetch.mockReturnValue(new Promise(() => {}))

      wrapper = mount(VolumeProfileByPhase, {
        props: { symbol: 'AAPL' },
      })
      // Wait for onMounted async to start and set loading = true
      await wrapper.vm.$nextTick()

      expect(wrapper.find('.vp-loading').exists()).toBe(true)
      expect(wrapper.text()).toContain('Loading')
    })
  })

  describe('Combined Mode (default)', () => {
    beforeEach(async () => {
      mockFetch.mockResolvedValue(createMockResponse())
      wrapper = mount(VolumeProfileByPhase, {
        props: { symbol: 'AAPL' },
      })
      await flushPromises()
    })

    it('should render SVG chart', () => {
      expect(wrapper.find('.vp-svg').exists()).toBe(true)
    })

    it('should render combined bars', () => {
      const bars = wrapper.findAll('.vp-bar')
      expect(bars.length).toBe(5) // num_bins = 5
    })

    it('should render POC line', () => {
      expect(wrapper.find('.vp-poc-line').exists()).toBe(true)
    })

    it('should render POC label', () => {
      expect(wrapper.find('.vp-poc-label').exists()).toBe(true)
    })

    it('should have combined mode button active by default', () => {
      const buttons = wrapper.findAll('.vp-mode-btn')
      expect(buttons[0].classes()).toContain('active')
      expect(buttons[1].classes()).not.toContain('active')
    })

    it('should display legend with all phases', () => {
      const legendItems = wrapper.findAll('.vp-legend-item')
      expect(legendItems.length).toBe(3) // A, B, C
    })
  })

  describe('Per-Phase Mode', () => {
    beforeEach(async () => {
      mockFetch.mockResolvedValue(createMockResponse())
      wrapper = mount(VolumeProfileByPhase, {
        props: { symbol: 'AAPL' },
      })
      await flushPromises()
    })

    it('should toggle to per-phase mode on click', async () => {
      const buttons = wrapper.findAll('.vp-mode-btn')
      await buttons[1].trigger('click')

      expect(buttons[1].classes()).toContain('active')
      expect(wrapper.find('.vp-phases-grid').exists()).toBe(true)
    })

    it('should show one card per phase', async () => {
      const buttons = wrapper.findAll('.vp-mode-btn')
      await buttons[1].trigger('click')

      const cards = wrapper.findAll('.vp-phase-card')
      expect(cards.length).toBe(3) // A, B, C
    })

    it('should display phase names in cards', async () => {
      const buttons = wrapper.findAll('.vp-mode-btn')
      await buttons[1].trigger('click')

      expect(wrapper.text()).toContain('Phase A')
      expect(wrapper.text()).toContain('Phase B')
      expect(wrapper.text()).toContain('Phase C')
    })

    it('should display bar counts per phase', async () => {
      const buttons = wrapper.findAll('.vp-mode-btn')
      await buttons[1].trigger('click')

      expect(wrapper.text()).toContain('30 bars')
      expect(wrapper.text()).toContain('70 bars')
    })
  })

  describe('Error State', () => {
    it('should display error message on fetch failure', async () => {
      mockFetch.mockRejectedValue(new Error('Network error'))

      wrapper = mount(VolumeProfileByPhase, {
        props: { symbol: 'AAPL' },
      })
      await flushPromises()

      expect(wrapper.find('.vp-error').exists()).toBe(true)
      expect(wrapper.text()).toContain('Network error')
    })
  })

  describe('Props Handling', () => {
    it('should call fetchVolumeProfile with correct params', async () => {
      mockFetch.mockResolvedValue(createMockResponse())

      wrapper = mount(VolumeProfileByPhase, {
        props: {
          symbol: 'SPY',
          timeframe: '1h',
          bars: 100,
          numBins: 30,
        },
      })
      await flushPromises()

      expect(mockFetch).toHaveBeenCalledWith('SPY', '1h', 100, 30)
    })

    it('should use default props when not specified', async () => {
      mockFetch.mockResolvedValue(createMockResponse())

      wrapper = mount(VolumeProfileByPhase, {
        props: { symbol: 'AAPL' },
      })
      await flushPromises()

      expect(mockFetch).toHaveBeenCalledWith('AAPL', '1d', 200, 50)
    })
  })
})
