<template>
  <transition name="slide-down">
    <div
      v-if="hasWarnings && !isDismissed"
      class="proximity-warnings-banner"
      role="alert"
      aria-live="assertive"
      aria-atomic="true"
    >
      <Message
        severity="warn"
        :closable="true"
        :pt="{
          root: { class: 'bg-yellow-900/30 border-yellow-600/50' },
          icon: { class: 'text-yellow-400' },
          text: { class: 'text-yellow-200' },
          closeButton: { class: 'text-yellow-400 hover:text-yellow-300' },
        }"
        @close="handleDismiss"
      >
        <template #messageicon>
          <i class="pi pi-exclamation-triangle text-xl"></i>
        </template>
        <div class="proximity-warnings-content">
          <!-- Header -->
          <div class="font-semibold text-yellow-100 mb-2">
            <i class="pi pi-shield text-yellow-400 mr-2"></i>
            Risk Capacity Warning ({{ warnings.length }})
          </div>

          <!-- Warning List -->
          <ul class="space-y-1.5 text-sm">
            <li
              v-for="(warning, index) in warnings"
              :key="index"
              class="flex items-start gap-2"
            >
              <i class="pi pi-angle-right text-yellow-400 mt-0.5 text-xs"></i>
              <span class="text-yellow-100">{{ warning }}</span>
            </li>
          </ul>

          <!-- Action Hint -->
          <div class="mt-3 text-xs text-yellow-300/80 flex items-center gap-2">
            <i class="pi pi-info-circle"></i>
            <span>
              Consider closing positions or reducing allocation to maintain risk
              discipline
            </span>
          </div>
        </div>
      </Message>
    </div>
  </transition>
</template>

<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import Message from 'primevue/message'

/**
 * ProximityWarningsBanner Component (Story 10.6 - AC 6)
 *
 * Displays proximity warnings when risk limits approach 80% capacity.
 *
 * Warning Types:
 * - Portfolio heat > 8.0% (80% of 10% limit)
 * - Campaign risk > 4.0% (80% of 5% limit)
 * - Sector risk > 4.8% (80% of 6% limit)
 *
 * Features:
 * - Dismissible warning banner
 * - Automatically reappears when new warnings detected
 * - Slide-down transition animation
 * - Accessible ARIA labels
 * - PrimeVue Message component with custom theming
 */

// Props
interface Props {
  /** Array of proximity warning messages */
  warnings: string[]
}

const props = defineProps<Props>()

// ============================================================================
// State
// ============================================================================

const isDismissed = ref(false)

// ============================================================================
// Computed
// ============================================================================

/**
 * Check if there are any warnings to display.
 */
const hasWarnings = computed(() => {
  return props.warnings.length > 0
})

// ============================================================================
// Methods
// ============================================================================

/**
 * Handle user dismissing the warning banner.
 * Banner will reappear if warnings change (new warning added).
 */
function handleDismiss() {
  isDismissed.value = true
}

// ============================================================================
// Watchers
// ============================================================================

/**
 * Watch for changes in warnings array.
 * If warnings change (new warning added or removed), un-dismiss the banner.
 */
watch(
  () => props.warnings.length,
  (newCount, oldCount) => {
    // Only un-dismiss if warnings count increased (new warning added)
    if (newCount > oldCount && isDismissed.value) {
      isDismissed.value = false
    }
  }
)
</script>

<style scoped>
/**
 * ProximityWarningsBanner Component Styles
 *
 * Custom slide-down transition for warning appearance.
 */

.proximity-warnings-banner {
  margin-bottom: 1.5rem;
}

.proximity-warnings-content {
  width: 100%;
}

/* Slide-down transition */
.slide-down-enter-active,
.slide-down-leave-active {
  transition: all 0.3s ease-out;
}

.slide-down-enter-from {
  transform: translateY(-100%);
  opacity: 0;
}

.slide-down-leave-to {
  transform: translateY(-100%);
  opacity: 0;
}
</style>
