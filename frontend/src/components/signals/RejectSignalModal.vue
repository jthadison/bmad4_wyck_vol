<script setup lang="ts">
/**
 * Reject Signal Modal Component (Story 19.10)
 *
 * Modal dialog for capturing rejection reason when a trader
 * rejects a pending signal from the approval queue.
 *
 * Features:
 * - Predefined rejection reasons
 * - Custom reason text input
 * - Optional notes field
 * - Confirmation button with validation
 */
import { ref, computed, watch } from 'vue'
import Dialog from 'primevue/dialog'
import Button from 'primevue/button'
import Dropdown from 'primevue/dropdown'
import Textarea from 'primevue/textarea'
import type { PendingSignal, RejectSignalRequest } from '@/types'

interface Props {
  visible: boolean
  signal: PendingSignal | null
}

const props = defineProps<Props>()

const emit = defineEmits<{
  'update:visible': [value: boolean]
  confirm: [request: RejectSignalRequest]
  cancel: []
}>()

// Predefined rejection reasons
const rejectionReasons = [
  { label: 'Entry too far from pattern', value: 'entry_too_far' },
  { label: 'Volume not convincing', value: 'volume_not_convincing' },
  { label: 'Market conditions unfavorable', value: 'market_conditions' },
  { label: 'Already at position limit', value: 'position_limit' },
  { label: 'Risk too high', value: 'risk_too_high' },
  { label: 'Pattern quality concerns', value: 'pattern_quality' },
  { label: 'Timeframe mismatch', value: 'timeframe_mismatch' },
  { label: 'Other (specify below)', value: 'other' },
]

// Form state
const selectedReason = ref<string | null>(null)
const customReason = ref('')
const additionalNotes = ref('')
const isSubmitting = ref(false)

// Computed
const showCustomReasonInput = computed(() => selectedReason.value === 'other')

const isFormValid = computed(() => {
  if (!selectedReason.value) return false
  if (selectedReason.value === 'other' && !customReason.value.trim())
    return false
  return true
})

const finalReason = computed(() => {
  if (selectedReason.value === 'other') {
    return customReason.value.trim()
  }
  const found = rejectionReasons.find((r) => r.value === selectedReason.value)
  return found?.label || ''
})

// Methods
const handleClose = () => {
  emit('update:visible', false)
  emit('cancel')
  resetForm()
}

const handleConfirm = async () => {
  if (!isFormValid.value || isSubmitting.value) return

  isSubmitting.value = true

  const request: RejectSignalRequest = {
    reason: finalReason.value,
    notes: additionalNotes.value.trim() || undefined,
  }

  emit('confirm', request)
  isSubmitting.value = false
  emit('update:visible', false)
  resetForm()
}

const resetForm = () => {
  selectedReason.value = null
  customReason.value = ''
  additionalNotes.value = ''
  isSubmitting.value = false
}

// Reset form when modal opens
watch(
  () => props.visible,
  (newVisible) => {
    if (newVisible) {
      resetForm()
    }
  }
)
</script>

<template>
  <Dialog
    :visible="visible"
    modal
    header="Reject Signal"
    :style="{ width: '450px' }"
    :closable="!isSubmitting"
    :draggable="false"
    data-testid="reject-signal-modal"
    @update:visible="emit('update:visible', $event)"
  >
    <template #header>
      <div class="flex items-center gap-2">
        <i class="pi pi-times-circle text-red-500 text-xl"></i>
        <span class="text-lg font-semibold">Reject Signal</span>
      </div>
    </template>

    <div v-if="signal" class="reject-form">
      <!-- Signal Info Summary -->
      <div
        class="signal-summary p-3 mb-4 rounded-lg bg-gray-100 dark:bg-gray-800"
        data-testid="signal-summary"
      >
        <div class="flex justify-between items-center">
          <div>
            <span class="font-bold text-gray-900 dark:text-white">
              {{ signal.signal.symbol }}
            </span>
            <span class="ml-2 text-sm text-gray-600 dark:text-gray-400">
              {{ signal.signal.pattern_type }}
            </span>
          </div>
          <div class="text-sm text-gray-600 dark:text-gray-400">
            {{ signal.signal.confidence_score }}% confidence
          </div>
        </div>
      </div>

      <!-- Rejection Reason Dropdown -->
      <div class="field mb-4">
        <label
          for="rejection-reason"
          class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2"
        >
          Rejection Reason <span class="text-red-500">*</span>
        </label>
        <Dropdown
          id="rejection-reason"
          v-model="selectedReason"
          :options="rejectionReasons"
          option-label="label"
          option-value="value"
          placeholder="Select a reason..."
          class="w-full"
          data-testid="reason-dropdown"
        />
      </div>

      <!-- Custom Reason Input (shown when "Other" selected) -->
      <div v-if="showCustomReasonInput" class="field mb-4">
        <label
          for="custom-reason"
          class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2"
        >
          Specify Reason <span class="text-red-500">*</span>
        </label>
        <Textarea
          id="custom-reason"
          v-model="customReason"
          rows="2"
          placeholder="Enter your specific reason..."
          class="w-full"
          auto-resize
          data-testid="custom-reason-input"
        />
      </div>

      <!-- Additional Notes (optional) -->
      <div class="field mb-4">
        <label
          for="additional-notes"
          class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2"
        >
          Additional Notes (optional)
        </label>
        <Textarea
          id="additional-notes"
          v-model="additionalNotes"
          rows="3"
          placeholder="Any additional context for this rejection..."
          class="w-full"
          auto-resize
          data-testid="notes-input"
        />
      </div>

      <!-- Info Message -->
      <div
        class="info-message flex items-start gap-2 p-3 rounded-lg bg-blue-50 dark:bg-blue-900/30 text-sm"
      >
        <i class="pi pi-info-circle text-blue-500 mt-0.5"></i>
        <span class="text-gray-700 dark:text-gray-300">
          This rejection will be logged for future analysis and pattern
          improvement. The signal will be removed from the queue.
        </span>
      </div>
    </div>

    <template #footer>
      <div class="flex justify-end gap-2">
        <Button
          label="Cancel"
          severity="secondary"
          outlined
          :disabled="isSubmitting"
          data-testid="cancel-button"
          @click="handleClose"
        />
        <Button
          label="Confirm Reject"
          severity="danger"
          :disabled="!isFormValid || isSubmitting"
          :loading="isSubmitting"
          data-testid="confirm-button"
          @click="handleConfirm"
        />
      </div>
    </template>
  </Dialog>
</template>

<style scoped>
.reject-form {
  min-height: 200px;
}

.field {
  margin-bottom: 1rem;
}

:deep(.p-dropdown) {
  width: 100%;
}

:deep(.p-inputtextarea) {
  width: 100%;
}
</style>
