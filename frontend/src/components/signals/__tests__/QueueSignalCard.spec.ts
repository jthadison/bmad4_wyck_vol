/**
 * QueueSignalCard Component Unit Tests
 * Story 19.10 - Signal Approval Queue UI
 *
 * Test Coverage:
 * - Component rendering with pending signal data
 * - Countdown timer display and formatting
 * - Approve/Reject button interactions
 * - Card styling based on state (selected, expired)
 * - Confidence grade calculation
 * - Accessibility features
 */

import { describe, it, expect, afterEach } from 'vitest'
import { mount, VueWrapper } from '@vue/test-utils'
import QueueSignalCard from '@/components/signals/QueueSignalCard.vue'
import type { PendingSignal } from '@/types'
import PrimeVue from 'primevue/config'

// Helper to create mock pending signal (flat structure matching backend PendingSignalView)
const createMockPendingSignal = (
  overrides?: Partial<PendingSignal>
): PendingSignal => ({
  queue_id: 'queue-123',
  signal_id: 'signal-123',
  symbol: 'AAPL',
  pattern_type: 'SPRING',
  confidence_score: 92,
  confidence_grade: 'A+',
  entry_price: '150.25',
  stop_loss: '149.50',
  target_price: '152.75',
  risk_amount: 1.5,
  wyckoff_phase: 'C',
  asset_class: 'Stock',
  submitted_at: new Date().toISOString(),
  expires_at: new Date(Date.now() + 300000).toISOString(),
  time_remaining_seconds: 272,
  is_expired: false,
  ...overrides,
})

