/**
 * WyckoffPhaseCompass Component Unit Tests (Feature 11)
 *
 * Test Coverage:
 * - Renders loading state initially
 * - Renders compass with mock data
 * - Shows correct phase letter
 * - Handles error state
 * - Displays recent events
 */

import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { nextTick } from 'vue'
import WyckoffPhaseCompass from '@/components/signals/WyckoffPhaseCompass.vue'
import type { PhaseStatusResponse } from '@/types/phase-status'

const mockPhaseData: PhaseStatusResponse = {
  symbol: 'AAPL',
  timeframe: '1d',
  phase: 'C',
  confidence: 0.78,
  phase_duration_bars: 22,
  progression_pct: 0.65,
  dominant_event: 'SPRING',
  recent_events: [
    { event_type: 'SC', bar_index: 145, price: 148.5, confidence: 0.82 },
    { event_type: 'SPRING', bar_index: 22, price: 147.8, confidence: 0.85 },
  ],
  bias: 'ACCUMULATION',
  updated_at: '2026-02-20T12:00:00Z',
}

// Track the mock function so tests can configure return values
const mockFetchPhaseStatus = vi.fn()

// Mock the phaseService module
vi.mock('@/services/phaseService', () => ({
  fetchPhaseStatus: (...args: unknown[]) => mockFetchPhaseStatus(...args),
}))

describe('WyckoffPhaseCompass', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('shows loading state while fetching', async () => {
    // Make fetch hang (never resolve)
    mockFetchPhaseStatus.mockReturnValue(new Promise(() => {}))

    const wrapper = mount(WyckoffPhaseCompass, {
      props: { symbol: 'AAPL' },
    })

    // Allow onMounted to run and set loading = true
    await nextTick()

    expect(wrapper.find('[data-testid="loading"]').exists()).toBe(true)
  })

  it('renders compass with data after loading', async () => {
    mockFetchPhaseStatus.mockResolvedValue(mockPhaseData)

    const wrapper = mount(WyckoffPhaseCompass, {
      props: { symbol: 'AAPL' },
    })

    await flushPromises()

    expect(wrapper.find('[data-testid="compass"]').exists()).toBe(true)
    expect(wrapper.text()).toContain('78% conf')
    expect(wrapper.text()).toContain('Testing')
    expect(wrapper.text()).toContain('22 bars in Phase C')
    expect(wrapper.text()).toContain('Accumulation')
  })

  it('shows correct phase name for phase D', async () => {
    mockFetchPhaseStatus.mockResolvedValue({ ...mockPhaseData, phase: 'D' })

    const wrapper = mount(WyckoffPhaseCompass, {
      props: { symbol: 'AAPL' },
    })

    await flushPromises()

    expect(wrapper.text()).toContain('Markup / Markdown')
  })

  it('displays error state on fetch failure', async () => {
    mockFetchPhaseStatus.mockRejectedValue(new Error('Network error'))

    const wrapper = mount(WyckoffPhaseCompass, {
      props: { symbol: 'AAPL' },
    })

    await flushPromises()

    expect(wrapper.find('[data-testid="error"]').exists()).toBe(true)
    expect(wrapper.text()).toContain('Network error')
  })

  it('displays recent events as tags', async () => {
    mockFetchPhaseStatus.mockResolvedValue(mockPhaseData)

    const wrapper = mount(WyckoffPhaseCompass, {
      props: { symbol: 'AAPL' },
    })

    await flushPromises()

    expect(wrapper.text()).toContain('SC (145b)')
    expect(wrapper.text()).toContain('SPRING (22b)')
  })
})
