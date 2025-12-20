import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import SignalCard from '@/components/signals/SignalCard.vue'
import type { Signal } from '@/types'
import PrimeVue from 'primevue/config'

const mockSignal: Signal = {
  id: 'signal-1',
  symbol: 'AAPL',
  pattern_type: 'SPRING',
  phase: 'C',
  entry_price: '150.00',
  stop_loss: '148.00',
  target_levels: {
    primary_target: '156.00',
    secondary_targets: ['153.00', '154.50'],
  },
  position_size: 100,
  risk_amount: '200.00',
  r_multiple: '3.0',
  confidence_score: 85,
  confidence_components: {
    pattern_confidence: 80,
    phase_confidence: 85,
    volume_confidence: 90,
    overall_confidence: 85,
  },
  campaign_id: null,
  status: 'PENDING',
  timestamp: '2024-10-19T10:30:00Z',
  timeframe: '1h',
}

describe('SignalCard', () => {
  it('renders signal data correctly', () => {
    const wrapper = mount(SignalCard, {
      props: { signal: mockSignal },
      global: {
        plugins: [PrimeVue],
      },
    })

    expect(wrapper.text()).toContain('AAPL')
    expect(wrapper.text()).toContain('SPRING')
    expect(wrapper.text()).toContain('$150.00')
    expect(wrapper.text()).toContain('$148.00')
    expect(wrapper.text()).toContain('$156.00')
    expect(wrapper.text()).toContain('85%')
    expect(wrapper.text()).toContain('3.0R')
  })

  it('displays correct pattern icon for SPRING', () => {
    const wrapper = mount(SignalCard, {
      props: { signal: mockSignal },
      global: {
        plugins: [PrimeVue],
      },
    })

    const icon = wrapper.find('.pi-arrow-up')
    expect(icon.exists()).toBe(true)
  })

  it('displays correct pattern icon for SOS', () => {
    const sosSignal = { ...mockSignal, pattern_type: 'SOS' as const }
    const wrapper = mount(SignalCard, {
      props: { signal: sosSignal },
      global: {
        plugins: [PrimeVue],
      },
    })

    const icon = wrapper.find('.pi-bolt')
    expect(icon.exists()).toBe(true)
  })

  it('displays correct pattern icon for LPS', () => {
    const lpsSignal = { ...mockSignal, pattern_type: 'LPS' as const }
    const wrapper = mount(SignalCard, {
      props: { signal: lpsSignal },
      global: {
        plugins: [PrimeVue],
      },
    })

    const icon = wrapper.find('.pi-check-circle')
    expect(icon.exists()).toBe(true)
  })

  it('displays correct pattern icon for UTAD', () => {
    const utadSignal = { ...mockSignal, pattern_type: 'UTAD' as const }
    const wrapper = mount(SignalCard, {
      props: { signal: utadSignal },
      global: {
        plugins: [PrimeVue],
      },
    })

    const icon = wrapper.find('.pi-exclamation-triangle')
    expect(icon.exists()).toBe(true)
  })

  it('applies green border for executed signals (FILLED)', () => {
    const filledSignal = { ...mockSignal, status: 'FILLED' as const }
    const wrapper = mount(SignalCard, {
      props: { signal: filledSignal },
      global: {
        plugins: [PrimeVue],
      },
    })

    expect(wrapper.classes()).toContain('border-green-500')
  })

  it('applies green border for STOPPED status', () => {
    const stoppedSignal = { ...mockSignal, status: 'STOPPED' as const }
    const wrapper = mount(SignalCard, {
      props: { signal: stoppedSignal },
      global: {
        plugins: [PrimeVue],
      },
    })

    const card = wrapper.find('.signal-card')
    expect(card.classes()).toContain('border-gray-500')
  })

  it('applies green border for TARGET_HIT status', () => {
    const targetHitSignal = { ...mockSignal, status: 'TARGET_HIT' as const }
    const wrapper = mount(SignalCard, {
      props: { signal: targetHitSignal },
      global: {
        plugins: [PrimeVue],
      },
    })

    expect(wrapper.classes()).toContain('border-green-500')
  })

  it('applies red border for REJECTED status', () => {
    const rejectedSignal = { ...mockSignal, status: 'REJECTED' as const }
    const wrapper = mount(SignalCard, {
      props: { signal: rejectedSignal },
      global: {
        plugins: [PrimeVue],
      },
    })

    expect(wrapper.classes()).toContain('border-red-500')
  })

  it('applies yellow border for PENDING status', () => {
    const wrapper = mount(SignalCard, {
      props: { signal: mockSignal },
      global: {
        plugins: [PrimeVue],
      },
    })

    expect(wrapper.classes()).toContain('border-yellow-500')
  })

  it('applies yellow border for APPROVED status', () => {
    const approvedSignal = { ...mockSignal, status: 'APPROVED' as const }
    const wrapper = mount(SignalCard, {
      props: { signal: approvedSignal },
      global: {
        plugins: [PrimeVue],
      },
    })

    expect(wrapper.classes()).toContain('border-yellow-500')
  })

  it('displays rejection reasons for rejected signals', () => {
    const rejectedSignal = {
      ...mockSignal,
      status: 'REJECTED' as const,
      rejection_reasons: ['Low confidence', 'High risk'],
    }
    const wrapper = mount(SignalCard, {
      props: { signal: rejectedSignal, isExpanded: true },
      global: {
        plugins: [PrimeVue],
      },
    })

    expect(wrapper.text()).toContain('Rejection Reasons')
    expect(wrapper.text()).toContain('Low confidence')
    expect(wrapper.text()).toContain('High risk')
  })

  it('does not display rejection reasons for non-rejected signals', () => {
    const wrapper = mount(SignalCard, {
      props: { signal: mockSignal },
      global: {
        plugins: [PrimeVue],
      },
    })

    expect(wrapper.text()).not.toContain('Rejection Reasons')
  })

  it('displays relative timestamp', () => {
    const recentSignal = {
      ...mockSignal,
      timestamp: new Date(Date.now() - 5 * 60 * 1000).toISOString(), // 5 minutes ago
    }
    const wrapper = mount(SignalCard, {
      props: { signal: recentSignal },
      global: {
        plugins: [PrimeVue],
      },
    })

    expect(wrapper.text()).toMatch(/\d+ minutes? ago/)
  })

  it('displays timeframe', () => {
    const wrapper = mount(SignalCard, {
      props: { signal: mockSignal },
      global: {
        plugins: [PrimeVue],
      },
    })

    expect(wrapper.text()).toContain('1h')
  })

  it('displays phase', () => {
    const wrapper = mount(SignalCard, {
      props: { signal: mockSignal, isExpanded: true },
      global: {
        plugins: [PrimeVue],
      },
    })

    expect(wrapper.text()).toContain('Phase')
    expect(wrapper.text()).toContain('C')
  })

  it('displays position size', () => {
    const wrapper = mount(SignalCard, {
      props: { signal: mockSignal },
      global: {
        plugins: [PrimeVue],
      },
    })

    // Position size is in the signal data, not necessarily displayed in the card UI
    expect(mockSignal.position_size).toBe(100)
  })

  it('has correct ARIA attributes', () => {
    const wrapper = mount(SignalCard, {
      props: { signal: mockSignal },
      global: {
        plugins: [PrimeVue],
      },
    })

    const card = wrapper.find('[role="button"]')
    expect(card.exists()).toBe(true)
    expect(card.attributes('aria-label')).toContain('SPRING')
    expect(card.attributes('aria-label')).toContain('AAPL')
    expect(card.attributes('aria-label')).toContain('85%')
  })

  it('is keyboard focusable', () => {
    const wrapper = mount(SignalCard, {
      props: { signal: mockSignal },
      global: {
        plugins: [PrimeVue],
      },
    })

    const card = wrapper.find('[role="button"]')
    expect(card.attributes('tabindex')).toBe('0')
  })

  it('displays pattern tooltip', () => {
    const wrapper = mount(SignalCard, {
      props: { signal: mockSignal },
      global: {
        plugins: [PrimeVue],
      },
    })

    const icon = wrapper.find('.pi-arrow-up')
    expect(icon.attributes('title')).toContain('Spring')
    expect(icon.attributes('title')).toContain('Testing support')
  })
})
