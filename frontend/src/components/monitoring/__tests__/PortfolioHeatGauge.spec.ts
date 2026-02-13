/* eslint-disable vue/one-component-per-file */
/**
 * PortfolioHeatGauge Component Unit Tests
 * Story 23.13 - Production Monitoring Dashboard
 */

import { describe, it, expect, afterEach } from 'vitest'
import { mount, VueWrapper } from '@vue/test-utils'
import PortfolioHeatGauge from '@/components/monitoring/PortfolioHeatGauge.vue'
import PrimeVue from 'primevue/config'
import { defineComponent } from 'vue'

const CardStub = defineComponent({
  name: 'PCard',
  template: `
    <div class="p-card">
      <div class="p-card-title"><slot name="title" /></div>
      <div class="p-card-content"><slot name="content" /></div>
    </div>
  `,
})

const ProgressBarStub = defineComponent({
  name: 'PProgressBar',
  props: {
    value: { type: Number, default: 0 },
    showValue: { type: Boolean, default: true },
  },
  template: `<div class="p-progressbar" :data-value="value"></div>`,
})

describe('PortfolioHeatGauge', () => {
  let wrapper: VueWrapper | undefined

  const createWrapper = (heatPercent = 5.0, heatLimit = 10.0) => {
    return mount(PortfolioHeatGauge, {
      props: { heatPercent, heatLimit },
      global: {
        plugins: [PrimeVue],
        stubs: {
          Card: CardStub,
          ProgressBar: ProgressBarStub,
        },
      },
    })
  }

  afterEach(() => {
    if (wrapper) wrapper.unmount()
  })

  it('renders component title', () => {
    wrapper = createWrapper()
    expect(wrapper.text()).toContain('Portfolio Heat')
  })

  it('displays heat percentage', () => {
    wrapper = createWrapper(5.0)
    expect(wrapper.text()).toContain('5.0%')
  })

  it('displays heat limit', () => {
    wrapper = createWrapper(5.0, 10.0)
    expect(wrapper.text()).toContain('Limit: 10%')
  })

  it('applies green styling for safe zone (< 7%)', () => {
    wrapper = createWrapper(3.0)
    expect(wrapper.find('.text-green-400').exists()).toBe(true)
  })

  it('applies yellow styling for warning zone (7-9%)', () => {
    wrapper = createWrapper(8.0)
    expect(wrapper.find('.text-yellow-400').exists()).toBe(true)
  })

  it('applies red styling for danger zone (9-10%)', () => {
    wrapper = createWrapper(9.5)
    expect(wrapper.find('.text-red-400').exists()).toBe(true)
  })

  it('applies pulsing red for critical zone (> 10%)', () => {
    wrapper = createWrapper(11.0)
    const critical = wrapper.find('.text-red-500.animate-pulse')
    expect(critical.exists()).toBe(true)
  })

  it('calculates correct progress bar value', () => {
    wrapper = createWrapper(5.0, 10.0)
    const bar = wrapper.findComponent(ProgressBarStub)
    expect(bar.props('value')).toBe(50)
  })

  it('caps progress bar at 100%', () => {
    wrapper = createWrapper(12.0, 10.0)
    const bar = wrapper.findComponent(ProgressBarStub)
    expect(bar.props('value')).toBe(100)
  })

  it('applies correct bar class for safe zone', () => {
    wrapper = createWrapper(3.0)
    const bar = wrapper.findComponent(ProgressBarStub)
    expect(bar.classes()).toContain('heat-bar-safe')
  })

  it('applies correct bar class for warning zone', () => {
    wrapper = createWrapper(7.5)
    const bar = wrapper.findComponent(ProgressBarStub)
    expect(bar.classes()).toContain('heat-bar-warning')
  })
})
