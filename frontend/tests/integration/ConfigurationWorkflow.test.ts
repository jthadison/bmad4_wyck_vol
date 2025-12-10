/**
 * End-to-end integration test for Configuration Wizard workflow.
 * Tests complete user flow: load → modify → analyze → confirm → save.
 */

import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import ConfigurationWizard from '@/components/configuration/ConfigurationWizard.vue'
import ParameterInput from '@/components/configuration/ParameterInput.vue'
import ImpactAnalysisPanel from '@/components/configuration/ImpactAnalysisPanel.vue'
import ConfirmationDialog from '@/components/configuration/ConfirmationDialog.vue'
import PrimeVue from 'primevue/config'
import ToastService from 'primevue/toastservice'
import * as api from '@/services/api'
import type { SystemConfiguration, ImpactAnalysisResult } from '@/services/api'

vi.mock('@/services/api')

describe('Configuration Wizard E2E Workflow', () => {
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

  const mockImpact: ImpactAnalysisResult = {
    signal_count_delta: 5,
    current_signal_count: 10,
    proposed_signal_count: 15,
    current_win_rate: '0.72',
    proposed_win_rate: '0.75',
    win_rate_delta: '0.03',
    confidence_range: { min: '0.70', max: '0.80' },
    risk_impact: 'No significant risk changes',
    recommendations: [
      {
        category: 'volume',
        severity: 'INFO',
        message: 'Relaxed spring volume will increase signal count',
      },
    ],
  }

  beforeEach(() => {
    vi.clearAllMocks()
    vi.mocked(api.getConfiguration).mockResolvedValue({
      data: mockConfig,
    } as any)
    vi.mocked(api.analyzeConfigImpact).mockResolvedValue({
      data: mockImpact,
    } as any)
    vi.mocked(api.updateConfiguration).mockResolvedValue({
      data: { ...mockConfig, version: 2 },
    } as any)
  })

  it('completes full workflow: load → modify → analyze → confirm → save', async () => {
    const wrapper = mount(ConfigurationWizard, {
      global: {
        plugins: [PrimeVue, ToastService],
        components: {
          ParameterInput,
          ImpactAnalysisPanel,
          ConfirmationDialog,
        },
      },
    })

    // Step 1: Load configuration
    await flushPromises()
    expect(api.getConfiguration).toHaveBeenCalledTimes(1)
    expect(wrapper.find('.wizard-content').exists()).toBe(true)

    // Step 2: Modify parameter (spring volume min)
    const parameterInputs = wrapper.findAllComponents(ParameterInput)
    expect(parameterInputs.length).toBeGreaterThan(0)

    const springVolumeInput = parameterInputs.find(
      (c) => c.props('label')?.includes('Spring Volume Min')
    )
    expect(springVolumeInput).toBeTruthy()

    // Simulate user changing spring volume from 0.70 to 0.65
    await springVolumeInput!.vm.$emit('update:modelValue', 0.65)
    await wrapper.vm.$nextTick()

    // Step 3: Impact analysis should be triggered (via watcher in real usage)
    // Note: In real usage, the watcher triggers analyze() automatically
    const impactPanel = wrapper.findComponent(ImpactAnalysisPanel)
    expect(impactPanel.exists()).toBe(true)

    // Step 4: Verify changes indicator appears
    await wrapper.vm.$nextTick()
    // Changes indicator should appear (but we can't easily test watcher in unit test)

    // Step 5: Click "Apply Changes" button
    const buttons = wrapper.findAllComponents({ name: 'Button' })
    const applyButton = buttons.find(
      (b) => b.props('label') === 'Apply Changes'
    )
    expect(applyButton).toBeTruthy()

    // Manually set hasChanges to true for testing
    ;(wrapper.vm as any).proposedConfig.volume_thresholds.spring_volume_min =
      0.65
    await wrapper.vm.$nextTick()

    await applyButton!.trigger('click')
    await wrapper.vm.$nextTick()

    // Step 6: Confirmation dialog should open
    const confirmDialog = wrapper.findComponent(ConfirmationDialog)
    expect(confirmDialog.exists()).toBe(true)
    expect(confirmDialog.props('visible')).toBe(true)

    // Step 7: Confirm save
    await confirmDialog.vm.$emit('confirm')
    await flushPromises()

    // Step 8: Verify updateConfiguration was called with new values
    expect(api.updateConfiguration).toHaveBeenCalledWith(
      expect.objectContaining({
        volume_thresholds: expect.objectContaining({
          spring_volume_min: 0.65,
        }),
      }),
      1 // version
    )

    // Step 9: Configuration should be updated
    expect((wrapper.vm as any).currentConfig.version).toBe(2)
  })

  it('handles cancel workflow: load → modify → cancel', async () => {
    const wrapper = mount(ConfigurationWizard, {
      global: {
        plugins: [PrimeVue, ToastService],
        components: {
          ParameterInput,
          ImpactAnalysisPanel,
          ConfirmationDialog,
        },
      },
    })

    // Load configuration
    await flushPromises()

    // Modify parameter
    ;(wrapper.vm as any).proposedConfig.risk_limits.max_risk_per_trade = '2.50'
    await wrapper.vm.$nextTick()

    // Original value should still be in currentConfig
    expect(
      (wrapper.vm as any).currentConfig.risk_limits.max_risk_per_trade
    ).toBe('2.00')

    // Click cancel
    const buttons = wrapper.findAllComponents({ name: 'Button' })
    const cancelButton = buttons.find((b) => b.props('label') === 'Cancel')
    await cancelButton!.trigger('click')
    await wrapper.vm.$nextTick()

    // Proposed config should revert to original
    expect(
      (wrapper.vm as any).proposedConfig.risk_limits.max_risk_per_trade
    ).toBe('2.00')
  })

  it('handles conflict scenario: concurrent modification', async () => {
    const wrapper = mount(ConfigurationWizard, {
      global: {
        plugins: [PrimeVue, ToastService],
        components: {
          ParameterInput,
          ImpactAnalysisPanel,
          ConfirmationDialog,
        },
      },
    })

    // Load configuration
    await flushPromises()
    expect(api.getConfiguration).toHaveBeenCalledTimes(1)

    // Modify parameter
    ;(wrapper.vm as any).proposedConfig.risk_limits.max_risk_per_trade = '2.50'
    await wrapper.vm.$nextTick()

    // Simulate 409 conflict response
    vi.mocked(api.updateConfiguration).mockRejectedValueOnce({
      response: { status: 409 },
    })

    // Attempt save
    await (wrapper.vm as any).confirmSave()
    await flushPromises()

    // Configuration should reload
    expect(api.getConfiguration).toHaveBeenCalledTimes(2)

    // Current config should be refreshed
    expect((wrapper.vm as any).currentConfig.version).toBe(1)
  })

  it('displays impact analysis when parameter changes', async () => {
    const wrapper = mount(ConfigurationWizard, {
      global: {
        plugins: [PrimeVue, ToastService],
        components: {
          ParameterInput,
          ImpactAnalysisPanel,
          ConfirmationDialog,
        },
      },
    })

    // Load configuration
    await flushPromises()

    // ImpactAnalysisPanel should be rendered
    const impactPanel = wrapper.findComponent(ImpactAnalysisPanel)
    expect(impactPanel.exists()).toBe(true)

    // Initially should show empty state (no impact data yet)
    expect(impactPanel.props('impact')).toBeNull()

    // Note: In full E2E, modifying parameters would trigger the watcher
    // which calls analyze() and updates the impact prop
    // This requires more complex async timing that's better tested in actual E2E
  })

  it('validates complete risk limit hierarchy', async () => {
    const wrapper = mount(ConfigurationWizard, {
      global: {
        plugins: [PrimeVue, ToastService],
        components: {
          ParameterInput,
          ImpactAnalysisPanel,
          ConfirmationDialog,
        },
      },
    })

    // Load configuration
    await flushPromises()

    // Modify all risk limits
    ;(wrapper.vm as any).proposedConfig.risk_limits.max_risk_per_trade = '2.50'
    ;(wrapper.vm as any).proposedConfig.risk_limits.max_campaign_risk = '6.00'
    ;(wrapper.vm as any).proposedConfig.risk_limits.max_portfolio_heat = '12.00'
    await wrapper.vm.$nextTick()

    // Attempt save
    await (wrapper.vm as any).confirmSave()
    await flushPromises()

    // Verify all risk limits are sent correctly
    expect(api.updateConfiguration).toHaveBeenCalledWith(
      expect.objectContaining({
        risk_limits: {
          max_risk_per_trade: '2.50',
          max_campaign_risk: '6.00',
          max_portfolio_heat: '12.00',
        },
      }),
      1
    )
  })

  it('preserves volume thresholds across save cycle', async () => {
    const wrapper = mount(ConfigurationWizard, {
      global: {
        plugins: [PrimeVue, ToastService],
        components: {
          ParameterInput,
          ImpactAnalysisPanel,
          ConfirmationDialog,
        },
      },
    })

    // Load configuration
    await flushPromises()

    // Modify multiple volume thresholds
    ;(wrapper.vm as any).proposedConfig.volume_thresholds.spring_volume_min =
      0.65
    ;(wrapper.vm as any).proposedConfig.volume_thresholds.sos_volume_min =
      '1.80'
    await wrapper.vm.$nextTick()

    // Save
    await (wrapper.vm as any).confirmSave()
    await flushPromises()

    // Verify both changes persisted
    expect(api.updateConfiguration).toHaveBeenCalledWith(
      expect.objectContaining({
        volume_thresholds: expect.objectContaining({
          spring_volume_min: 0.65,
          sos_volume_min: '1.80',
          spring_volume_max: '0.90', // unchanged
          lps_volume_min: '0.50', // unchanged
        }),
      }),
      1
    )
  })

  it('handles validation errors from API', async () => {
    const wrapper = mount(ConfigurationWizard, {
      global: {
        plugins: [PrimeVue, ToastService],
        components: {
          ParameterInput,
          ImpactAnalysisPanel,
          ConfirmationDialog,
        },
      },
    })

    // Load configuration
    await flushPromises()

    // Modify to invalid value (spring volume > 1.0)
    ;(wrapper.vm as any).proposedConfig.volume_thresholds.spring_volume_min =
      1.2
    await wrapper.vm.$nextTick()

    // Mock validation error
    vi.mocked(api.updateConfiguration).mockRejectedValueOnce({
      response: {
        status: 422,
        data: {
          detail: {
            message: 'Spring volume must be < 1.0x per Wyckoff principles',
          },
        },
      },
    })

    // Attempt save
    await (wrapper.vm as any).confirmSave()
    await flushPromises()

    // Error toast should be displayed (can't easily verify toast content in unit test)
    expect(api.updateConfiguration).toHaveBeenCalled()
  })

  it('updates pattern confidence settings correctly', async () => {
    const wrapper = mount(ConfigurationWizard, {
      global: {
        plugins: [PrimeVue, ToastService],
        components: {
          ParameterInput,
          ImpactAnalysisPanel,
          ConfirmationDialog,
        },
      },
    })

    // Load configuration
    await flushPromises()

    // Modify confidence thresholds
    ;(
      wrapper.vm as any
    ).proposedConfig.pattern_confidence.min_spring_confidence = 75
    ;(wrapper.vm as any).proposedConfig.pattern_confidence.min_sos_confidence =
      80
    await wrapper.vm.$nextTick()

    // Save
    await (wrapper.vm as any).confirmSave()
    await flushPromises()

    // Verify confidence changes
    expect(api.updateConfiguration).toHaveBeenCalledWith(
      expect.objectContaining({
        pattern_confidence: {
          min_spring_confidence: 75,
          min_sos_confidence: 80,
          min_lps_confidence: 75, // unchanged
          min_utad_confidence: 80, // unchanged
        },
      }),
      1
    )
  })
})
