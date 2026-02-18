/* eslint-disable vue/one-component-per-file */
/**
 * ActiveSignals Component Unit Tests
 * Story 23.13 - Production Monitoring Dashboard
 */

import { describe, it, expect, afterEach } from 'vitest'
import { mount, VueWrapper } from '@vue/test-utils'
import ActiveSignals from '@/components/monitoring/ActiveSignals.vue'
import PrimeVue from 'primevue/config'
import { defineComponent } from 'vue'
import type { ActiveSignalSummary } from '@/types/monitoring'

const CardStub = defineComponent({
  name: 'PCard',
  template: `
    <div class="p-card">
      <div class="p-card-title"><slot name="title" /></div>
      <div class="p-card-content"><slot name="content" /></div>
    </div>
  `,
})

const BadgeStub = defineComponent({
  name: 'PBadge',
  props: {
    value: { type: [String, Number], default: '' },
    severity: { type: String, default: '' },
  },
  template: `<span class="p-badge" :data-severity="severity">{{ value }}</span>`,
})

const mockSignals: ActiveSignalSummary[] = [
  {
    signal_id: 'sig-001',
    symbol: 'AAPL',
    pattern_type: 'SPRING',
    confidence: 85,
    timestamp: '2026-02-10T14:30:00Z',
    status: 'PENDING',
  },
  {
    signal_id: 'sig-002',
    symbol: 'MSFT',
    pattern_type: 'UTAD',
    confidence: 72,
    timestamp: '2026-02-10T14:45:00Z',
    status: 'APPROVED',
  },
]

describe('ActiveSignals', () => {
  let wrapper: VueWrapper | undefined

  const createWrapper = (signals: ActiveSignalSummary[] = mockSignals) => {
    return mount(ActiveSignals, {
      props: { signals },
      global: {
        plugins: [PrimeVue],
        stubs: {
          Card: CardStub,
          Badge: BadgeStub,
        },
      },
    })
  }

  afterEach(() => {
    if (wrapper) wrapper.unmount()
  })

  it('renders component title', () => {
    wrapper = createWrapper()
    expect(wrapper.text()).toContain('Active Signals')
  })

  it('displays signal count in badge', () => {
    wrapper = createWrapper()
    const badges = wrapper.findAllComponents(BadgeStub)
    const countBadge = badges.find((b) => b.props('value') === 2)
    expect(countBadge).toBeTruthy()
  })

  it('shows empty state when no signals', () => {
    wrapper = createWrapper([])
    expect(wrapper.text()).toContain('No active signals')
  })

  it('renders signal symbols', () => {
    wrapper = createWrapper()
    expect(wrapper.text()).toContain('AAPL')
    expect(wrapper.text()).toContain('MSFT')
  })

  it('renders signal pattern types as badges', () => {
    wrapper = createWrapper()
    const badges = wrapper.findAllComponents(BadgeStub)
    const springBadge = badges.find((b) => b.props('value') === 'SPRING')
    const utadBadge = badges.find((b) => b.props('value') === 'UTAD')
    expect(springBadge).toBeTruthy()
    expect(utadBadge).toBeTruthy()
  })

  it('displays confidence percentages', () => {
    wrapper = createWrapper()
    expect(wrapper.text()).toContain('85%')
    expect(wrapper.text()).toContain('72%')
  })

  it('applies correct severity for SPRING pattern (success)', () => {
    wrapper = createWrapper()
    const badges = wrapper.findAllComponents(BadgeStub)
    const springBadge = badges.find((b) => b.props('value') === 'SPRING')
    expect(springBadge?.props('severity')).toBe('success')
  })

  it('applies correct severity for UTAD pattern (danger)', () => {
    wrapper = createWrapper()
    const badges = wrapper.findAllComponents(BadgeStub)
    const utadBadge = badges.find((b) => b.props('value') === 'UTAD')
    expect(utadBadge?.props('severity')).toBe('danger')
  })
})