describe('QueueSignalCard.vue', () => {
  let wrapper: VueWrapper

  const mountComponent = (props: {
    signal: PendingSignal
    isSelected?: boolean
  }) => {
    return mount(QueueSignalCard, {
      props,
      global: {
        plugins: [PrimeVue],
        stubs: {
          Card: {
            template: `
              <div class="p-card" :class="$attrs.class" @click="$emit('click')" @keypress="$emit('keypress', $event)">
                <slot name="content" />
              </div>
            `,
          },
          Badge: {
            template:
              '<span class="p-badge" :class="$attrs.class">{{ value }}</span>',
            props: ['value', 'severity'],
          },
          Button: {
            template: `
              <button
                class="p-button"
                :class="{ 'p-disabled': disabled }"
                :disabled="disabled"
                @click="$emit('click', $event)"
              >
                <i v-if="icon" :class="icon"></i>
                {{ label }}
              </button>
            `,
            props: [
              'label',
              'icon',
              'severity',
              'outlined',
              'disabled',
              'loading',
            ],
          },
        },
      },
    })
  }

  afterEach(() => {
    if (wrapper) {
      wrapper.unmount()
    }
  })

  describe('Component Rendering', () => {
    it('should render signal card with symbol', () => {
      const signal = createMockPendingSignal()
      wrapper = mountComponent({ signal })

      expect(wrapper.find('[data-testid="signal-symbol"]').text()).toBe('AAPL')
    })

    it('should render pattern badge', () => {
      const signal = createMockPendingSignal()
      wrapper = mountComponent({ signal })

      const badge = wrapper.find('[data-testid="pattern-badge"]')
      expect(badge.text()).toBe('SPRING')
    })

    it('should render confidence grade', () => {
      const signal = createMockPendingSignal()
      wrapper = mountComponent({ signal })

      const grade = wrapper.find('[data-testid="confidence-grade"]')
      expect(grade.text()).toBe('A+')
    })

    it('should render entry price', () => {
      const signal = createMockPendingSignal()
      wrapper = mountComponent({ signal })

      expect(wrapper.find('[data-testid="entry-price"]').text()).toContain(
        '150.25'
      )
    })

    it('should render stop price', () => {
      const signal = createMockPendingSignal()
      wrapper = mountComponent({ signal })

      expect(wrapper.find('[data-testid="stop-price"]').text()).toContain(
        '149.50'
      )
    })

    it('should render target price', () => {
      const signal = createMockPendingSignal()
      wrapper = mountComponent({ signal })

      expect(wrapper.find('[data-testid="target-price"]').text()).toContain(
        '152.75'
      )
    })

    it('should render R-multiple', () => {
      const signal = createMockPendingSignal()
      wrapper = mountComponent({ signal })

      expect(wrapper.find('[data-testid="r-multiple"]').text()).toContain(
        '3.33R'
      )
    })
  })

  describe('Signal Detail Fields (Story 23.10)', () => {
    it('should render confidence grade row', () => {
      const signal = createMockPendingSignal({ confidence_grade: 'A+' })
      wrapper = mountComponent({ signal })

      expect(wrapper.find('[data-testid="confidence-grade-row"]').text()).toBe(
        'A+'
      )
    })

    it('should render stop distance percentage', () => {
      const signal = createMockPendingSignal({
        entry_price: '150.25',
        stop_loss: '149.50',
      })
      wrapper = mountComponent({ signal })

      const el = wrapper.find('[data-testid="stop-distance"]')
      expect(el.exists()).toBe(true)
      expect(el.text()).toContain('0.5%')
    })

    it('should show 0.0% stop distance when entry is zero', () => {
      const signal = createMockPendingSignal({
        entry_price: '0',
        stop_loss: '0',
      })
      wrapper = mountComponent({ signal })

      const el = wrapper.find('[data-testid="stop-distance"]')
      expect(el.text()).toBe('0.0%')
    })

    it('should render asset class', () => {
      const signal = createMockPendingSignal({ symbol: 'AAPL' })
      wrapper = mountComponent({ signal })

      expect(wrapper.find('[data-testid="asset-class"]').text()).toBe('Stock')
    })

    it('should show Forex for currency pair symbols (heuristic fallback)', () => {
      const signal = createMockPendingSignal({
        symbol: 'EURUSD',
        asset_class: '',
      })
      wrapper = mountComponent({ signal })

      expect(wrapper.find('[data-testid="asset-class"]').text()).toBe('Forex')
    })

    it('should show Index for index symbols (heuristic fallback)', () => {
      const signal = createMockPendingSignal({
        symbol: 'US30',
        asset_class: '',
      })
      wrapper = mountComponent({ signal })

      expect(wrapper.find('[data-testid="asset-class"]').text()).toBe('Index')
    })

    it('should use backend asset_class when available', () => {
      const signal = createMockPendingSignal({ asset_class: 'Crypto' })
      wrapper = mountComponent({ signal })

      expect(wrapper.find('[data-testid="asset-class"]').text()).toBe('Crypto')
    })

    it('should render risk amount as dollar value', () => {
      const signal = createMockPendingSignal({ risk_amount: 225.0 })
      wrapper = mountComponent({ signal })

      expect(wrapper.find('[data-testid="risk-amount"]').text()).toContain(
        '$225.00'
      )
    })

    it('should show N/A when risk_amount is 0', () => {
      const signal = createMockPendingSignal({ risk_amount: 0 })
      wrapper = mountComponent({ signal })

      expect(wrapper.find('[data-testid="risk-amount"]').text()).toBe('N/A')
    })

    it('should render Wyckoff phase', () => {
      const signal = createMockPendingSignal({ wyckoff_phase: 'C' })
      wrapper = mountComponent({ signal })

      expect(wrapper.find('[data-testid="wyckoff-phase"]').text()).toBe('C')
    })

    it('should show N/A when wyckoff_phase is empty', () => {
      const signal = createMockPendingSignal({ wyckoff_phase: '' })
      wrapper = mountComponent({ signal })

      expect(wrapper.find('[data-testid="wyckoff-phase"]').text()).toBe('N/A')
    })

    it('should show $ prefix for stock prices', () => {
      const signal = createMockPendingSignal({ asset_class: 'Stock' })
      wrapper = mountComponent({ signal })

      expect(wrapper.find('[data-testid="entry-price"]').text()).toContain('$')
    })

    it('should omit $ prefix for forex prices', () => {
      const signal = createMockPendingSignal({
        symbol: 'EURUSD',
        asset_class: 'Forex',
        entry_price: '1.08765',
      })
      wrapper = mountComponent({ signal })

      const text = wrapper.find('[data-testid="entry-price"]').text()
      expect(text).not.toContain('$')
      expect(text).toContain('1.08765')
    })

    it('should show 5 decimal places for forex prices', () => {
      const signal = createMockPendingSignal({
        symbol: 'EURUSD',
        asset_class: 'Forex',
        entry_price: '1.08765',
        stop_loss: '1.08500',
        target_price: '1.09200',
      })
      wrapper = mountComponent({ signal })

      expect(wrapper.find('[data-testid="entry-price"]').text()).toContain(
        '1.08765'
      )
      expect(wrapper.find('[data-testid="stop-price"]').text()).toContain(
        '1.08500'
      )
      expect(wrapper.find('[data-testid="target-price"]').text()).toContain(
        '1.09200'
      )
    })
  })

  describe('Confidence Grade Calculation', () => {
    it('should show A+ for confidence >= 90', () => {
      const signal = createMockPendingSignal({ confidence_score: 92 })
      wrapper = mountComponent({ signal })

      expect(wrapper.find('[data-testid="confidence-grade"]').text()).toBe('A+')
    })

    it('should show A for confidence >= 85', () => {
      const signal = createMockPendingSignal({
        confidence_score: 87,
        confidence_grade: '',
      })
      wrapper = mountComponent({ signal })

      expect(wrapper.find('[data-testid="confidence-grade"]').text()).toBe('A')
    })

    it('should show B+ for confidence >= 80', () => {
      const signal = createMockPendingSignal({
        confidence_score: 82,
        confidence_grade: '',
      })
      wrapper = mountComponent({ signal })

      expect(wrapper.find('[data-testid="confidence-grade"]').text()).toBe('B+')
    })

    it('should show B for confidence >= 75', () => {
      const signal = createMockPendingSignal({
        confidence_score: 77,
        confidence_grade: '',
      })
      wrapper = mountComponent({ signal })

      expect(wrapper.find('[data-testid="confidence-grade"]').text()).toBe('B')
    })

    it('should show C for confidence < 75', () => {
      const signal = createMockPendingSignal({
        confidence_score: 72,
        confidence_grade: '',
      })
      wrapper = mountComponent({ signal })

      expect(wrapper.find('[data-testid="confidence-grade"]').text()).toBe('C')
    })
  })

  describe('Countdown Timer', () => {
    it('should format time remaining correctly', () => {
      const signal = createMockPendingSignal({
        time_remaining_seconds: 272, // 4:32
      })
      wrapper = mountComponent({ signal })

      const timer = wrapper.find('[data-testid="time-remaining"]')
      expect(timer.text()).toContain('4:32')
    })

    it('should show Expired when time is 0', () => {
      const signal = createMockPendingSignal({
        time_remaining_seconds: 0,
        is_expired: true,
      })
      wrapper = mountComponent({ signal })

      const timer = wrapper.find('[data-testid="time-remaining"]')
      expect(timer.text()).toContain('Expired')
    })

    it('should show expired badge when expired', () => {
      const signal = createMockPendingSignal({
        time_remaining_seconds: 0,
        is_expired: true,
      })
      wrapper = mountComponent({ signal })

      expect(wrapper.find('[data-testid="expired-badge"]').exists()).toBe(true)
    })
  })

  describe('Button Interactions', () => {
    it('should emit approve event when approve button clicked', async () => {
      const signal = createMockPendingSignal()
      wrapper = mountComponent({ signal })

      await wrapper.find('[data-testid="approve-button"]').trigger('click')

      expect(wrapper.emitted('approve')).toBeTruthy()
    })

    it('should emit reject event when reject button clicked', async () => {
      const signal = createMockPendingSignal()
      wrapper = mountComponent({ signal })

      await wrapper.find('[data-testid="reject-button"]').trigger('click')

      expect(wrapper.emitted('reject')).toBeTruthy()
    })

    it('should emit select event when card clicked', async () => {
      const signal = createMockPendingSignal()
      wrapper = mountComponent({ signal })

      await wrapper.find('.p-card').trigger('click')

      expect(wrapper.emitted('select')).toBeTruthy()
    })

    it('should disable buttons when expired', () => {
      const signal = createMockPendingSignal({
        time_remaining_seconds: 0,
        is_expired: true,
      })
      wrapper = mountComponent({ signal })

      const approveButton = wrapper.find('[data-testid="approve-button"]')
      const rejectButton = wrapper.find('[data-testid="reject-button"]')

      expect(approveButton.attributes('disabled')).toBeDefined()
      expect(rejectButton.attributes('disabled')).toBeDefined()
    })
  })

  describe('Card Styling', () => {
    it('should have selected styling when isSelected is true', () => {
      const signal = createMockPendingSignal()
      wrapper = mountComponent({ signal, isSelected: true })

      const card = wrapper.find('.p-card')
      expect(card.classes()).toContain('border-blue-500')
    })

    it('should have expired styling when expired', () => {
      const signal = createMockPendingSignal({
        is_expired: true,
      })
      wrapper = mountComponent({ signal })

      const card = wrapper.find('.p-card')
      expect(card.classes()).toContain('opacity-50')
    })
  })

  describe('Pattern Badge Colors', () => {
    it('should show green badge for SPRING', () => {
      const signal = createMockPendingSignal({ pattern_type: 'SPRING' })
      wrapper = mountComponent({ signal })

      const badge = wrapper.find('[data-testid="pattern-badge"]')
      expect(badge.classes()).toContain('bg-green-500')
    })

    it('should show blue badge for SOS', () => {
      const signal = createMockPendingSignal({ pattern_type: 'SOS' })
      wrapper = mountComponent({ signal })

      const badge = wrapper.find('[data-testid="pattern-badge"]')
      expect(badge.classes()).toContain('bg-blue-500')
    })

    it('should show red badge for UTAD', () => {
      const signal = createMockPendingSignal({ pattern_type: 'UTAD' })
      wrapper = mountComponent({ signal })

      const badge = wrapper.find('[data-testid="pattern-badge"]')
      expect(badge.classes()).toContain('bg-red-500')
    })
  })

  describe('Accessibility', () => {
    it('should have proper aria-label', () => {
      const signal = createMockPendingSignal()
      wrapper = mountComponent({ signal })

      const card = wrapper.find('[data-testid="queue-signal-card"]')
      expect(card.attributes('aria-label')).toContain('SPRING')
      expect(card.attributes('aria-label')).toContain('AAPL')
      expect(card.attributes('aria-label')).toContain('92%')
    })

    it('should have role button', () => {
      const signal = createMockPendingSignal()
      wrapper = mountComponent({ signal })

      const card = wrapper.find('[data-testid="queue-signal-card"]')
      expect(card.attributes('role')).toBe('button')
    })

    it('should be keyboard accessible', () => {
      const signal = createMockPendingSignal()
      wrapper = mountComponent({ signal })

      const card = wrapper.find('[data-testid="queue-signal-card"]')
      expect(card.attributes('tabindex')).toBe('0')
    })
  })
})
