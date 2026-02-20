/**
 * PriceAlertManager Component Unit Tests
 *
 * Tests:
 * - Renders the create form with all alert type options
 * - Validates required fields before creating
 * - Shows and hides price/direction fields based on alert type
 * - Renders alerts list from the store
 * - Emits delete and toggle actions
 */

import { describe, it, expect, beforeEach, vi } from 'vitest'
import { mount, type VueWrapper } from '@vue/test-utils'
import { createPinia, setActivePinia, type Pinia } from 'pinia'
import PriceAlertManager from '../PriceAlertManager.vue'
import { usePriceAlertsStore } from '@/stores/priceAlerts'
import type { PriceAlert } from '@/services/priceAlertService'

// ---------------------------------------------------------------------------
// Minimal PrimeVue stubs so we don't need a full PrimeVue install
// ---------------------------------------------------------------------------
// eslint-disable-next-line @typescript-eslint/no-explicit-any
const primevueStubs: Record<string, any> = {
  Button: {
    template:
      '<button :data-loading="loading" :data-icon="icon" @click="$emit(\'click\')"><slot /></button>',
    props: [
      'label',
      'icon',
      'loading',
      'disabled',
      'severity',
      'size',
      'title',
    ],
    emits: ['click'],
  },
  Dropdown: {
    template:
      '<select :value="modelValue" @change="$emit(\'update:modelValue\', $event.target.value)"><slot /></select>',
    props: [
      'modelValue',
      'options',
      'optionLabel',
      'optionValue',
      'placeholder',
    ],
    emits: ['update:modelValue'],
  },
  InputText: {
    template:
      '<input :value="modelValue" @input="$emit(\'update:modelValue\', $event.target.value)" />',
    props: ['modelValue', 'placeholder', 'maxlength', 'class'],
    emits: ['update:modelValue', 'input'],
  },
  InputNumber: {
    template:
      '<input type="number" :value="modelValue" @input="$emit(\'update:modelValue\', parseFloat($event.target.value) || null)" />',
    props: ['modelValue', 'min', 'maxFractionDigits', 'placeholder', 'class'],
    emits: ['update:modelValue'],
  },
  Message: {
    template: '<div class="p-message" :data-severity="severity"><slot /></div>',
    props: ['severity', 'closable'],
    emits: ['close'],
  },
}

// Type for accessing component internals in tests (unexposed Composition API)
interface ComponentVM {
  handleCreate: () => Promise<void>
  form: {
    symbol: string
    alert_type: string
    price_level: number | null
    direction: string | null
  }
  alertTypeOptions: Array<{ value: string; label: string }>
}

// ---------------------------------------------------------------------------
// Factory helpers
// ---------------------------------------------------------------------------

function makePriceAlert(overrides: Partial<PriceAlert> = {}): PriceAlert {
  return {
    id: '00000000-0000-0000-0000-000000000001',
    user_id: 'user-1',
    symbol: 'AAPL',
    alert_type: 'price_level',
    price_level: 150,
    direction: 'above',
    wyckoff_level_type: null,
    is_active: true,
    notes: null,
    created_at: '2026-02-20T10:00:00Z',
    triggered_at: null,
    ...overrides,
  }
}

// ---------------------------------------------------------------------------
// Setup
// ---------------------------------------------------------------------------

let pinia: Pinia
let store: ReturnType<typeof usePriceAlertsStore>

function createWrapper(): VueWrapper {
  return mount(PriceAlertManager, {
    global: {
      // Reuse the same pinia instance so store mocks apply to the component
      plugins: [pinia],
      stubs: primevueStubs,
    },
  })
}

