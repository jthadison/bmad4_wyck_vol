<template>
  <Dialog
    :visible="visible"
    modal
    :closable="true"
    :draggable="false"
    class="kill-switch-modal"
    style="width: 500px; max-width: 90vw"
    @update:visible="$emit('update:visible', $event)"
  >
    <template #header>
      <div class="flex items-center gap-3">
        <i class="pi pi-stop-circle text-red-600 text-2xl"></i>
        <h3 class="text-xl font-bold text-gray-900 dark:text-gray-100">
          Emergency Stop
        </h3>
      </div>
    </template>

    <div class="kill-switch-content space-y-4">
      <!-- Warning Banner -->
      <div
        class="bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg p-4"
      >
        <p class="text-sm text-red-800 dark:text-red-200 font-medium">
          Are you sure you want to stop all automatic trading?
        </p>
      </div>

      <!-- Info Items -->
      <ul class="space-y-3 text-sm text-gray-700 dark:text-gray-300">
        <li class="flex items-start gap-2">
          <i class="pi pi-circle-fill text-xs mt-1 text-gray-400"></i>
          <span>All auto-execution will be immediately halted</span>
        </li>
        <li class="flex items-start gap-2">
          <i class="pi pi-circle-fill text-xs mt-1 text-gray-400"></i>
          <span>Pending signals will remain in queue</span>
        </li>
        <li class="flex items-start gap-2">
          <i class="pi pi-circle-fill text-xs mt-1 text-gray-400"></i>
          <span>Manual approval will still work</span>
        </li>
        <li class="flex items-start gap-2">
          <i class="pi pi-circle-fill text-xs mt-1 text-gray-400"></i>
          <span>You can re-enable in settings</span>
        </li>
      </ul>

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
          :disabled="loading"
          @click="handleCancel"
        />
        <Button
          label="Stop All Trading"
          severity="danger"
          :loading="loading"
          icon="pi pi-stop-circle"
          @click="handleConfirm"
        />
      </div>
    </template>
  </Dialog>
</template>

<script setup lang="ts">
/**
 * KillSwitchModal.vue - Emergency Stop Confirmation Modal
 *
 * Story 19.22: Emergency Kill Switch
 *
 * Displays a confirmation dialog when user clicks the kill switch button.
 * Shows warning message and consequences of activating the kill switch.
 */
import Dialog from 'primevue/dialog'
import Button from 'primevue/button'
import Message from 'primevue/message'

interface Props {
  visible: boolean
  loading?: boolean
  error?: string | null
}

interface Emits {
  (e: 'update:visible', value: boolean): void
  (e: 'confirm'): void
  (e: 'cancel'): void
}

withDefaults(defineProps<Props>(), {
  loading: false,
  error: null,
})

const emit = defineEmits<Emits>()

function handleConfirm(): void {
  emit('confirm')
}

function handleCancel(): void {
  emit('cancel')
  emit('update:visible', false)
}
</script>

<style scoped>
.kill-switch-modal :deep(.p-dialog-header) {
  background-color: #fef2f2;
  border-bottom: 2px solid #ef4444;
}

.dark .kill-switch-modal :deep(.p-dialog-header) {
  background-color: #7f1d1d;
  border-bottom-color: #dc2626;
}

.kill-switch-content {
  padding: 1rem 0;
}
</style>
