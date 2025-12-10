<script setup lang="ts">
import { ref, reactive, computed, onMounted, watch } from 'vue'
import { useToast } from 'primevue/usetoast'
import TabView from 'primevue/tabview'
import TabPanel from 'primevue/tabpanel'
import Button from 'primevue/button'
import Toast from 'primevue/toast'
import {
  getConfiguration,
  updateConfiguration,
  type SystemConfiguration,
} from '@/services/api'
import ParameterInput from './ParameterInput.vue'
import ImpactAnalysisPanel from './ImpactAnalysisPanel.vue'
import ConfirmationDialog from './ConfirmationDialog.vue'
import { useImpactAnalysis } from '@/composables/useImpactAnalysis'

const toast = useToast()

// State
const currentConfig = ref<SystemConfiguration | null>(null)
const proposedConfig = reactive<Partial<SystemConfiguration>>({})
const loadingConfig = ref(false)
const savingConfig = ref(false)
const showConfirmDialog = ref(false)

// Impact analysis composable
const {
  impact,
  loading: analyzingImpact,
  error: impactError,
  analyze,
} = useImpactAnalysis()

// Computed
const hasChanges = computed(() => {
  if (!currentConfig.value) return false
  return JSON.stringify(proposedConfig) !== JSON.stringify(currentConfig.value)
})

const canSave = computed(() => {
  return hasChanges.value && !savingConfig.value && !loadingConfig.value
})

// Load current configuration
async function loadConfiguration() {
  loadingConfig.value = true
  try {
    const response = await getConfiguration()
    currentConfig.value = response.data
    Object.assign(proposedConfig, response.data)
  } catch (error: any) {
    toast.add({
      severity: 'error',
      summary: 'Error',
      detail: 'Failed to load configuration',
      life: 5000,
    })
  } finally {
    loadingConfig.value = false
  }
}

// Watch for changes and trigger impact analysis
watch(
  () => ({ ...proposedConfig }),
  (newConfig) => {
    if (hasChanges.value && currentConfig.value) {
      analyze(newConfig as SystemConfiguration)
    }
  },
  { deep: true }
)

// Handle save
async function handleSave() {
  showConfirmDialog.value = true
}

// Confirm and apply changes
async function confirmSave() {
  if (!currentConfig.value || !proposedConfig) return

  savingConfig.value = true
  try {
    const response = await updateConfiguration(
      proposedConfig as SystemConfiguration,
      currentConfig.value.version
    )

    currentConfig.value = response.data
    Object.assign(proposedConfig, response.data)

    toast.add({
      severity: 'success',
      summary: 'Success',
      detail: 'Configuration updated successfully',
      life: 3000,
    })
  } catch (error: any) {
    if (error.response?.status === 409) {
      toast.add({
        severity: 'error',
        summary: 'Conflict',
        detail: 'Configuration was modified by another user. Please reload.',
        life: 5000,
      })
      await loadConfiguration()
    } else {
      toast.add({
        severity: 'error',
        summary: 'Error',
        detail:
          error.response?.data?.detail?.message ||
          'Failed to save configuration',
        life: 5000,
      })
    }
  } finally {
    savingConfig.value = false
  }
}

// Handle cancel
function handleCancel() {
  if (!currentConfig.value) return
  Object.assign(proposedConfig, currentConfig.value)
  toast.add({
    severity: 'info',
    summary: 'Cancelled',
    detail: 'Changes reverted to current configuration',
    life: 3000,
  })
}

// Initialize
onMounted(() => {
  loadConfiguration()
})
</script>

