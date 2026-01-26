<template>
  <div class="auto-execution-settings">
    <!-- Loading State -->
    <div
      v-if="loading && !config"
      class="flex justify-center items-center py-12"
    >
      <ProgressSpinner />
    </div>

    <!-- Content -->
    <div v-else-if="config" class="space-y-6">
      <!-- Warning Banner (Active) -->
      <Message
        v-if="isEnabled && !isKillSwitchActive"
        severity="warn"
        :closable="false"
        class="shadow-lg"
      >
        <div class="flex items-center gap-2">
          <i class="pi pi-exclamation-triangle text-xl"></i>
          <div>
            <p class="font-bold">AUTO-EXECUTION IS ACTIVE</p>
            <p class="text-sm mt-1">
              Trades will execute automatically for qualifying signals. Use kill
              switch to stop immediately.
            </p>
          </div>
        </div>
      </Message>

      <!-- Kill Switch Banner (Active) -->
      <Message
        v-if="isKillSwitchActive"
        severity="error"
        :closable="false"
        class="shadow-lg"
      >
        <div class="flex items-center justify-between">
          <div class="flex items-center gap-2">
            <i class="pi pi-ban text-xl"></i>
            <div>
              <p class="font-bold">KILL SWITCH ACTIVE</p>
              <p class="text-sm mt-1">
                All automatic trading is stopped. Settings remain but are
                inactive.
              </p>
            </div>
          </div>
          <Button
            label="Deactivate"
            severity="secondary"
            size="small"
            @click="handleDeactivateKillSwitch"
            :loading="loading"
          />
        </div>
      </Message>

      <!-- Master Toggle Card -->
      <Card>
        <template #title>
          <div class="flex items-center justify-between">
            <span>Auto-Execution</span>
            <InputSwitch
              :model-value="isEnabled"
              @update:model-value="handleMasterToggle"
              :disabled="loading || isKillSwitchActive"
            />
          </div>
        </template>
        <template #content>
          <p v-if="!isEnabled" class="text-gray-600 dark:text-gray-400 text-sm">
            Enable auto-execution to configure automatic trade settings.
          </p>
          <p
            v-else-if="consentGiven"
            class="text-sm text-gray-600 dark:text-gray-400"
          >
            Consent given on {{ formatDate(config.consent_given_at!) }}
          </p>
        </template>
      </Card>

      <!-- Settings Form (Enabled State) -->
      <div v-if="isEnabled" class="space-y-6">
        <!-- Confidence and Limits Card -->
        <Card>
          <template #title>Risk and Trade Limits</template>
          <template #content>
            <div class="space-y-6">
              <!-- Confidence Threshold -->
              <div>
                <label
                  class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2"
                >
                  Minimum Confidence: {{ config.min_confidence }}%
                </label>
                <Slider
                  :model-value="Number(config.min_confidence)"
                  @update:model-value="updateMinConfidence"
                  :min="60"
                  :max="100"
                  :step="5"
                  :disabled="loading || isKillSwitchActive"
                  class="w-full"
                />
                <small class="text-gray-500 dark:text-gray-400">
                  Only signals with confidence ≥ {{ config.min_confidence }}%
                  will execute automatically
                </small>
              </div>

              <!-- Max Trades Per Day -->
              <div>
                <label
                  for="max-trades"
                  class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2"
                >
                  Max Trades Per Day
                </label>
                <InputNumber
                  id="max-trades"
                  :model-value="config.max_trades_per_day"
                  @update:model-value="updateMaxTrades"
                  :min="1"
                  :max="50"
                  :disabled="loading || isKillSwitchActive"
                  show-buttons
                  class="w-full"
                />
              </div>

              <!-- Max Risk Per Day -->
              <div>
                <label
                  for="max-risk"
                  class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2"
                >
                  Max Risk Per Day (%)
                </label>
                <InputNumber
                  id="max-risk"
                  :model-value="
                    config.max_risk_per_day
                      ? Number(config.max_risk_per_day)
                      : null
                  "
                  @update:model-value="updateMaxRisk"
                  :min="0"
                  :max="10"
                  :min-fraction-digits="1"
                  :max-fraction-digits="2"
                  :disabled="loading || isKillSwitchActive"
                  show-buttons
                  :step="0.5"
                  suffix="%"
                  class="w-full"
                />
                <small class="text-gray-500 dark:text-gray-400">
                  Leave empty for no daily risk limit
                </small>
              </div>
            </div>
          </template>
        </Card>

        <!-- Pattern Selection Card -->
        <Card>
          <template #title>Enabled Patterns</template>
          <template #content>
            <PatternSelector
              :model-value="config.enabled_patterns"
              @update:model-value="updateEnabledPatterns"
              :disabled="loading || isKillSwitchActive"
              help-text="Select which Wyckoff patterns should trigger automatic execution"
            />
          </template>
        </Card>

        <!-- Symbol Filters Card -->
        <Card>
          <template #title>Symbol Filters</template>
          <template #content>
            <div class="space-y-6">
              <!-- Whitelist -->
              <SymbolListEditor
                :model-value="config.symbol_whitelist || []"
                @update:model-value="updateSymbolWhitelist"
                label="Symbol Whitelist"
                placeholder="Add symbol (e.g., AAPL)"
                empty-message="All symbols allowed"
                help-text="Only these symbols will execute automatically (leave empty to allow all)"
                :disabled="loading || isKillSwitchActive"
              />

              <Divider />

              <!-- Blacklist -->
              <SymbolListEditor
                :model-value="config.symbol_blacklist || []"
                @update:model-value="updateSymbolBlacklist"
                label="Symbol Blacklist"
                placeholder="Add symbol (e.g., MEME)"
                empty-message="No symbols blocked"
                help-text="These symbols will never execute automatically"
                :disabled="loading || isKillSwitchActive"
              />
            </div>
          </template>
        </Card>

        <!-- Daily Statistics Card -->
        <Card>
          <template #title>Today's Activity</template>
          <template #content>
            <div class="space-y-4">
              <!-- Trades Progress -->
              <div>
                <div class="flex justify-between mb-2">
                  <span
                    class="text-sm font-medium text-gray-700 dark:text-gray-300"
                    >Trades Today</span
                  >
                  <span class="text-sm font-bold">
                    {{ config.trades_today }} / {{ config.max_trades_per_day }}
                  </span>
                </div>
                <ProgressBar
                  :value="tradesPercentage"
                  :severity="tradesProgressSeverity"
                />
              </div>

              <!-- Risk Progress -->
              <div v-if="config.max_risk_per_day">
                <div class="flex justify-between mb-2">
                  <span
                    class="text-sm font-medium text-gray-700 dark:text-gray-300"
                    >Risk Today</span
                  >
                  <span class="text-sm font-bold">
                    {{ config.risk_today }}% / {{ config.max_risk_per_day }}%
                  </span>
                </div>
                <ProgressBar
                  :value="riskPercentage"
                  :severity="riskProgressSeverity"
                />
              </div>
            </div>
          </template>
        </Card>

        <!-- Kill Switch Card -->
        <Card class="border-2 border-red-300 dark:border-red-800">
          <template #title>
            <span class="text-red-600 dark:text-red-400"
              >Emergency Kill Switch</span
            >
          </template>
          <template #content>
            <div class="space-y-3">
              <p class="text-sm text-gray-600 dark:text-gray-400">
                Immediately stops all automatic trade execution. Use this if you
                need to halt trading due to market volatility, system issues, or
                unexpected behavior.
              </p>
              <Button
                label="KILL SWITCH - Stop All Automatic Trading"
                severity="danger"
                icon="pi pi-ban"
                @click="showKillSwitchConfirm = true"
                :disabled="loading || isKillSwitchActive"
                class="w-full"
              />
            </div>
          </template>
        </Card>
      </div>
    </div>

    <!-- Consent Modal -->
    <ConsentModal
      :visible="showConsentModal"
      :loading="loading"
      :error="error"
      @enable="handleEnableWithConsent"
      @cancel="handleCancelConsent"
    />

    <!-- Kill Switch Confirmation -->
    <Dialog
      v-model:visible="showKillSwitchConfirm"
      modal
      header="Activate Kill Switch?"
      style="width: 500px; max-width: 90vw"
    >
      <p class="text-gray-700 dark:text-gray-300">
        This will immediately stop all automatic trading. Are you sure you want
        to activate the kill switch?
      </p>
      <template #footer>
        <Button
          label="Cancel"
          severity="secondary"
          @click="showKillSwitchConfirm = false"
        />
        <Button
          label="Activate Kill Switch"
          severity="danger"
          icon="pi pi-ban"
          @click="handleActivateKillSwitch"
          :loading="loading"
        />
      </template>
    </Dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useAutoExecutionStore } from '@/stores/autoExecutionStore'
