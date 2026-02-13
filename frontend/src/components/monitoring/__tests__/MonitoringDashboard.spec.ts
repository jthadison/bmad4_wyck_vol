/* eslint-disable vue/one-component-per-file */
/**
 * MonitoringDashboard Component Unit Tests
 * Story 23.13 - Production Monitoring Dashboard
 */

import { describe, it, expect, afterEach, vi, beforeEach } from 'vitest'
import { mount, VueWrapper, flushPromises } from '@vue/test-utils'
import MonitoringDashboard from '@/components/monitoring/MonitoringDashboard.vue'
import PrimeVue from 'primevue/config'
import { defineComponent } from 'vue'
import type { DashboardData } from '@/types/monitoring'

vi.mock('@/services/monitoringApi', () => ({
  getDashboardData: vi.fn(),
}))

import { getDashboardData } from '@/services/monitoringApi'

const mockDashboardData: DashboardData = {
  portfolio_heat_percent: 5.5,
  portfolio_heat_limit: 10.0,
  positions_by_broker: {
    Alpaca: [
      {
        broker: 'Alpaca',
        symbol: 'AAPL',
        side: 'LONG' as const,
        size: 100,
        entry_price: 150.0,
        current_price: 155.0,
        unrealized_pnl: 500.0,
        campaign_id: null,
      },
    ],
  },
  pnl_metrics: {
    daily_pnl: 250.0,
    daily_pnl_percent: 0.5,
    total_pnl: 1200.0,
    total_pnl_percent: 2.4,
    daily_loss_limit_percent: 3.0,
    winning_trades_today: 2,
    losing_trades_today: 1,
  },
  active_signals: [
    {
      signal_id: 'sig-001',
      symbol: 'AAPL',
      pattern_type: 'SPRING',
      confidence: 85,
      timestamp: '2026-02-10T14:30:00Z',
      status: 'PENDING',
    },
  ],
  kill_switch_active: false,
  last_updated: '2026-02-10T14:30:00Z',
}

const MessageStub = defineComponent({
  name: 'PMessage',
  props: {
    severity: { type: String, default: '' },
    closable: { type: Boolean, default: false },
  },
  template: `<div class="p-message"><slot /></div>`,
})

// Stub all child monitoring components
const PortfolioHeatGaugeStub = defineComponent({
  name: 'PortfolioHeatGauge',
  props: {
    heatPercent: { type: Number, default: 0 },
    heatLimit: { type: Number, default: 10 },
  },
  template: `<div data-testid="heat-gauge">Heat: {{ heatPercent }}%</div>`,
})

const PnLMetricsStub = defineComponent({
  name: 'PnLMetricsComponent',
  props: { metrics: { type: Object, default: () => ({}) } },
  template: `<div data-testid="pnl-metrics">PnL</div>`,
})

const ActiveSignalsStub = defineComponent({
  name: 'ActiveSignals',
  props: { signals: { type: Array, default: () => [] } },
  template: `<div data-testid="active-signals">Signals: {{ signals?.length }}</div>`,
})

const PositionsByBrokerStub = defineComponent({
  name: 'PositionsByBroker',
  props: { positions: { type: Object, default: () => ({}) } },
  template: `<div data-testid="positions">Positions</div>`,
})

describe('MonitoringDashboard', () => {
  let wrapper: VueWrapper | undefined

  beforeEach(() => {
    vi.useFakeTimers()
    vi.mocked(getDashboardData).mockResolvedValue(mockDashboardData)
  })

  afterEach(() => {
    if (wrapper) wrapper.unmount()
    vi.useRealTimers()
    vi.restoreAllMocks()
  })

  const createWrapper = () => {
    return mount(MonitoringDashboard, {
      global: {
        plugins: [PrimeVue],
        stubs: {
          Message: MessageStub,
          PortfolioHeatGauge: PortfolioHeatGaugeStub,
          PnLMetricsComponent: PnLMetricsStub,
          ActiveSignals: ActiveSignalsStub,
          PositionsByBroker: PositionsByBrokerStub,
        },
      },
    })
  }

  it('renders dashboard title', async () => {
    wrapper = createWrapper()
    await flushPromises()
    expect(wrapper.text()).toContain('Production Monitoring')
  })

  it('fetches data on mount', async () => {
    wrapper = createWrapper()
    await flushPromises()
    expect(getDashboardData).toHaveBeenCalledOnce()
  })

  it('renders all sub-components', async () => {
    wrapper = createWrapper()
    await flushPromises()
    expect(wrapper.findComponent(PortfolioHeatGaugeStub).exists()).toBe(true)
    expect(wrapper.findComponent(PnLMetricsStub).exists()).toBe(true)
    expect(wrapper.findComponent(ActiveSignalsStub).exists()).toBe(true)
    expect(wrapper.findComponent(PositionsByBrokerStub).exists()).toBe(true)
  })

  it('passes correct heat data to PortfolioHeatGauge', async () => {
    wrapper = createWrapper()
    await flushPromises()
    const gauge = wrapper.findComponent(PortfolioHeatGaugeStub)
    expect(gauge.props('heatPercent')).toBe(5.5)
    expect(gauge.props('heatLimit')).toBe(10.0)
  })

  it('displays error message on API failure', async () => {
    vi.mocked(getDashboardData).mockRejectedValue(new Error('Network error'))
    wrapper = createWrapper()
    await flushPromises()
    expect(wrapper.text()).toContain('Network error')
  })

  it('auto-refreshes every 10 seconds', async () => {
    wrapper = createWrapper()
    await flushPromises()
    expect(getDashboardData).toHaveBeenCalledTimes(1)

    vi.advanceTimersByTime(10_000)
    await flushPromises()
    expect(getDashboardData).toHaveBeenCalledTimes(2)

    vi.advanceTimersByTime(10_000)
    await flushPromises()
    expect(getDashboardData).toHaveBeenCalledTimes(3)
  })

  it('clears interval on unmount', async () => {
    wrapper = createWrapper()
    await flushPromises()
    wrapper.unmount()

    vi.advanceTimersByTime(20_000)
    await flushPromises()
    // Should still be 1 call (from mount), not additional calls
    expect(getDashboardData).toHaveBeenCalledTimes(1)
    wrapper = undefined // prevent double unmount in afterEach
  })
})
