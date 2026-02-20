/**
 * OrderTable Component Unit Tests (Issue P4-I16)
 *
 * Tests:
 * - Renders order list correctly
 * - Cancel button calls correct store action
 * - Modify flow: click -> inline edit -> submit
 * - OCO groups are visually grouped
 * - Empty state shows helpful message
 */

import { describe, it, expect, beforeEach, vi } from 'vitest'
import { mount, type VueWrapper } from '@vue/test-utils'
import { createPinia, setActivePinia, type Pinia } from 'pinia'
import OrderTable from '../OrderTable.vue'
import { useOrdersStore } from '@/stores/orders'
import type { PendingOrder } from '@/services/ordersService'

// ---------------------------------------------------------------------------
// Factory helpers
// ---------------------------------------------------------------------------

function makeOrder(overrides: Partial<PendingOrder> = {}): PendingOrder {
  return {
    order_id: 'ORD-001',
    internal_order_id: null,
    broker: 'alpaca',
    symbol: 'AAPL',
    side: 'buy',
    order_type: 'limit',
    quantity: '100',
    filled_quantity: '0',
    remaining_quantity: '100',
    limit_price: '150.50',
    stop_price: null,
    status: 'pending',
    created_at: new Date().toISOString(),
    campaign_id: null,
    is_oco: false,
    oco_group_id: null,
    ...overrides,
  }
}

// ---------------------------------------------------------------------------
// Setup
// ---------------------------------------------------------------------------

let pinia: Pinia
let store: ReturnType<typeof useOrdersStore>

function createWrapper(): VueWrapper {
  return mount(OrderTable, {
    global: {
      plugins: [pinia],
    },
  })
}

describe('OrderTable', () => {
  beforeEach(() => {
    pinia = createPinia()
    setActivePinia(pinia)
    store = useOrdersStore()

    // Mock store actions
    vi.spyOn(store, 'cancelOrder').mockResolvedValue(true)
    vi.spyOn(store, 'modifyOrder').mockResolvedValue(true)
  })

  // -------------------------------------------------------------------------
  // Rendering
  // -------------------------------------------------------------------------

  it('shows empty state when no orders', () => {
    const wrapper = createWrapper()
    expect(wrapper.text()).toContain('No pending orders')
  })

  it('renders order rows for each order', async () => {
    store.orders = [
      makeOrder({ order_id: 'ORD-001', symbol: 'AAPL' }),
      makeOrder({ order_id: 'ORD-002', symbol: 'TSLA', broker: 'mt5' }),
    ]
    store.brokersConnected = { alpaca: true, mt5: true }
    const wrapper = createWrapper()
    await wrapper.vm.$nextTick()

    const rows = wrapper.findAll('tbody tr')
    expect(rows.length).toBeGreaterThanOrEqual(2)
  })

  it('renders broker badges for connected brokers', async () => {
    store.brokersConnected = { alpaca: true, mt5: false }
    const wrapper = createWrapper()
    await wrapper.vm.$nextTick()

    const text = wrapper.text()
    expect(text).toContain('alpaca')
    expect(text).toContain('mt5')
  })

  it('displays correct status badges', async () => {
    store.orders = [
      makeOrder({ order_id: 'ORD-001', status: 'pending' }),
      makeOrder({ order_id: 'ORD-002', status: 'partial' }),
      makeOrder({ order_id: 'ORD-003', status: 'rejected' }),
    ]
    store.brokersConnected = { alpaca: true }
    const wrapper = createWrapper()
    await wrapper.vm.$nextTick()

    expect(wrapper.text()).toContain('pending')
    expect(wrapper.text()).toContain('partial')
    expect(wrapper.text()).toContain('rejected')
  })

  // -------------------------------------------------------------------------
  // Cancel action
  // -------------------------------------------------------------------------

  it('cancel button calls cancelOrder on store', async () => {
    store.orders = [makeOrder()]
    store.brokersConnected = { alpaca: true }
    const wrapper = createWrapper()
    await wrapper.vm.$nextTick()

    const cancelBtn = wrapper
      .findAll('button')
      .find((btn) => btn.text().trim() === 'Cancel')
    expect(cancelBtn).toBeDefined()
    await cancelBtn!.trigger('click')
    await wrapper.vm.$nextTick()

    expect(store.cancelOrder).toHaveBeenCalledWith('ORD-001')
  })

  // -------------------------------------------------------------------------
  // Modify flow
  // -------------------------------------------------------------------------

  it('modify button shows inline edit inputs', async () => {
    store.orders = [makeOrder()]
    store.brokersConnected = { alpaca: true }
    const wrapper = createWrapper()
    await wrapper.vm.$nextTick()

    // Click Modify button
    const modifyBtn = wrapper
      .findAll('button')
      .find((btn) => btn.text().trim() === 'Modify')
    expect(modifyBtn).toBeDefined()
    await modifyBtn!.trigger('click')
    await wrapper.vm.$nextTick()

    // Should show input and Save/Cancel buttons
    expect(wrapper.find('input[placeholder="New price"]').exists()).toBe(true)
    expect(wrapper.text()).toContain('Save')
  })

  it('submit modify calls modifyOrder with correct params', async () => {
    store.orders = [makeOrder({ limit_price: '150.50' })]
    store.brokersConnected = { alpaca: true }
    const wrapper = createWrapper()
    await wrapper.vm.$nextTick()

    // Click Modify
    const modifyBtn = wrapper
      .findAll('button')
      .find((btn) => btn.text().trim() === 'Modify')
    expect(modifyBtn).toBeDefined()
    await modifyBtn!.trigger('click')
    await wrapper.vm.$nextTick()

    // Set new price value
    const input = wrapper.find('input[placeholder="New price"]')
    await input.setValue('155.00')
    await wrapper.vm.$nextTick()

    // Click Save
    const saveBtn = wrapper
      .findAll('button')
      .find((btn) => btn.text().trim() === 'Save')
    expect(saveBtn).toBeDefined()
    await saveBtn!.trigger('click')
    await wrapper.vm.$nextTick()

    expect(store.modifyOrder).toHaveBeenCalledWith('ORD-001', {
      limit_price: '155.00',
    })
  })

  // -------------------------------------------------------------------------
  // OCO groups
  // -------------------------------------------------------------------------

  it('displays OCO group header for grouped orders', async () => {
    store.orders = [
      makeOrder({
        order_id: 'ORD-A',
        is_oco: true,
        oco_group_id: 'OCO-1',
      }),
      makeOrder({
        order_id: 'ORD-B',
        is_oco: true,
        oco_group_id: 'OCO-1',
      }),
    ]
    store.brokersConnected = { alpaca: true }
    const wrapper = createWrapper()
    await wrapper.vm.$nextTick()

    expect(wrapper.text()).toContain('OCO Group')
    expect(wrapper.text()).toContain('OCO-1')
  })

  // -------------------------------------------------------------------------
  // Loading state
  // -------------------------------------------------------------------------

  it('shows loading skeleton when isLoading', async () => {
    store.isLoading = true
    const wrapper = createWrapper()
    await wrapper.vm.$nextTick()

    expect(wrapper.findAll('.animate-pulse').length).toBeGreaterThan(0)
  })

  // -------------------------------------------------------------------------
  // Error display
  // -------------------------------------------------------------------------

  it('shows error banner when store has error', async () => {
    store.error = 'Failed to load pending orders'
    const wrapper = createWrapper()
    await wrapper.vm.$nextTick()

    expect(wrapper.text()).toContain('Failed to load pending orders')
  })
})
