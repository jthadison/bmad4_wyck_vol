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
import type { PendingSignal, Signal } from '@/types'
import PrimeVue from 'primevue/config'

// Helper to create mock signal data
const createMockSignal = (overrides?: Partial<Signal>): Signal => ({
  id: 'signal-123',
  symbol: 'AAPL',
  pattern_type: 'SPRING',
  phase: 'C',
  entry_price: '150.25',
  stop_loss: '149.50',
  target_levels: {
    primary_target: '152.75',
    secondary_targets: [],
  },
  position_size: 100,
  risk_amount: '75.00',
  r_multiple: '3.33',
  confidence_score: 92,
  confidence_components: {
    pattern_confidence: 90,
    phase_confidence: 95,
    volume_confidence: 91,
    overall_confidence: 92,
  },
  campaign_id: null,
  status: 'PENDING',
  timestamp: new Date().toISOString(),
  timeframe: '1D',
  ...overrides,
})

// Helper to create mock pending signal
const createMockPendingSignal = (
  overrides?: Partial<PendingSignal>
): PendingSignal => ({
  queue_id: 'queue-123',
  signal: createMockSignal(),
  queued_at: new Date().toISOString(),
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

  describe('Confidence Grade Calculation', () => {
    it('should show A+ for confidence >= 90', () => {
      const signal = createMockPendingSignal({
        signal: createMockSignal({ confidence_score: 92 }),
      })
      wrapper = mountComponent({ signal })

      expect(wrapper.find('[data-testid="confidence-grade"]').text()).toBe('A+')
    })

    it('should show A for confidence >= 85', () => {
      const signal = createMockPendingSignal({
        signal: createMockSignal({ confidence_score: 87 }),
      })
      wrapper = mountComponent({ signal })

      expect(wrapper.find('[data-testid="confidence-grade"]').text()).toBe('A')
    })

    it('should show B+ for confidence >= 80', () => {
      const signal = createMockPendingSignal({
        signal: createMockSignal({ confidence_score: 82 }),
      })
      wrapper = mountComponent({ signal })

      expect(wrapper.find('[data-testid="confidence-grade"]').text()).toBe('B+')
    })

    it('should show B for confidence >= 75', () => {
      const signal = createMockPendingSignal({
        signal: createMockSignal({ confidence_score: 77 }),
      })
      wrapper = mountComponent({ signal })

      expect(wrapper.find('[data-testid="confidence-grade"]').text()).toBe('B')
    })

    it('should show C for confidence < 75', () => {
      const signal = createMockPendingSignal({
        signal: createMockSignal({ confidence_score: 72 }),
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
      const signal = createMockPendingSignal({
        signal: createMockSignal({ pattern_type: 'SPRING' }),
      })
      wrapper = mountComponent({ signal })

      const badge = wrapper.find('[data-testid="pattern-badge"]')
      expect(badge.classes()).toContain('bg-green-500')
    })

    it('should show blue badge for SOS', () => {
      const signal = createMockPendingSignal({
        signal: createMockSignal({ pattern_type: 'SOS' }),
      })
      wrapper = mountComponent({ signal })

      const badge = wrapper.find('[data-testid="pattern-badge"]')
      expect(badge.classes()).toContain('bg-blue-500')
    })

    it('should show red badge for UTAD', () => {
      const signal = createMockPendingSignal({
        signal: createMockSignal({ pattern_type: 'UTAD' }),
      })
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
