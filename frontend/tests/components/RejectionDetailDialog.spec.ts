/**
 * Unit tests for RejectionDetailDialog component (Story 10.7)
 *
 * Tests the educational rejection detail dialog component with volume visualization,
 * historical context, educational content, and feedback functionality.
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, VueWrapper } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import PrimeVue from 'primevue/config'
import ToastService from 'primevue/toastservice'
import RejectionDetailDialog from '@/components/signals/RejectionDetailDialog.vue'
import type { Signal } from '@/types'
import * as feedbackApi from '@/services/feedbackApi'

// Mock the feedback API
vi.mock('@/services/feedbackApi', () => ({
  getPatternStatistics: vi.fn(),
  submitFeedback: vi.fn(),
  getRejectionCategory: vi.fn(),
}))

describe('RejectionDetailDialog', () => {
  let wrapper: VueWrapper<unknown>
  let mockSignal: Signal

  // Helper function to mount component with default config
  const mountComponent = (props: unknown) => {
    return mount(RejectionDetailDialog, {
      props,
      global: {
        plugins: [PrimeVue, ToastService],
        stubs: {
          Dialog: false,
          Button: false,
          Badge: false,
          Message: false,
        },
      },
    })
  }

  beforeEach(() => {
    setActivePinia(createPinia())

    // Mock signal with rejection data
    mockSignal = {
      id: '550e8400-e29b-41d4-a716-446655440000',
      pattern_type: 'SPRING',
      status: 'REJECTED',
      rejection_reason:
        'Volume Too High (Non-Negotiable Rule): 0.82x > 0.7x threshold',
      volume_ratio: 0.82,
      symbol: 'EURUSD',
      timeframe: '1H',
      entry_price: '1.0850',
      stop_loss: '1.0820',
      target: '1.0920',
      risk_reward_ratio: '2.33',
      confidence_score: 45,
      created_at: '2024-03-15T14:30:00Z',
      updated_at: '2024-03-15T14:30:00Z',
    } as Signal

    // Reset mocks
    vi.clearAllMocks()
  })

  describe('Component Rendering', () => {
    it('should render dialog when visible', () => {
      wrapper = mountComponent({
        signal: mockSignal,
        visible: true,
      })

      expect(wrapper.exists()).toBe(true)
    })

    it('should not render dialog when not visible', () => {
      wrapper = mountComponent({
        signal: mockSignal,
        visible: false,
      })

      const dialog = wrapper.findComponent({ name: 'Dialog' })
      expect(dialog.props('visible')).toBe(false)
    })

    it('should display parsed rejection reason', () => {
      wrapper = mountComponent({
        signal: mockSignal,
        visible: true,
      })

      // Since PrimeVue Dialog may not render content when not visible,
      // we'll check for the parsed data in component instance
      expect(wrapper.vm.parsedRejection.primary.reason).toBe('Volume Too High')
    })

    it('should display rule type badge severity', () => {
      wrapper = mountComponent({
        signal: mockSignal,
        visible: true,
      })

      // Check computed property
      expect(wrapper.vm.ruleSeverity).toBe('danger')
    })

    it('should not have non-negotiable severity when no rule type', () => {
      const signalWithoutRuleType = {
        ...mockSignal,
        rejection_reason: 'Phase Mismatch: Phase B, Spring requires Phase C',
      }

      wrapper = mountComponent({
        signal: signalWithoutRuleType,
        visible: true,
      })

      expect(wrapper.vm.ruleSeverity).toBe('warning')
    })
  })

  describe('Volume Visualization', () => {
    it('should calculate volume threshold for SPRING pattern', () => {
      wrapper = mountComponent({
        signal: mockSignal,
        visible: true,
      })

      // SPRING threshold is 0.7x
      expect(wrapper.vm.volumeThreshold).toBe(0.7)
    })

    it('should calculate volume threshold for SOS pattern', () => {
      const sosSignal = {
        ...mockSignal,
        pattern_type: 'SOS' as const,
        rejection_reason: 'Volume Too Low: 1.1x < 1.3x threshold',
        volume_ratio: 1.1,
      }

      wrapper = mountComponent({
        signal: sosSignal,
        visible: true,
      })

      // SOS threshold is 1.3x
      expect(wrapper.vm.volumeThreshold).toBe(1.3)
    })

    it('should calculate volume requirement for patterns', () => {
      wrapper = mountComponent({
        signal: mockSignal,
        visible: true,
      })

      // SPRING should have 'low' volume requirement
      expect(wrapper.vm.volumeRequirement).toBe('low')
    })

    it('should calculate percent difference correctly', () => {
      wrapper = mountComponent({
        signal: mockSignal,
        visible: true,
      })

      // 0.82 vs 0.7 threshold = ~17% above
      const comparison = wrapper.vm.volumeComparison
      expect(comparison.actualVolume).toBe(0.82)
      expect(comparison.threshold).toBe(0.7)
      expect(comparison.isAboveThreshold).toBe(true)
      expect(comparison.percentDiff).toBe('17')
    })
  })

  describe('Educational Content', () => {
    it('should provide educational content for SPRING pattern', () => {
      wrapper = mountComponent({
        signal: mockSignal,
        visible: true,
      })

      const content = wrapper.vm.educationalContent
      expect(content).toContain('Spring')
      expect(content).toContain('LOW volume')
      expect(content).toContain('0.7x')
    })

    it('should provide educational content for SOS pattern', () => {
      const sosSignal = {
        ...mockSignal,
        pattern_type: 'SOS' as const,
        rejection_reason: 'Volume Too Low: 1.1x < 1.3x threshold',
      }

      wrapper = mountComponent({
        signal: sosSignal,
        visible: true,
      })

      const content = wrapper.vm.educationalContent
      expect(content).toContain('Sign of Strength')
      expect(content).toContain('HIGH volume')
      expect(content).toContain('1.3x')
    })

    it('should provide educational content for all pattern types', () => {
      const patternTypes: Array<Signal['pattern_type']> = [
        'SPRING',
        'UTAD',
        'SOS',
        'LPS',
        'SC',
        'AR',
        'ST',
      ]

      patternTypes.forEach((patternType) => {
        const signal = {
          ...mockSignal,
          pattern_type: patternType,
        }

        wrapper = mountComponent({
          signal,
          visible: true,
        })

        const content = wrapper.vm.educationalContent
        expect(content.length).toBeGreaterThan(0)
        expect(content).not.toContain(
          'Pattern-specific educational content not available'
        )
      })
    })
  })

  describe('Historical Statistics', () => {
    it('should fetch statistics when dialog opens', async () => {
      const mockStats = {
        pattern_type: 'SPRING',
        rejection_category: 'volume',
        valid_win_rate: '65',
        invalid_win_rate: '32',
        sample_size_valid: 45,
        sample_size_invalid: 28,
        sufficient_data: true,
        message:
          'SPRING patterns with volume violations won 32% vs 65% valid patterns',
      }

      vi.mocked(feedbackApi.getPatternStatistics).mockResolvedValue(mockStats)
      vi.mocked(feedbackApi.getRejectionCategory).mockReturnValue('volume')

      // Mount with visible=false first, then change to true to trigger watch
      wrapper = mountComponent({
        signal: mockSignal,
        visible: false,
      })

      await wrapper.setProps({ visible: true })
      await wrapper.vm.$nextTick()
      await new Promise((resolve) => setTimeout(resolve, 100))

      expect(feedbackApi.getPatternStatistics).toHaveBeenCalledWith(
        'SPRING',
        'volume'
      )
    })

    it('should store statistics when available', async () => {
      const mockStats = {
        pattern_type: 'SPRING',
        rejection_category: 'volume',
        valid_win_rate: '65',
        invalid_win_rate: '32',
        sample_size_valid: 45,
        sample_size_invalid: 28,
        sufficient_data: true,
        message:
          'SPRING patterns with volume violations won 32% vs 65% valid patterns',
      }

      vi.mocked(feedbackApi.getPatternStatistics).mockResolvedValue(mockStats)
      vi.mocked(feedbackApi.getRejectionCategory).mockReturnValue('volume')

      // Mount with visible=false first, then change to true to trigger watch
      wrapper = mountComponent({
        signal: mockSignal,
        visible: false,
      })

      await wrapper.setProps({ visible: true })
      await wrapper.vm.$nextTick()
      await new Promise((resolve) => setTimeout(resolve, 100))

      expect(wrapper.vm.statistics).toEqual(mockStats)
      expect(wrapper.vm.statisticsLoading).toBe(false)
    })

    it('should handle statistics error gracefully', async () => {
      vi.mocked(feedbackApi.getPatternStatistics).mockRejectedValue(
        new Error('API Error')
      )
      vi.mocked(feedbackApi.getRejectionCategory).mockReturnValue('volume')

      // Mount with visible=false first, then change to true to trigger watch
      wrapper = mountComponent({
        signal: mockSignal,
        visible: false,
      })

      await wrapper.setProps({ visible: true })
      await wrapper.vm.$nextTick()
      await new Promise((resolve) => setTimeout(resolve, 100))

      expect(wrapper.vm.statisticsError).toBe(
        'Insufficient historical data available'
      )
    })
  })

  describe('Secondary Issues', () => {
    it('should parse secondary issues when present', () => {
      const signalWithSecondary = {
        ...mockSignal,
        rejection_reason:
          'Volume Too High: 0.82x > 0.7x; Test not confirmed: 0 bars vs 3-15 required; Phase mismatch: Phase B vs Phase C',
      }

      wrapper = mountComponent({
        signal: signalWithSecondary,
        visible: true,
      })

      const parsed = wrapper.vm.parsedRejection
      expect(parsed.secondary).toHaveLength(2)
      expect(parsed.secondary[0].reason).toBe('Test not confirmed')
      expect(parsed.secondary[1].reason).toBe('Phase mismatch')
    })

    it('should have empty secondary array when no secondary reasons', () => {
      wrapper = mountComponent({
        signal: mockSignal,
        visible: true,
      })

      const parsed = wrapper.vm.parsedRejection
      expect(parsed.secondary).toHaveLength(0)
    })
  })

  describe('Feedback Functionality', () => {
    it('should call submitFeedback with correct parameters', async () => {
      const mockResponse = {
        feedback_id: '660e8400-e29b-41d4-a716-446655440001',
        status: 'received' as const,
        message: 'Thank you for your feedback! This helps improve the system.',
      }

      vi.mocked(feedbackApi.submitFeedback).mockResolvedValue(mockResponse)

      wrapper = mountComponent({
        signal: mockSignal,
        visible: true,
      })

      await wrapper.vm.handleFeedback('positive')

      expect(feedbackApi.submitFeedback).toHaveBeenCalledWith(
        expect.objectContaining({
          signal_id: mockSignal.id,
          feedback_type: 'positive',
          explanation: null,
        })
      )
    })

    it('should emit feedbackSubmitted event after successful submission', async () => {
      const mockResponse = {
        feedback_id: '660e8400-e29b-41d4-a716-446655440001',
        status: 'received' as const,
        message: 'Thank you for your feedback!',
      }

      vi.mocked(feedbackApi.submitFeedback).mockResolvedValue(mockResponse)

      wrapper = mountComponent({
        signal: mockSignal,
        visible: true,
      })

      await wrapper.vm.handleFeedback('positive')
      await wrapper.vm.$nextTick()

      expect(wrapper.emitted('feedbackSubmitted')).toBeTruthy()
      expect(wrapper.emitted('feedbackSubmitted')![0]).toEqual(['positive'])
    })

    it('should set feedbackSubmitted flag after submission', async () => {
      const mockResponse = {
        feedback_id: '660e8400-e29b-41d4-a716-446655440001',
        status: 'received' as const,
        message: 'Thank you for your feedback!',
      }

      vi.mocked(feedbackApi.submitFeedback).mockResolvedValue(mockResponse)

      wrapper = mountComponent({
        signal: mockSignal,
        visible: true,
      })

      expect(wrapper.vm.feedbackSubmitted).toBe(false)

      await wrapper.vm.handleFeedback('positive')
      await wrapper.vm.$nextTick()

      expect(wrapper.vm.feedbackSubmitted).toBe(true)
    })

    it('should handle feedback submission error', async () => {
      vi.mocked(feedbackApi.submitFeedback).mockRejectedValue(
        new Error('API Error')
      )

      wrapper = mountComponent({
        signal: mockSignal,
        visible: true,
      })

      await wrapper.vm.handleFeedback('positive')
      await wrapper.vm.$nextTick()

      expect(feedbackApi.submitFeedback).toHaveBeenCalled()
      expect(wrapper.vm.feedbackSubmitted).toBe(false)
    })
  })

  describe('Event Emissions', () => {
    it('should emit update:visible when dialog visibility changes', async () => {
      wrapper = mountComponent({
        signal: mockSignal,
        visible: true,
      })

      const dialog = wrapper.findComponent({ name: 'Dialog' })
      await dialog.vm.$emit('update:visible', false)

      expect(wrapper.emitted('update:visible')).toBeTruthy()
      expect(wrapper.emitted('update:visible')![0]).toEqual([false])
    })

    it('should emit viewChart event with signal ID', () => {
      wrapper = mountComponent({
        signal: mockSignal,
        visible: true,
      })

      wrapper.vm.handleViewChart()

      expect(wrapper.emitted('viewChart')).toBeTruthy()
      expect(wrapper.emitted('viewChart')![0]).toEqual([mockSignal.id])
    })
  })

  describe('Ask William Feature', () => {
    it('should call handleAskWilliam without errors', () => {
      wrapper = mountComponent({
        signal: mockSignal,
        visible: true,
      })

      expect(() => wrapper.vm.handleAskWilliam()).not.toThrow()
    })
  })
})