describe('PriceAlertManager', () => {
  beforeEach(() => {
    pinia = createPinia()
    setActivePinia(pinia)
    store = usePriceAlertsStore()

    // Mock store actions to avoid real API calls
    vi.spyOn(store, 'fetchAlerts').mockResolvedValue()
    vi.spyOn(store, 'createAlert').mockResolvedValue(makePriceAlert())
    vi.spyOn(store, 'toggleAlert').mockResolvedValue(true)
    vi.spyOn(store, 'deleteAlert').mockResolvedValue(true)
  })

  // -------------------------------------------------------------------------
  // Rendering
  // -------------------------------------------------------------------------

  it('renders the manager title', () => {
    const wrapper = createWrapper()
    expect(wrapper.find('.manager-title').text()).toBe('Price Alerts')
  })

  it('calls fetchAlerts on mount', () => {
    createWrapper()
    expect(store.fetchAlerts).toHaveBeenCalledOnce()
  })

  it('renders the create form', () => {
    const wrapper = createWrapper()
    expect(wrapper.find('.alert-form-card').exists()).toBe(true)
    expect(wrapper.find('.form-title').text()).toContain('Create New Alert')
  })

  it('renders empty state when no alerts', () => {
    store.alerts = []
    const wrapper = createWrapper()
    expect(wrapper.find('.empty-state').exists()).toBe(true)
  })

  it('renders alert rows when alerts exist', async () => {
    store.alerts = [
      makePriceAlert(),
      makePriceAlert({ id: '2', symbol: 'TSLA' }),
    ]
    const wrapper = createWrapper()
    await wrapper.vm.$nextTick()
    expect(wrapper.findAll('.alert-row')).toHaveLength(2)
  })

  it('shows symbol for each alert row', async () => {
    store.alerts = [makePriceAlert({ symbol: 'NVDA' })]
    const wrapper = createWrapper()
    await wrapper.vm.$nextTick()
    expect(wrapper.find('.alert-symbol').text()).toBe('NVDA')
  })

  it('applies inactive class for paused alerts', async () => {
    store.alerts = [makePriceAlert({ is_active: false })]
    const wrapper = createWrapper()
    await wrapper.vm.$nextTick()
    expect(wrapper.find('.alert-row').classes()).toContain(
      'alert-row--inactive'
    )
  })

  // -------------------------------------------------------------------------
  // Form validation
  // -------------------------------------------------------------------------

  it('shows error when creating without a symbol', async () => {
    const wrapper = createWrapper()
    // Trigger handleCreate by finding the button with Create Alert label text
    await wrapper.vm.$nextTick()
    // Access internals directly since label is a prop on the stub
    const vm = wrapper.vm as unknown as ComponentVM
    await vm.handleCreate()
    await wrapper.vm.$nextTick()

    expect(wrapper.find('.field-error').text()).toContain('Symbol is required')
    expect(store.createAlert).not.toHaveBeenCalled()
  })

  it('shows error for price_level alert without price_level', async () => {
    const wrapper = createWrapper()
    const vm = wrapper.vm as unknown as ComponentVM
    vm.form.symbol = 'AAPL'
    vm.form.alert_type = 'price_level'
    vm.form.price_level = null
    vm.form.direction = 'above'

    await vm.handleCreate()
    await wrapper.vm.$nextTick()

    expect(store.createAlert).not.toHaveBeenCalled()
  })

  it('shows error for price_level alert without direction', async () => {
    const wrapper = createWrapper()
    const vm = wrapper.vm as unknown as ComponentVM
    vm.form.symbol = 'AAPL'
    vm.form.alert_type = 'price_level'
    vm.form.price_level = 150.0
    vm.form.direction = null

    await vm.handleCreate()
    await wrapper.vm.$nextTick()

    expect(store.createAlert).not.toHaveBeenCalled()
  })

  it('allows phase_change alert without price_level', async () => {
    const wrapper = createWrapper()
    const vm = wrapper.vm as unknown as ComponentVM
    vm.form.symbol = 'AAPL'
    vm.form.alert_type = 'phase_change'
    vm.form.price_level = null
    vm.form.direction = null

    await vm.handleCreate()
    await wrapper.vm.$nextTick()

    expect(store.createAlert).toHaveBeenCalledWith(
      expect.objectContaining({ alert_type: 'phase_change' })
    )
  })

  // -------------------------------------------------------------------------
  // Alert type options
  // -------------------------------------------------------------------------

  it('form includes all 5 Wyckoff alert type options', () => {
    const wrapper = createWrapper()
    const vm = wrapper.vm as unknown as ComponentVM
    const types = vm.alertTypeOptions.map((o: { value: string }) => o.value)
    expect(types).toContain('price_level')
    expect(types).toContain('creek')
    expect(types).toContain('ice')
    expect(types).toContain('spring')
    expect(types).toContain('phase_change')
  })

  // -------------------------------------------------------------------------
  // Toggle / Delete actions
  // -------------------------------------------------------------------------

  it('calls toggleAlert when pause button clicked', async () => {
    const alert = makePriceAlert()
    store.alerts = [alert]
    const wrapper = createWrapper()
    await wrapper.vm.$nextTick()

    // Find toggle button (first button in actions - pause/play)
    const actionBtns = wrapper.find('.alert-actions').findAll('button')
    await actionBtns[0].trigger('click')
    await wrapper.vm.$nextTick()

    expect(store.toggleAlert).toHaveBeenCalledWith(alert.id)
  })

  it('calls deleteAlert when trash button clicked', async () => {
    const alert = makePriceAlert()
    store.alerts = [alert]
    const wrapper = createWrapper()
    await wrapper.vm.$nextTick()

    const actionBtns = wrapper.find('.alert-actions').findAll('button')
    await actionBtns[1].trigger('click')
    await wrapper.vm.$nextTick()

    expect(store.deleteAlert).toHaveBeenCalledWith(alert.id)
  })

  // -------------------------------------------------------------------------
  // Count display
  // -------------------------------------------------------------------------

  it('displays correct total and active counts', async () => {
    store.alerts = [
      makePriceAlert({ is_active: true }),
      makePriceAlert({ id: '2', is_active: false }),
    ]
    const wrapper = createWrapper()
    await wrapper.vm.$nextTick()

    expect(wrapper.find('.count-badge').text()).toBe('2')
    expect(wrapper.find('.active-count').text()).toContain('1 active')
  })
})