import { storeToRefs } from 'pinia'
import Card from 'primevue/card'
import Button from 'primevue/button'
import InputSwitch from 'primevue/inputswitch'
import InputNumber from 'primevue/inputnumber'
import Slider from 'primevue/slider'
import ProgressBar from 'primevue/progressbar'
import ProgressSpinner from 'primevue/progressspinner'
import Message from 'primevue/message'
import Dialog from 'primevue/dialog'
import Divider from 'primevue/divider'
import ConsentModal from '@/components/settings/ConsentModal.vue'
import PatternSelector from '@/components/settings/PatternSelector.vue'
import SymbolListEditor from '@/components/settings/SymbolListEditor.vue'
import type { PatternType } from '@/types/auto-execution'

const store = useAutoExecutionStore()
const {
  config,
  loading,
  error,
  isEnabled,
  isKillSwitchActive,
  consentGiven,
  tradesPercentage,
  riskPercentage,
  tradesProgressSeverity,
  riskProgressSeverity,
} = storeToRefs(store)

const showConsentModal = ref(false)
const showKillSwitchConfirm = ref(false)

onMounted(() => {
  store.fetchConfig()
})

function handleMasterToggle(enabled: boolean): void {
  if (enabled) {
    showConsentModal.value = true
  } else {
    store.disable()
  }
}

