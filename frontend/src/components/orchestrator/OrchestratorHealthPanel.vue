<template>
  <Card class="orchestrator-health-panel">
    <template #title>
      <div class="flex items-center justify-between">
        <div class="flex items-center gap-2">
          <i class="pi pi-server text-blue-500"></i>
          <span>Orchestrator Health</span>
        </div>
        <div class="flex items-center gap-2 text-sm text-gray-400">
          <i
            class="pi pi-refresh cursor-pointer hover:text-blue-400"
            :class="{ 'animate-spin': loading }"
            title="Refresh now"
            @click="fetchHealth"
          ></i>
          <span v-if="lastUpdated" class="text-xs">{{ lastUpdated }}</span>
        </div>
      </div>
    </template>
    <template #content>
      <!-- Error state -->
      <div
        v-if="error"
        class="flex items-center gap-2 text-red-400 text-sm mb-3"
      >
        <i class="pi pi-exclamation-triangle"></i>
        <span>{{ error }}</span>
      </div>

      <!-- Overall status -->
      <div v-if="health" class="flex items-center gap-2 mb-4">
        <span
          class="inline-block w-3 h-3 rounded-full"
          :class="overallStatusColor"
        ></span>
        <span class="text-sm font-semibold" :class="overallStatusTextColor">
          {{ overallStatusLabel }}
        </span>
      </div>

      <!-- Components -->
      <div v-if="health?.components" class="mb-4">
        <div class="text-xs text-gray-400 uppercase tracking-wider mb-2">
          Components
        </div>
        <div class="grid grid-cols-3 gap-2">
          <div
            v-for="comp in componentList"
            :key="comp.name"
            class="flex items-center gap-2 px-3 py-2 rounded bg-gray-800"
          >
            <i
              :class="
                comp.healthy
                  ? 'pi pi-check-circle text-green-500'
                  : 'pi pi-times-circle text-red-500'
              "
            ></i>
            <span class="text-sm text-gray-200 capitalize">{{
              comp.label
            }}</span>
          </div>
        </div>
      </div>

      <!-- Metrics -->
      <div v-if="health?.metrics">
        <div class="text-xs text-gray-400 uppercase tracking-wider mb-2">
          Metrics
        </div>
        <div class="grid grid-cols-3 gap-2 text-center">
          <div class="px-3 py-2 rounded bg-gray-800">
            <div class="text-lg font-semibold text-gray-100">
              {{ health.metrics.analysis_count }}
            </div>
            <div class="text-xs text-gray-400">Analyses</div>
          </div>
          <div class="px-3 py-2 rounded bg-gray-800">
            <div class="text-lg font-semibold text-gray-100">
              {{ health.metrics.signal_count }}
            </div>
            <div class="text-xs text-gray-400">Signals</div>
          </div>
          <div class="px-3 py-2 rounded bg-gray-800">
            <div
              class="text-lg font-semibold"
              :class="
                health.metrics.error_count > 0
                  ? 'text-red-400'
                  : 'text-gray-100'
              "
            >
              {{ health.metrics.error_count }}
            </div>
            <div class="text-xs text-gray-400">Errors</div>
          </div>
        </div>
      </div>

      <!-- Loading skeleton when no data yet -->
      <div v-if="!health && !error && loading" class="space-y-3 animate-pulse">
        <div class="h-4 bg-gray-800 rounded w-1/3"></div>
        <div class="grid grid-cols-3 gap-2">
          <div class="h-10 bg-gray-800 rounded"></div>
          <div class="h-10 bg-gray-800 rounded"></div>
          <div class="h-10 bg-gray-800 rounded"></div>
        </div>
      </div>
    </template>
  </Card>
</template>

<script setup lang="ts">
/**
 * OrchestratorHealthPanel.vue - Orchestrator health status display
 *
 * Story 23.2: Wire orchestrator pipeline with real detectors
 *
 * Displays overall orchestrator health, component status (container,
 * cache, event bus), and operational metrics (analyses, signals, errors).
 * Auto-refreshes every 30 seconds.
 */
import { ref, computed, onMounted, onUnmounted } from 'vue'
import Card from 'primevue/card'
import { apiClient } from '@/services/api'

const REFRESH_INTERVAL_MS = 30_000

interface OrchestratorHealth {
  status: string
  components: {
    container: { status: string; healthy: boolean }
    cache: Record<string, unknown>
    event_bus: Record<string, unknown>
  }
  metrics: {
    analysis_count: number
    signal_count: number
    error_count: number
  }
}

const health = ref<OrchestratorHealth | null>(null)
const loading = ref(false)
const error = ref<string | null>(null)
let refreshTimer: ReturnType<typeof setInterval> | null = null

const componentList = computed(() => {
  const components = health.value?.components
  if (!components) return []
  return [
    {
      name: 'container',
      label: 'Container',
      healthy: components.container?.healthy ?? false,
    },
    {
      name: 'cache',
      label: 'Cache',
      healthy: components.cache != null,
    },
    {
      name: 'event_bus',
      label: 'Event Bus',
      healthy: components.event_bus != null,
    },
  ]
})

const overallStatusLabel = computed(() => {
  if (!health.value) return 'Unknown'
  const s = health.value.status
  return s.charAt(0).toUpperCase() + s.slice(1)
})

const overallStatusColor = computed(() => {
  if (!health.value) return 'bg-gray-500'
  switch (health.value.status) {
    case 'healthy':
      return 'bg-green-500'
    case 'degraded':
      return 'bg-yellow-500'
    default:
      return 'bg-red-500'
  }
})

const overallStatusTextColor = computed(() => {
  if (!health.value) return 'text-gray-400'
  switch (health.value.status) {
    case 'healthy':
      return 'text-green-400'
    case 'degraded':
      return 'text-yellow-400'
    default:
      return 'text-red-400'
  }
})

const lastUpdated = computed(() => {
  if (!health.value) return null
  return new Date().toLocaleTimeString()
})

async function fetchHealth(): Promise<void> {
  loading.value = true
  try {
    health.value = await apiClient.get<OrchestratorHealth>(
      '/orchestrator/health'
    )
    error.value = null
  } catch (err: unknown) {
    const message =
      err instanceof Error ? err.message : 'Failed to fetch orchestrator health'
    error.value = message
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  fetchHealth()
  refreshTimer = setInterval(fetchHealth, REFRESH_INTERVAL_MS)
})

onUnmounted(() => {
  if (refreshTimer) {
    clearInterval(refreshTimer)
    refreshTimer = null
  }
})
</script>

<style scoped>
.orchestrator-health-panel :deep(.p-card-body) {
  padding: 1rem;
}
</style>
