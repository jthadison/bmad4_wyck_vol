/**
 * LivePositionCard Component Unit Tests
 *
 * Feature P4-I15 (Live Position Management)
 *
 * Test Coverage:
 * - Renders position data correctly
 * - Pattern badge shows correct type
 * - P&L shows green when positive, red when negative
 * - Stop adjustment emits correct event
 * - Partial exit buttons trigger correct events
 */

import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import LivePositionCard from '@/components/positions/LivePositionCard.vue'
import type { EnrichedPosition } from '@/services/livePositionsService'

const mockPosition: EnrichedPosition = {
  id: 'pos-1',
  campaign_id: 'camp-1',
  signal_id: 'sig-1',
  symbol: 'AAPL',
  timeframe: '1h',
  pattern_type: 'SPRING',
  entry_price: '150.00',
  current_price: '155.00',
  stop_loss: '145.00',
  shares: '100',
  current_pnl: '500.00',
  status: 'OPEN',
  entry_date: '2026-02-20T10:00:00Z',
  stop_distance_pct: '6.45',
  r_multiple: '1.00',
  dollars_at_risk: '500.00',
  pnl_pct: '3.33',
}

const negativePosition: EnrichedPosition = {
  ...mockPosition,
  id: 'pos-2',
  current_price: '148.00',
  current_pnl: '-200.00',
  pnl_pct: '-1.33',
  r_multiple: '-0.40',
}

describe('LivePositionCard', () => {
  it('renders position symbol and pattern badge', () => {
    const wrapper = mount(LivePositionCard, {
      props: { position: mockPosition, isActing: false },
    })
    expect(wrapper.text()).toContain('AAPL')
    const badge = wrapper.find('[data-testid="pattern-badge"]')
    expect(badge.exists()).toBe(true)
    expect(badge.text()).toBe('SPRING')
  })

  it('shows entry, current, and stop prices', () => {
    const wrapper = mount(LivePositionCard, {
      props: { position: mockPosition, isActing: false },
    })
    expect(wrapper.text()).toContain('150.00')
    expect(wrapper.text()).toContain('155.00')
    expect(wrapper.text()).toContain('145.00')
  })

  it('shows green P&L when positive', () => {
    const wrapper = mount(LivePositionCard, {
      props: { position: mockPosition, isActing: false },
    })
    const pnl = wrapper.find('[data-testid="pnl-display"]')
    expect(pnl.classes()).toContain('text-green-400')
  })

  it('shows red P&L when negative', () => {
    const wrapper = mount(LivePositionCard, {
      props: { position: negativePosition, isActing: false },
    })
    const pnl = wrapper.find('[data-testid="pnl-display"]')
    expect(pnl.classes()).toContain('text-red-400')
  })

  it('emits updateStop when stop input submitted', async () => {
    const wrapper = mount(LivePositionCard, {
      props: { position: mockPosition, isActing: false },
    })
    const input = wrapper.find('[data-testid="stop-input"]')
    await input.setValue('147.00')

    const btn = wrapper.find('[data-testid="update-stop-btn"]')
    await btn.trigger('click')

    expect(wrapper.emitted('updateStop')).toBeTruthy()
    expect(wrapper.emitted('updateStop')![0]).toEqual(['pos-1', '147.00'])
  })

  it('emits partialExit with 25%', async () => {
    const wrapper = mount(LivePositionCard, {
      props: { position: mockPosition, isActing: false },
    })
    const btn = wrapper.find('[data-testid="exit-25-btn"]')
    await btn.trigger('click')

    expect(wrapper.emitted('partialExit')).toBeTruthy()
    expect(wrapper.emitted('partialExit')![0]).toEqual(['pos-1', 25])
  })

  it('emits partialExit with 50%', async () => {
    const wrapper = mount(LivePositionCard, {
      props: { position: mockPosition, isActing: false },
    })
    const btn = wrapper.find('[data-testid="exit-50-btn"]')
    await btn.trigger('click')

    expect(wrapper.emitted('partialExit')).toBeTruthy()
    expect(wrapper.emitted('partialExit')![0]).toEqual(['pos-1', 50])
  })

  it('emits partialExit with 100%', async () => {
    const wrapper = mount(LivePositionCard, {
      props: { position: mockPosition, isActing: false },
    })
    const btn = wrapper.find('[data-testid="exit-100-btn"]')
    await btn.trigger('click')

    expect(wrapper.emitted('partialExit')).toBeTruthy()
    expect(wrapper.emitted('partialExit')![0]).toEqual(['pos-1', 100])
  })

  it('disables buttons when isActing is true', () => {
    const wrapper = mount(LivePositionCard, {
      props: { position: mockPosition, isActing: true },
    })
    const btn = wrapper.find('[data-testid="exit-25-btn"]')
    expect((btn.element as HTMLButtonElement).disabled).toBe(true)
  })

  it('shows R-multiple and dollars at risk', () => {
    const wrapper = mount(LivePositionCard, {
      props: { position: mockPosition, isActing: false },
    })
    expect(wrapper.text()).toContain('1.00')
    expect(wrapper.text()).toContain('500.00')
  })

  it('shows phase label for SPRING pattern', () => {
    const wrapper = mount(LivePositionCard, {
      props: { position: mockPosition, isActing: false },
    })
    expect(wrapper.text()).toContain('Phase C')
  })
})