<template>
  <div class="configuration-wizard">
    <Toast />

    <div class="wizard-header">
      <h2>System Configuration</h2>
      <p class="header-description">
        Adjust system parameters with real-time impact analysis. All changes
        follow Wyckoff methodology principles.
      </p>
    </div>

    <div v-if="loadingConfig" class="loading-state">
      <i class="pi pi-spin pi-spinner" style="font-size: 2rem"></i>
      <p>Loading configuration...</p>
    </div>

    <div v-else-if="currentConfig" class="wizard-content">
      <!-- Impact Analysis Panel -->
      <ImpactAnalysisPanel
        :impact="impact"
        :loading="analyzingImpact"
        :error="impactError"
      />

      <!-- Configuration Tabs -->
      <TabView class="config-tabs">
        <!-- Volume Thresholds -->
        <TabPanel header="Volume Thresholds">
          <div class="tab-content">
            <p class="tab-description">
              Volume ratios relative to average volume (1.0x = average). Wyckoff
              principles require springs to show low volume and SOS to show high
              volume.
            </p>

            <ParameterInput
              label="Spring Volume Min"
              v-model="proposedConfig.volume_thresholds!.spring_volume_min"
              :current-value="
                parseFloat(currentConfig.volume_thresholds.spring_volume_min)
              "
              :min="0.5"
              :max="1.0"
              :step="0.05"
              unit="x"
              help-text="Minimum volume for Spring detection. Must be < 1.0x per Wyckoff (low volume = lack of selling)."
            />

            <ParameterInput
              label="Spring Volume Max"
              v-model="proposedConfig.volume_thresholds!.spring_volume_max"
              :current-value="
                parseFloat(currentConfig.volume_thresholds.spring_volume_max)
              "
              :min="0.5"
              :max="1.0"
              :step="0.05"
              unit="x"
              help-text="Maximum volume for Spring detection."
            />

            <ParameterInput
              label="SOS Volume Min"
              v-model="proposedConfig.volume_thresholds!.sos_volume_min"
              :current-value="
                parseFloat(currentConfig.volume_thresholds.sos_volume_min)
              "
              :min="1.5"
              :max="3.0"
              :step="0.1"
              unit="x"
              help-text="Minimum volume for Sign of Strength. Must be ≥ 1.5x to confirm demand."
            />

            <ParameterInput
              label="LPS Volume Min"
              v-model="proposedConfig.volume_thresholds!.lps_volume_min"
              :current-value="
                parseFloat(currentConfig.volume_thresholds.lps_volume_min)
              "
              :min="0.3"
              :max="1.0"
              :step="0.05"
              unit="x"
              help-text="Minimum volume for Last Point of Support detection."
            />

            <ParameterInput
              label="UTAD Volume Max"
              v-model="proposedConfig.volume_thresholds!.utad_volume_max"
              :current-value="
                parseFloat(currentConfig.volume_thresholds.utad_volume_max)
              "
              :min="0.3"
              :max="1.0"
              :step="0.05"
              unit="x"
              help-text="Maximum volume for Upthrust After Distribution."
            />
          </div>
        </TabPanel>

        <!-- Risk Limits -->
        <TabPanel header="Risk Limits">
          <div class="tab-content">
            <p class="tab-description">
              Risk management limits as percentages of account equity. Must
              satisfy: per-trade &lt; campaign &lt; portfolio heat.
            </p>

            <ParameterInput
              label="Max Risk Per Trade"
              v-model="proposedConfig.risk_limits!.max_risk_per_trade"
              :current-value="
                parseFloat(currentConfig.risk_limits.max_risk_per_trade)
              "
              :min="1.0"
              :max="3.0"
              :step="0.1"
              unit="%"
              help-text="Maximum risk per individual trade."
            />

            <ParameterInput
              label="Max Campaign Risk"
              v-model="proposedConfig.risk_limits!.max_campaign_risk"
              :current-value="
                parseFloat(currentConfig.risk_limits.max_campaign_risk)
              "
              :min="3.0"
              :max="7.0"
              :step="0.5"
              unit="%"
              help-text="Maximum total risk across all positions in a campaign."
            />

            <ParameterInput
              label="Max Portfolio Heat"
              v-model="proposedConfig.risk_limits!.max_portfolio_heat"
              :current-value="
                parseFloat(currentConfig.risk_limits.max_portfolio_heat)
              "
              :min="5.0"
              :max="15.0"
              :step="0.5"
              unit="%"
              help-text="Maximum total risk exposure across entire portfolio."
            />
          </div>
        </TabPanel>

        <!-- Cause Factors -->
        <TabPanel header="Cause Factors">
          <div class="tab-content">
            <p class="tab-description">
              Cause-to-effect ratio per Wyckoff methodology. A 2:1 ratio means
              accumulation is 2x the expected move duration. Minimum 2.0
              required.
            </p>

            <ParameterInput
              label="Min Cause Factor"
              v-model="proposedConfig.cause_factors!.min_cause_factor"
              :current-value="
                parseFloat(currentConfig.cause_factors.min_cause_factor)
              "
              :min="2.0"
              :max="2.5"
              :step="0.1"
              help-text="Minimum cause-to-effect ratio. Wyckoff requires ≥ 2.0 for reliable projections."
            />

            <ParameterInput
              label="Max Cause Factor"
              v-model="proposedConfig.cause_factors!.max_cause_factor"
              :current-value="
                parseFloat(currentConfig.cause_factors.max_cause_factor)
              "
              :min="2.5"
              :max="4.0"
              :step="0.1"
              help-text="Maximum cause-to-effect ratio for filtering extended patterns."
            />
          </div>
        </TabPanel>

        <!-- Pattern Confidence -->
        <TabPanel header="Pattern Confidence">
          <div class="tab-content">
            <p class="tab-description">
              Minimum confidence thresholds for pattern-based signals. Range:
              70-95. Higher values = fewer but higher quality signals.
            </p>

            <ParameterInput
              label="Min Spring Confidence"
              v-model="proposedConfig.pattern_confidence!.min_spring_confidence"
              :current-value="
                currentConfig.pattern_confidence.min_spring_confidence
              "
              :min="70"
              :max="95"
              :step="5"
              unit="%"
              help-text="Minimum confidence for Spring signals."
            />

            <ParameterInput
              label="Min SOS Confidence"
              v-model="proposedConfig.pattern_confidence!.min_sos_confidence"
              :current-value="
                currentConfig.pattern_confidence.min_sos_confidence
              "
              :min="70"
              :max="95"
              :step="5"
              unit="%"
              help-text="Minimum confidence for Sign of Strength signals."
            />

            <ParameterInput
              label="Min LPS Confidence"
              v-model="proposedConfig.pattern_confidence!.min_lps_confidence"
              :current-value="
                currentConfig.pattern_confidence.min_lps_confidence
              "
              :min="70"
              :max="95"
              :step="5"
              unit="%"
              help-text="Minimum confidence for Last Point of Support signals."
            />

            <ParameterInput
              label="Min UTAD Confidence"
              v-model="proposedConfig.pattern_confidence!.min_utad_confidence"
              :current-value="
                currentConfig.pattern_confidence.min_utad_confidence
              "
              :min="70"
              :max="95"
              :step="5"
              unit="%"
              help-text="Minimum confidence for UTAD signals."
            />
          </div>
        </TabPanel>
      </TabView>

      <!-- Action Buttons -->
      <div class="wizard-footer">
        <div class="footer-info">
          <span v-if="hasChanges" class="changes-indicator">
            <i class="pi pi-exclamation-circle"></i>
            Unsaved changes
          </span>
          <span v-else class="no-changes">
            <i class="pi pi-check-circle"></i>
            No changes
          </span>
        </div>

        <div class="footer-actions">
          <Button
            label="Cancel"
            icon="pi pi-times"
            @click="handleCancel"
            severity="secondary"
            outlined
            :disabled="!hasChanges"
          />
          <Button
            label="Apply Changes"
            icon="pi pi-check"
            @click="handleSave"
            :disabled="!canSave"
            :loading="savingConfig"
          />
        </div>
      </div>
    </div>

    <!-- Confirmation Dialog -->
    <ConfirmationDialog
      v-model:visible="showConfirmDialog"
      :impact="impact"
      change-description="This will update system configuration and affect future signal generation."
      @confirm="confirmSave"
      @cancel="showConfirmDialog = false"
    />
  </div>
