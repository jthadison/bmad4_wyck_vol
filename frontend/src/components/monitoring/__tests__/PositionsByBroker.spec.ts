/* eslint-disable vue/one-component-per-file */
/**
 * PositionsByBroker Component Unit Tests
 * Story 23.13 - Production Monitoring Dashboard
 */

import { describe, it, expect, afterEach } from 'vitest'
import { mount, VueWrapper } from '@vue/test-utils'
import PositionsByBroker from '@/components/monitoring/PositionsByBroker.vue'
import PrimeVue from 'primevue/config'
import { defineComponent } from 'vue'
import type { PositionByBroker } from '@/types/monitoring'

const CardStub = defineComponent({
  name: 'PCard',
  template: `
    <div class="p-card">
      <div class="p-card-title"><slot name="title" /></div>
      <div class="p-card-content"><slot name="content" /></div>
    </div>
  `,
})

const DataTableStub = defineComponent({
  name: 'PDataTable',
  props: { value: { type: Array, default: () => [] } },
  template: `<table class="p-datatable"><slot /></table>`,
})

const ColumnStub = defineComponent({
  name: 'PColumn',
  props: {
    field: { type: String, default: '' },
    header: { type: String, default: '' },
  },
  template: `<th>{{ header }}</th>`,
})

const mockPositions: Record<string, PositionByBroker[]> = {
  Alpaca: [
    {
      broker: 'Alpaca',
      symbol: 'AAPL',
      side: 'LONG',
      size: 100,
      entry_price: 150.0,
      current_price: 155.0,
      unrealized_pnl: 500.0,
      campaign_id: 'C-001',
    },
    {
      broker: 'Alpaca',
      symbol: 'TSLA',
      side: 'SHORT',
      size: 50,
      entry_price: 200.0,
      current_price: 195.0,
      unrealized_pnl: 250.0,
      campaign_id: null,
    },
  ],
  MetaTrader: [
    {
      broker: 'MetaTrader',
      symbol: 'EURUSD',
      side: 'LONG',
      size: 10000,
      entry_price: 1.085,
      current_price: 1.08,
      unrealized_pnl: -50.0,
      campaign_id: 'C-002',
    },
  ],
}

describe('PositionsByBroker', () => {
  let wrapper: VueWrapper | undefined

  const createWrapper = (
    positions: Record<string, PositionByBroker[]> = mockPositions
  ) => {
    return mount(PositionsByBroker, {
      props: { positions },
      global: {
        plugins: [PrimeVue],
        stubs: {
          Card: CardStub,
          DataTable: DataTableStub,
          Column: ColumnStub,
        },
      },
    })
  }

  afterEach(() => {
    if (wrapper) wrapper.unmount()
  })

  it('renders component title', () => {
    wrapper = createWrapper()
    expect(wrapper.text()).toContain('Positions by Broker')
  })

  it('renders broker names as section headers', () => {
    wrapper = createWrapper()
    expect(wrapper.text()).toContain('Alpaca')
    expect(wrapper.text()).toContain('MetaTrader')
  })

  it('shows empty state when no positions', () => {
    wrapper = createWrapper({})
    expect(wrapper.text()).toContain('No open positions')
  })

  it('creates a DataTable for each broker', () => {
    wrapper = createWrapper()
    const tables = wrapper.findAllComponents(DataTableStub)
    expect(tables.length).toBe(2)
  })

  it('passes correct data to each DataTable', () => {
    wrapper = createWrapper()
    const tables = wrapper.findAllComponents(DataTableStub)
    expect(tables[0].props('value')).toHaveLength(2)
    expect(tables[1].props('value')).toHaveLength(1)
  })
})
