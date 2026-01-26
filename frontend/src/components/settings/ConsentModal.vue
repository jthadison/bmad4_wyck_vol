<template>
  <Dialog
    :visible="visible"
    modal
    :closable="false"
    :draggable="false"
    class="consent-modal"
    style="width: 600px; max-width: 90vw"
  >
    <template #header>
      <div class="flex items-center gap-3">
        <i class="pi pi-exclamation-triangle text-yellow-600 text-2xl"></i>
        <h3 class="text-xl font-bold text-gray-900 dark:text-gray-100">
          Enable Automatic Execution
        </h3>
      </div>
    </template>

    <div class="consent-content space-y-4">
      <!-- Warning Banner -->
      <div
        class="bg-yellow-50 dark:bg-yellow-900/20 border border-yellow-200 dark:border-yellow-800 rounded-lg p-4"
      >
        <p class="text-sm text-yellow-800 dark:text-yellow-200 font-medium">
          By enabling auto-execution, you acknowledge that:
        </p>
      </div>

      <!-- Consent Items -->
      <ul class="space-y-3 text-sm text-gray-700 dark:text-gray-300">
        <li class="flex items-start gap-2">
          <i class="pi pi-circle-fill text-xs mt-1 text-gray-400"></i>
          <span
            >Trades will execute automatically without manual confirmation</span
          >
        </li>
        <li class="flex items-start gap-2">
          <i class="pi pi-circle-fill text-xs mt-1 text-gray-400"></i>
          <span>You are responsible for monitoring your account</span>
        </li>
        <li class="flex items-start gap-2">
          <i class="pi pi-circle-fill text-xs mt-1 text-gray-400"></i>
          <span>Past performance does not guarantee future results</span>
        </li>
        <li class="flex items-start gap-2">
          <i class="pi pi-circle-fill text-xs mt-1 text-gray-400"></i>
          <span>You can disable auto-execution at any time</span>
        </li>
        <li class="flex items-start gap-2">
          <i class="pi pi-circle-fill text-xs mt-1 text-gray-400"></i>
          <span
            >The kill switch will immediately halt all automatic trading</span
          >
        </li>
      </ul>

      <!-- Acknowledgment Checkbox -->
      <div
        class="flex items-start gap-3 mt-6 p-4 bg-gray-50 dark:bg-gray-800 rounded-lg"
      >
        <Checkbox
          v-model="acknowledged"
          :binary="true"
          input-id="consent-checkbox"
        />
        <label
          for="consent-checkbox"
          class="text-sm font-medium text-gray-900 dark:text-gray-100 cursor-pointer"
        >
          I understand and accept the risks of automatic trading
        </label>
      </div>

      <!-- Error Message -->
      <Message v-if="error" severity="error" :closable="false">
        {{ error }}
      </Message>
    </div>

    <template #footer>
      <div class="flex justify-end gap-3">
        <Button
          label="Cancel"
          severity="secondary"
          @click="handleCancel"
          :disabled="loading"
        />
        <Button
          label="Enable Auto-Execution"
          severity="warning"
          @click="handleEnable"
          :disabled="!canEnable"
          :loading="loading"
          icon="pi pi-check"
        />
      </div>
    </template>
  </Dialog>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import Dialog from 'primevue/dialog'
import Button from 'primevue/button'
import Checkbox from 'primevue/checkbox'
import Message from 'primevue/message'

interface Props {
  visible: boolean
  loading?: boolean
  error?: string | null
}

interface Emits {
  (e: 'update:visible', value: boolean): void
  (e: 'enable'): void
  (e: 'cancel'): void
}

const props = withDefaults(defineProps<Props>(), {
  loading: false,
  error: null,
})

const emit = defineEmits<Emits>()

const acknowledged = ref(false)

const canEnable = computed(() => {
  return acknowledged.value && !props.loading
})

function handleEnable(): void {
  if (canEnable.value) {
    emit('enable')
  }
}

function handleCancel(): void {
  acknowledged.value = false
  emit('cancel')
  emit('update:visible', false)
}

// Reset form when modal is closed
function resetForm(): void {
  acknowledged.value = false
}

defineExpose({
  resetForm,
})
</script>

<style scoped>
.consent-modal :deep(.p-dialog-header) {
  background-color: #fef3c7;
  border-bottom: 2px solid #fbbf24;
}

.dark .consent-modal :deep(.p-dialog-header) {
  background-color: #78350f;
  border-bottom-color: #f59e0b;
}

.consent-content {
  padding: 1rem 0;
}
</style>