</template>

<style scoped>
.configuration-wizard {
  max-width: 1200px;
  margin: 0 auto;
  padding: 2rem;
}

.wizard-header {
  margin-bottom: 2rem;
}

.wizard-header h2 {
  font-size: 1.75rem;
  font-weight: 700;
  color: var(--text-color);
  margin: 0 0 0.5rem 0;
}

.header-description {
  font-size: 1rem;
  color: var(--text-color-secondary);
  margin: 0;
}

.loading-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 4rem 2rem;
  color: var(--text-color-secondary);
}

.loading-state p {
  margin-top: 1rem;
}

.wizard-content {
  display: flex;
  flex-direction: column;
  gap: 1.5rem;
}

.config-tabs {
  background: white;
  border-radius: 8px;
  border: 1px solid var(--surface-200);
}

.tab-content {
  padding: 1.5rem;
}

.tab-description {
  font-size: 0.9375rem;
  color: var(--text-color-secondary);
  margin-bottom: 1.5rem;
  padding: 1rem;
  background: var(--blue-50);
  border-left: 3px solid var(--blue-500);
  border-radius: 4px;
}

.wizard-footer {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 1.5rem;
  background: white;
  border: 1px solid var(--surface-200);
  border-radius: 8px;
}

.footer-info {
  display: flex;
  align-items: center;
}

.changes-indicator {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  color: var(--yellow-700);
  font-weight: 600;
}

.no-changes {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  color: var(--green-700);
}

.footer-actions {
  display: flex;
  gap: 0.75rem;
}
</style>
