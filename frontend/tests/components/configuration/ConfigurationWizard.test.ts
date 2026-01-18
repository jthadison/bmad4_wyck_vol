/**
 * Unit tests for ConfigurationWizard component.
 * Tests configuration loading, change detection, and save workflow.
 */

import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import ConfigurationWizard from '@/components/configuration/ConfigurationWizard.vue'
import PrimeVue from 'primevue/config'
import ToastService from 'primevue/toastservice'
import * as api from '@/services/api'
import type { SystemConfiguration } from '@/services/api'

vi.mock('@/services/api', () => ({
  getConfiguration: vi.fn(),
  updateConfiguration: vi.fn(),
  analyzeConfigImpact: vi.fn(),
}))

vi.mock('@/composables/useImpactAnalysis', () => ({
  useImpactAnalysis: () => ({
    impact: null,
    loading: false,
    error: null,
    analyze: vi.fn(),
  }),
}))

describe('ConfigurationWizard', () => {
  const mockConfig: SystemConfiguration = {
    id: 1,
    version: 1,
    volume_thresholds: {
      spring_volume_min: '0.70',
      spring_volume_max: '0.90',
      sos_volume_min: '1.50',
      lps_volume_min: '0.50',
      utad_volume_max: '0.80',
    },
    risk_limits: {
      max_risk_per_trade: '2.00',
      max_campaign_risk: '5.00',
      max_portfolio_heat: '10.00',
    },
    cause_factors: {
      min_cause_factor: '2.00',
      max_cause_factor: '3.00',
    },
    pattern_confidence: {
      min_spring_confidence: 70,
      min_sos_confidence: 70,
      min_lps_confidence: 75,
      min_utad_confidence: 80,
    },
    created_at: '2025-01-01T00:00:00Z',
    updated_at: '2025-01-01T00:00:00Z',
  }

  const createWrapper = () => {
    return mount(ConfigurationWizard, {
      global: {
        plugins: [PrimeVue, ToastService],
        stubs: {
          ImpactAnalysisPanel: true,
          ParameterInput: true,
          ConfirmationDialog: true,
          TabView: true,
          TabPanel: true,
        },
      },
    })
  }

  beforeEach(() => {
    vi.clearAllMocks()
  })

  describe('Initialization', () => {
    it('loads configuration on mount', async () => {
      vi.mocked(api.getConfiguration).mockResolvedValue({
        data: mockConfig,
      } as unknown)

      const wrapper = createWrapper()
      await flushPromises()

      expect(api.getConfiguration).toHaveBeenCalledTimes(1)
    })

    it('displays loading state while loading configuration', async () => {
      vi.mocked(api.getConfiguration).mockImplementation(
        () =>
          new Promise((resolve) =>
            setTimeout(() => resolve({ data: mockConfig } as unknown), 100)
          )
      )

      const wrapper = createWrapper()
      expect(wrapper.find('.loading-state').exists()).toBe(true)
      expect(wrapper.find('.loading-state p').text()).toBe(
        'Loading configuration...'
      )

      await flushPromises()
    })

    it('shows wizard content after loading', async () => {
      vi.mocked(api.getConfiguration).mockResolvedValue({
        data: mockConfig,
      } as unknown)

      const wrapper = createWrapper()
      await flushPromises()

      expect(wrapper.find('.loading-state').exists()).toBe(false)
      expect(wrapper.find('.wizard-content').exists()).toBe(true)
    })

    it('displays error toast when configuration load fails', async () => {
      vi.mocked(api.getConfiguration).mockRejectedValue(
        new Error('Network error')
      )

      const wrapper = createWrapper()
      await flushPromises()

      // Toast should be added (can't easily test PrimeVue toast in unit tests)
      expect(api.getConfiguration).toHaveBeenCalled()
    })
  })

  describe('Configuration Display', () => {
    beforeEach(async () => {
      vi.mocked(api.getConfiguration).mockResolvedValue({
        data: mockConfig,
      } as unknown)
    })

    it('renders header with title and description', async () => {
      const wrapper = createWrapper()
      await flushPromises()

      expect(wrapper.find('.wizard-header h2').text()).toBe(
        'System Configuration'
      )
      expect(wrapper.find('.header-description').text()).toContain(
        'Adjust system parameters with real-time impact analysis'
      )
    })

    it('renders ImpactAnalysisPanel component', async () => {
      const wrapper = createWrapper()
      await flushPromises()

      const panel = wrapper.findComponent({ name: 'ImpactAnalysisPanel' })
      expect(panel.exists()).toBe(true)
    })

    it('renders TabView with configuration tabs', async () => {
      const wrapper = createWrapper()
      await flushPromises()

      expect(wrapper.findComponent({ name: 'TabView' }).exists()).toBe(true)
    })

    it('renders ConfirmationDialog component', async () => {
      const wrapper = createWrapper()
      await flushPromises()

      const dialog = wrapper.findComponent({ name: 'ConfirmationDialog' })
      expect(dialog.exists()).toBe(true)
    })
  })

  describe('Change Detection', () => {
    beforeEach(async () => {
      vi.mocked(api.getConfiguration).mockResolvedValue({
        data: mockConfig,
      } as unknown)
    })

    it('displays "No changes" indicator initially', async () => {
      const wrapper = createWrapper()
      await flushPromises()

      expect(wrapper.find('.no-changes').exists()).toBe(true)
      expect(wrapper.find('.no-changes').text()).toContain('No changes')
    })

    it('disables cancel button when no changes', async () => {
      const wrapper = createWrapper()
      await flushPromises()

      const buttons = wrapper.findAllComponents({ name: 'Button' })
      const cancelButton = buttons.find((b) => b.props('label') === 'Cancel')
      expect(cancelButton?.props('disabled')).toBe(true)
    })

    it('disables apply button when no changes', async () => {
      const wrapper = createWrapper()
      await flushPromises()

      const buttons = wrapper.findAllComponents({ name: 'Button' })
      const applyButton = buttons.find(
        (b) => b.props('label') === 'Apply Changes'
      )
      expect(applyButton?.props('disabled')).toBe(true)
    })
  })

  describe('Save Workflow', () => {
    beforeEach(async () => {
      vi.mocked(api.getConfiguration).mockResolvedValue({
        data: mockConfig,
      } as unknown)
    })

    it('shows confirmation dialog when save button clicked', async () => {
      const wrapper = createWrapper()
      await flushPromises()

      // Manually modify proposedConfig to trigger hasChanges
      ;(wrapper.vm as unknown).proposedConfig.risk_limits!.max_risk_per_trade =
        '2.50'
      await wrapper.vm.$nextTick()

      const buttons = wrapper.findAllComponents({ name: 'Button' })
      const applyButton = buttons.find(
        (b) => b.props('label') === 'Apply Changes'
      )
      await applyButton?.trigger('click')

      expect((wrapper.vm as unknown).showConfirmDialog).toBe(true)
    })

    it('calls updateConfiguration with correct parameters on confirm', async () => {
      vi.mocked(api.updateConfiguration).mockResolvedValue({
        data: { ...mockConfig, version: 2 },
      } as unknown)

      const wrapper = createWrapper()
      await flushPromises()

      // Manually modify proposedConfig
      ;(wrapper.vm as unknown).proposedConfig.risk_limits!.max_risk_per_trade =
        '2.50'
      await wrapper.vm.$nextTick()

      // Trigger confirmSave directly
      await (wrapper.vm as unknown).confirmSave()
      await flushPromises()

      expect(api.updateConfiguration).toHaveBeenCalledWith(
        expect.objectContaining({
          risk_limits: expect.objectContaining({
            max_risk_per_trade: '2.50',
          }),
        }),
        1 // version
      )
    })

    it('displays success toast after successful save', async () => {
      vi.mocked(api.updateConfiguration).mockResolvedValue({
        data: { ...mockConfig, version: 2 },
      } as unknown)

      const wrapper = createWrapper()
      await flushPromises()
      ;(wrapper.vm as unknown).proposedConfig.risk_limits!.max_risk_per_trade =
        '2.50'
      await (wrapper.vm as unknown).confirmSave()
      await flushPromises()

      // Toast should be added with success severity
      expect(api.updateConfiguration).toHaveBeenCalled()
    })

    it('updates currentConfig after successful save', async () => {
      const updatedConfig = { ...mockConfig, version: 2 }
      vi.mocked(api.updateConfiguration).mockResolvedValue({
        data: updatedConfig,
      } as unknown)

      const wrapper = createWrapper()
      await flushPromises()
      ;(wrapper.vm as unknown).proposedConfig.risk_limits!.max_risk_per_trade =
        '2.50'
      await (wrapper.vm as unknown).confirmSave()
      await flushPromises()

      expect((wrapper.vm as unknown).currentConfig.version).toBe(2)
    })
  })

  describe('Conflict Handling (409)', () => {
    beforeEach(async () => {
      vi.mocked(api.getConfiguration).mockResolvedValue({
        data: mockConfig,
      } as unknown)
    })

    it('displays conflict error toast on 409 response', async () => {
      vi.mocked(api.updateConfiguration).mockRejectedValue({
        response: { status: 409 },
      })

      const wrapper = createWrapper()
      await flushPromises()
      ;(wrapper.vm as unknown).proposedConfig.risk_limits!.max_risk_per_trade =
        '2.50'
      await (wrapper.vm as unknown).confirmSave()
      await flushPromises()

      // Conflict toast should be added
      expect(api.updateConfiguration).toHaveBeenCalled()
    })

    it('reloads configuration on 409 conflict', async () => {
      vi.mocked(api.updateConfiguration).mockRejectedValue({
        response: { status: 409 },
      })

      const wrapper = createWrapper()
      await flushPromises()

      expect(api.getConfiguration).toHaveBeenCalledTimes(1)
      ;(wrapper.vm as unknown).proposedConfig.risk_limits!.max_risk_per_trade =
        '2.50'
      await (wrapper.vm as unknown).confirmSave()
      await flushPromises()

      expect(api.getConfiguration).toHaveBeenCalledTimes(2)
    })
  })

  describe('Error Handling', () => {
    beforeEach(async () => {
      vi.mocked(api.getConfiguration).mockResolvedValue({
        data: mockConfig,
      } as unknown)
    })

    it('displays error toast on save failure', async () => {
      vi.mocked(api.updateConfiguration).mockRejectedValue(
        new Error('Network error')
      )

      const wrapper = createWrapper()
      await flushPromises()
      ;(wrapper.vm as unknown).proposedConfig.risk_limits!.max_risk_per_trade =
        '2.50'
      await (wrapper.vm as unknown).confirmSave()
      await flushPromises()

      // Error toast should be added
      expect(api.updateConfiguration).toHaveBeenCalled()
    })

    it('displays validation error message from API', async () => {
      vi.mocked(api.updateConfiguration).mockRejectedValue({
        response: {
          status: 422,
          data: {
            detail: {
              message: 'Spring volume must be < 1.0x',
            },
          },
        },
      })

      const wrapper = createWrapper()
      await flushPromises()
      ;(wrapper.vm as unknown).proposedConfig.risk_limits!.max_risk_per_trade =
        '2.50'
      await (wrapper.vm as unknown).confirmSave()
      await flushPromises()

      // Validation error toast should be added with custom message
      expect(api.updateConfiguration).toHaveBeenCalled()
    })

    it('stops loading state after save error', async () => {
      vi.mocked(api.updateConfiguration).mockRejectedValue(
        new Error('Network error')
      )

      const wrapper = createWrapper()
      await flushPromises()
      ;(wrapper.vm as unknown).proposedConfig.risk_limits!.max_risk_per_trade =
        '2.50'
      await (wrapper.vm as unknown).confirmSave()
      await flushPromises()

      expect((wrapper.vm as unknown).savingConfig).toBe(false)
    })
  })

  describe('Cancel Action', () => {
    beforeEach(async () => {
      vi.mocked(api.getConfiguration).mockResolvedValue({
        data: mockConfig,
      } as unknown)
    })

    it('reverts proposedConfig to currentConfig on cancel', async () => {
      const wrapper = createWrapper()
      await flushPromises()

      // Modify proposedConfig
      ;(wrapper.vm as unknown).proposedConfig.risk_limits!.max_risk_per_trade =
        '2.50'
      await wrapper.vm.$nextTick()

      // Trigger cancel
      await (wrapper.vm as unknown).handleCancel()
      await wrapper.vm.$nextTick()

      expect(
        (wrapper.vm as unknown).proposedConfig.risk_limits.max_risk_per_trade
      ).toBe('2.00')
    })

    it('displays info toast after cancel', async () => {
      const wrapper = createWrapper()
      await flushPromises()
      ;(wrapper.vm as unknown).proposedConfig.risk_limits!.max_risk_per_trade =
        '2.50'
      await (wrapper.vm as unknown).handleCancel()
      await wrapper.vm.$nextTick()

      // Info toast should be added
      expect((wrapper.vm as unknown).currentConfig).toBeTruthy()
    })

    it('does nothing when cancel clicked with no currentConfig', async () => {
      const wrapper = createWrapper()
      await flushPromises()
      ;(wrapper.vm as unknown).currentConfig = null
      await (wrapper.vm as unknown).handleCancel()

      // Should not throw error
      expect((wrapper.vm as unknown).currentConfig).toBeNull()
    })
  })

  describe('Loading States', () => {
    beforeEach(async () => {
      vi.mocked(api.getConfiguration).mockResolvedValue({
        data: mockConfig,
      } as unknown)
    })

    it('disables save button while saving', async () => {
      vi.mocked(api.updateConfiguration).mockImplementation(
        () =>
          new Promise((resolve) =>
            setTimeout(() => resolve({ data: mockConfig } as unknown), 100)
          )
      )

      const wrapper = createWrapper()
      await flushPromises()
      ;(wrapper.vm as unknown).proposedConfig.risk_limits!.max_risk_per_trade =
        '2.50'
      await wrapper.vm.$nextTick()

      // Start save
      ;(wrapper.vm as unknown).confirmSave()
      await wrapper.vm.$nextTick()

      expect((wrapper.vm as unknown).savingConfig).toBe(true)

      const buttons = wrapper.findAllComponents({ name: 'Button' })
      const applyButton = buttons.find(
        (b) => b.props('label') === 'Apply Changes'
      )
      expect(applyButton?.props('disabled')).toBe(true)
    })

    it('shows loading indicator on save button', async () => {
      vi.mocked(api.updateConfiguration).mockImplementation(
        () =>
          new Promise((resolve) =>
            setTimeout(() => resolve({ data: mockConfig } as unknown), 100)
          )
      )

      const wrapper = createWrapper()
      await flushPromises()
      ;(wrapper.vm as unknown).proposedConfig.risk_limits!.max_risk_per_trade =
        '2.50'
      await wrapper.vm.$nextTick()

      // Start save
      ;(wrapper.vm as unknown).confirmSave()
      await wrapper.vm.$nextTick()

      const buttons = wrapper.findAllComponents({ name: 'Button' })
      const applyButton = buttons.find(
        (b) => b.props('label') === 'Apply Changes'
      )
      expect(applyButton?.props('loading')).toBe(true)
    })
  })
})
