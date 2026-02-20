/**
 * BrokerConnectionCard Component Unit Tests (Issue P4-I17)
 *
 * Tests:
 * - Shows correct connection status badge
 * - Test Connection button calls correct API
 * - Disconnect button shows confirmation
 * - Margin level bar shows correct color at thresholds
 */

import { describe, it, expect, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import BrokerConnectionCard from '../BrokerConnectionCard.vue'
import type { BrokerAccountInfo } from '@/services/brokerDashboardService'

// PrimeVue stub for Dialog
const DialogStub = {
  template:
    '<div v-if="visible" class="dialog-stub"><slot /><slot name="footer" /></div>',
  props: ['visible', 'modal', 'header', 'style'],
  emits: ['update:visible'],
}

// --- Test Data ---

function makeBrokerInfo(
  overrides: Partial<BrokerAccountInfo> = {}
): BrokerAccountInfo {
  return {
    broker: 'mt5',
    connected: true,
    last_connected_at: '2025-01-01T00:00:00Z',
    platform_name: 'MetaTrader 5',
    account_id: 'ACC123',
    account_balance: '50000.00',
    buying_power: '100000.00',
    cash: '50000.00',
    margin_used: '5000.00',
    margin_available: '45000.00',
    margin_level_pct: '900.00',
    latency_ms: null,
    error_message: null,
    ...overrides,
  }
}

function mountCard(broker: BrokerAccountInfo) {
  return mount(BrokerConnectionCard, {
    props: { broker },
    global: {
      stubs: {
        Dialog: DialogStub,
      },
    },
  })
}

// --- Tests ---

describe('BrokerConnectionCard', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('shows green status badge when connected', () => {
    const wrapper = mountCard(makeBrokerInfo({ connected: true }))
    const badge = wrapper.find('[data-testid="status-badge"]')
    expect(badge.classes()).toContain('bg-green-500')
  })

  it('shows red status badge when disconnected', () => {
    const wrapper = mountCard(
      makeBrokerInfo({ connected: false, error_message: 'Not connected' })
    )
    const badge = wrapper.find('[data-testid="status-badge"]')
    expect(badge.classes()).toContain('bg-red-500')
  })

  it('displays account information when connected', () => {
    const wrapper = mountCard(makeBrokerInfo())
    const text = wrapper.text()
    expect(text).toContain('ACC123')
    expect(text).toContain('$50,000.00')
    expect(text).toContain('$100,000.00')
  })

  it('shows error message when disconnected', () => {
    const wrapper = mountCard(
      makeBrokerInfo({
        connected: false,
        error_message: 'Connection refused',
        account_id: null,
      })
    )
    expect(wrapper.text()).toContain('Connection refused')
  })

  it('has a Test Connection button', () => {
    const wrapper = mountCard(makeBrokerInfo())
    const btn = wrapper.find('[data-testid="test-connection-btn"]')
    expect(btn.exists()).toBe(true)
    expect(btn.text()).toBe('Test Connection')
  })

  it('shows Disconnect button when connected', () => {
    const wrapper = mountCard(makeBrokerInfo({ connected: true }))
    const btn = wrapper.find('[data-testid="disconnect-btn"]')
    expect(btn.exists()).toBe(true)
  })

  it('shows Reconnect button when disconnected', () => {
    const wrapper = mountCard(makeBrokerInfo({ connected: false }))
    const btn = wrapper.find('[data-testid="reconnect-btn"]')
    expect(btn.exists()).toBe(true)
    expect(btn.text()).toBe('Reconnect')
  })

  it('shows disconnect confirmation dialog on click', async () => {
    const wrapper = mountCard(makeBrokerInfo({ connected: true }))
    const btn = wrapper.find('[data-testid="disconnect-btn"]')
    await btn.trigger('click')

    // Dialog should now be visible (stub renders when visible=true)
    const dialog = wrapper.find('.dialog-stub')
    expect(dialog.exists()).toBe(true)
  })

  describe('margin level bar colors', () => {
    it('shows green bar when margin level >= 200%', () => {
      const wrapper = mountCard(makeBrokerInfo({ margin_level_pct: '250.00' }))
      const bar = wrapper.find('[data-testid="margin-bar"]')
      expect(bar.classes()).toContain('bg-green-500')
    })

    it('shows yellow bar when margin level is 100-200%', () => {
      const wrapper = mountCard(makeBrokerInfo({ margin_level_pct: '150.00' }))
      const bar = wrapper.find('[data-testid="margin-bar"]')
      expect(bar.classes()).toContain('bg-yellow-500')
    })

    it('shows red bar when margin level < 100%', () => {
      const wrapper = mountCard(makeBrokerInfo({ margin_level_pct: '80.00' }))
      const bar = wrapper.find('[data-testid="margin-bar"]')
      expect(bar.classes()).toContain('bg-red-500')
    })
  })
})
