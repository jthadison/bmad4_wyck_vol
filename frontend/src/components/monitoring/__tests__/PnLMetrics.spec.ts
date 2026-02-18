/* eslint-disable vue/one-component-per-file */
/**
 * PnLMetrics Component Unit Tests
 * Story 23.13 - Production Monitoring Dashboard
 */

import { describe, it, expect, afterEach } from 'vitest'
import { mount, VueWrapper } from '@vue/test-utils'
import PnLMetricsComponent from '@/components/monitoring/PnLMetrics.vue'
import PrimeVue from 'primevue/config'
import { defineComponent } from 'vue'
import type { PnLMetrics } from '@/types/monitoring'

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

const positiveMetrics: PnLMetrics = {
  daily_pnl: 500.0,
  daily_pnl_percent: 1.5,
  total_pnl: 2500.0,
  total_pnl_percent: 5.0,
  daily_loss_limit_percent: 3.0,
  winning_trades_today: 3,
  losing_trades_today: 1,
}

const negativeMetrics: PnLMetrics = {
  daily_pnl: -800.0,
  daily_pnl_percent: -2.5,
  total_pnl: -1200.0,
  total_pnl_percent: -3.0,
  daily_loss_limit_percent: 3.0,
  winning_trades_today: 1,
  losing_trades_today: 4,
}

describe('PnLMetrics', () => {
  let wrapper: VueWrapper | undefined

  const createWrapper = (metrics: PnLMetrics = positiveMetrics) => {
    return mount(PnLMetricsComponent, {
      props: { metrics },
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
    expect(wrapper.text()).toContain('P&L Metrics')
  })

  it('displays daily P&L value', () => {
    wrapper = createWrapper()
    expect(wrapper.text()).toContain('+$500.00')
  })

  it('displays total P&L value', () => {
    wrapper = createWrapper()
    expect(wrapper.text()).toContain('+$2500.00')
  })

  it('displays win/loss counts', () => {
    wrapper = createWrapper()
    expect(wrapper.text()).toContain('3W')
    expect(wrapper.text()).toContain('1L')
  })

  it('applies green color for positive P&L', () => {
    wrapper = createWrapper(positiveMetrics)
    const dailyPnl = wrapper.find('.text-green-400')
    expect(dailyPnl.exists()).toBe(true)
  })

  it('applies red color for negative P&L', () => {
    wrapper = createWrapper(negativeMetrics)
    const redElements = wrapper.findAll('.text-red-400')
    expect(redElements.length).toBeGreaterThan(0)
  })

  it('displays daily loss limit percent', () => {
    wrapper = createWrapper()
    expect(wrapper.text()).toContain('3.00%')
  })

  it('renders progress bar for daily loss tracking', () => {
    wrapper = createWrapper()
    const bar = wrapper.findComponent(ProgressBarStub)
    expect(bar.exists()).toBe(true)
  })

  it('calculates correct progress bar value for negative P&L', () => {
    wrapper = createWrapper(negativeMetrics)
    const bar = wrapper.findComponent(ProgressBarStub)
    // |−2.5| / 3.0 * 100 = 83.33
    const value = bar.props('value') as number
    expect(value).toBeCloseTo(83.33, 0)
  })
})