async function handleEnableWithConsent(password: string): Promise<void> {
  try {
    await store.enable({
      consent_acknowledged: true,
      password,
    })
    showConsentModal.value = false
  } catch (err) {
    // Error is handled by the store and displayed in the modal
  }
}

function handleCancelConsent(): void {
  showConsentModal.value = false
}

async function handleActivateKillSwitch(): Promise<void> {
  try {
    await store.activateEmergencyKillSwitch()
    showKillSwitchConfirm.value = false
  } catch (err) {
    // Error is handled by the store
  }
}

async function handleDeactivateKillSwitch(): Promise<void> {
  try {
    await store.deactivateEmergencyKillSwitch()
  } catch (err) {
    // Error is handled by the store
  }
}

function updateMinConfidence(value: number): void {
  store.updateConfig({ min_confidence: value })
}

function updateMaxTrades(value: number | null): void {
  if (value !== null) {
    store.updateConfig({ max_trades_per_day: value })
  }
}

function updateMaxRisk(value: number | null): void {
  store.updateConfig({ max_risk_per_day: value })
}

function updateEnabledPatterns(patterns: PatternType[]): void {
  store.updateConfig({ enabled_patterns: patterns })
}

function updateSymbolWhitelist(symbols: string[]): void {
  store.updateConfig({ symbol_whitelist: symbols.length > 0 ? symbols : null })
}

function updateSymbolBlacklist(symbols: string[]): void {
  store.updateConfig({ symbol_blacklist: symbols.length > 0 ? symbols : null })
}

function formatDate(isoString: string): string {
  return new Date(isoString).toLocaleString()
}
</script>

<style scoped>
.auto-execution-settings {
  max-width: 1200px;
  margin: 0 auto;
  padding: 2rem;
}
</style>
