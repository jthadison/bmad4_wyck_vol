<script setup lang="ts">
/**
 * Correlation Override Audit Log (Task #2)
 *
 * Admin dashboard for viewing audit trail entries with focus on
 * correlation override compliance tracking.
 *
 * Features:
 * - PrimeVue DataTable with lazy loading and pagination (100 rows/page)
 * - Filters: date range, event type, entity type, actor
 * - Row expansion for metadata display
 * - CSV export for compliance reporting
 * - Suspicious pattern highlighting (repeated overrides by same actor)
 */

import { ref, onMounted, watch } from 'vue'
import { useToast } from 'primevue/usetoast'
import DataTable from 'primevue/datatable'
import type { DataTablePageEvent } from 'primevue/datatable'
import Column from 'primevue/column'
import Button from 'primevue/button'
import Calendar from 'primevue/calendar'
import Dropdown from 'primevue/dropdown'
import InputText from 'primevue/inputtext'
import Tag from 'primevue/tag'
import { useAuditTrailStore } from '@/stores/auditTrailStore'
import { EVENT_TYPE_OPTIONS, ENTITY_TYPE_OPTIONS } from '@/types/audit-trail'
import type { AuditTrailEntry } from '@/types/audit-trail'

const store = useAuditTrailStore()
const toast = useToast()

// Expanded row tracking
const expandedRowId = ref<string | null>(null)

// Debounced filter watcher
let filterDebounceTimer: number | null = null
watch(
  () => [
    store.eventTypeFilter,
    store.entityTypeFilter,
    store.actorFilter,
    store.startDate,
    store.endDate,
  ],
  () => {
    if (filterDebounceTimer) {
      clearTimeout(filterDebounceTimer)
    }
    filterDebounceTimer = window.setTimeout(() => {
      store.currentPage = 0
      store.fetchEntries()
    }, 500)
  },
  { deep: true }
)

function onPage(event: DataTablePageEvent) {
  store.setPage(event.page || 0)
}

function toggleRowExpansion(entryId: string) {
  expandedRowId.value = expandedRowId.value === entryId ? null : entryId
}

// Formatters
function formatTimestamp(timestamp: string): string {
  return new Date(timestamp).toLocaleString()
}

function formatRelativeTime(timestamp: string): string {
  const date = new Date(timestamp)
  const now = new Date()
  const diffMs = now.getTime() - date.getTime()
  const diffMins = Math.floor(diffMs / (1000 * 60))

  if (diffMins < 60) return `${diffMins}m ago`
  const diffHours = Math.floor(diffMins / 60)
  if (diffHours < 24) return `${diffHours}h ago`
  const diffDays = Math.floor(diffHours / 24)
  return `${diffDays}d ago`
}

function getEventTypeColor(
  eventType: string
): 'success' | 'danger' | 'warning' | 'info' | 'secondary' | undefined {
  switch (eventType) {
    case 'CORRELATION_OVERRIDE':
      return 'warning'
    case 'CONFIG_CHANGE':
      return 'info'
    case 'KILL_SWITCH':
      return 'danger'
    case 'RISK_OVERRIDE':
      return 'warning'
    default:
      return 'secondary'
  }
}

function formatMetadataKey(key: string): string {
  return key.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase())
}

function formatMetadataValue(value: unknown): string {
  if (value === null || value === undefined) return 'N/A'
  if (typeof value === 'object') return JSON.stringify(value, null, 2)
  return String(value)
}

// CSV Export
function exportToCSV() {
  try {
    const headers = [
      'Timestamp',
      'Event Type',
      'Entity Type',
      'Entity ID',
      'Actor',
      'Action',
      'Correlation ID',
    ]

    const csvRows = [
      headers.join(','),
      ...store.entries.map((entry) => {
        const row = [
          entry.created_at,
          entry.event_type,
          entry.entity_type,
          entry.entity_id,
          entry.actor,
          entry.action,
          entry.correlation_id || '',
        ]
        return row
          .map((cell) => `"${String(cell).replace(/"/g, '""')}"`)
          .join(',')
      }),
    ]

    const csvContent = csvRows.join('\n')
    const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' })
    const url = URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url

    const dateStr = new Date().toISOString().split('T')[0]
    link.download = `audit-trail-${dateStr}.csv`

    link.click()
    URL.revokeObjectURL(url)

    toast.add({
      severity: 'success',
      summary: 'Export Complete',
      detail: `Exported ${store.entries.length} entries to CSV`,
      life: 3000,
    })
  } catch (error) {
    console.error('Failed to export CSV:', error)
    toast.add({
      severity: 'error',
      summary: 'Export Failed',
      detail: 'Failed to export audit trail to CSV',
      life: 3000,
    })
  }
}

// Initialize
onMounted(() => {
  const endDate = new Date()
  const startDate = new Date()
  startDate.setDate(startDate.getDate() - 30)
  store.startDate = startDate
  store.endDate = endDate
  store.fetchEntries()
})
</script>

<template>
  <div class="audit-trail-log p-4">
    <!-- Header -->
    <div class="mb-4">
      <h2 class="text-2xl font-bold text-white mb-2">Audit Trail</h2>
      <p class="text-gray-400 text-sm">
        Compliance log for correlation overrides, configuration changes, and
        manual actions
      </p>
    </div>

    <!-- Filters -->
    <div class="bg-gray-800 rounded-lg p-4 mb-4">
      <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <!-- Date Range Start -->
        <div>
          <label class="block text-sm font-medium text-gray-300 mb-2"
            >Start Date</label
          >
          <Calendar
            v-model="store.startDate"
            :show-icon="true"
            :show-button-bar="true"
            date-format="yy-mm-dd"
            placeholder="Start date"
            class="w-full"
          />
        </div>

        <!-- Date Range End -->
        <div>
          <label class="block text-sm font-medium text-gray-300 mb-2"
            >End Date</label
          >
          <Calendar
            v-model="store.endDate"
            :show-icon="true"
            :show-button-bar="true"
            date-format="yy-mm-dd"
            placeholder="End date"
            class="w-full"
          />
        </div>

        <!-- Event Type -->
        <div>
          <label class="block text-sm font-medium text-gray-300 mb-2"
            >Event Type</label
          >
          <Dropdown
            v-model="store.eventTypeFilter"
            :options="EVENT_TYPE_OPTIONS"
            option-label="label"
            option-value="value"
            placeholder="All event types"
            :show-clear="true"
            class="w-full"
          />
        </div>

        <!-- Entity Type -->
        <div>
          <label class="block text-sm font-medium text-gray-300 mb-2"
            >Entity Type</label
          >
          <Dropdown
            v-model="store.entityTypeFilter"
            :options="ENTITY_TYPE_OPTIONS"
            option-label="label"
            option-value="value"
            placeholder="All entity types"
            :show-clear="true"
            class="w-full"
          />
        </div>
      </div>

      <!-- Actor Filter and Actions -->
      <div class="flex items-center gap-4 mt-4">
        <div class="flex-1">
          <InputText
            v-model="store.actorFilter"
            placeholder="Filter by actor..."
            class="w-full"
          />
        </div>
        <Button
          label="Clear Filters"
          severity="secondary"
          @click="store.clearFilters"
        />
        <Button
          label="Export CSV"
          icon="pi pi-download"
          severity="info"
          :disabled="!store.hasEntries"
          @click="exportToCSV"
        />
      </div>
    </div>

    <!-- Error State -->
    <div
      v-if="store.error"
      class="bg-red-900/50 border border-red-500 rounded-lg p-4 mb-4 text-red-200"
    >
      <i class="pi pi-exclamation-triangle mr-2"></i>
      {{ store.error }}
    </div>

    <!-- Data Table -->
    <DataTable
      :value="store.entries"
      :loading="store.isLoading"
      :lazy="true"
      :paginator="true"
      :rows="store.rowsPerPage"
      :total-records="store.totalCount"
      :first="store.currentPage * store.rowsPerPage"
      paginator-template="FirstPageLink PrevPageLink PageLinks NextPageLink LastPageLink CurrentPageReport"
      :current-page-report-template="`Showing ${
        store.currentPage * store.rowsPerPage + 1
      }-${Math.min(
        (store.currentPage + 1) * store.rowsPerPage,
        store.totalCount
      )} of ${store.totalCount} results`"
      class="bg-gray-800"
      scrollable
      scroll-height="600px"
      @page="onPage"
    >
      <!-- Timestamp -->
      <Column field="created_at" header="Timestamp">
        <template #body="{ data }: { data: AuditTrailEntry }">
          <span :title="formatTimestamp(data.created_at)">
            {{ formatRelativeTime(data.created_at) }}
          </span>
        </template>
      </Column>

      <!-- Event Type -->
      <Column field="event_type" header="Event Type">
        <template #body="{ data }: { data: AuditTrailEntry }">
          <Tag
            :value="data.event_type.replace(/_/g, ' ')"
            :severity="getEventTypeColor(data.event_type)"
          />
        </template>
      </Column>

      <!-- Actor -->
      <Column field="actor" header="Actor">
        <template #body="{ data }: { data: AuditTrailEntry }">
          <span
            class="font-medium"
            :class="{
              'text-yellow-400': store.isActorSuspicious(data.actor),
              'text-white': !store.isActorSuspicious(data.actor),
            }"
          >
            {{ data.actor }}
            <i
              v-if="store.isActorSuspicious(data.actor)"
              class="pi pi-exclamation-triangle ml-1 text-yellow-400"
              title="Frequent override pattern detected"
            ></i>
          </span>
        </template>
      </Column>

      <!-- Entity -->
      <Column header="Entity">
        <template #body="{ data }: { data: AuditTrailEntry }">
          <span class="text-gray-300">{{ data.entity_type }}</span>
          <span class="text-gray-500 ml-1 text-xs">{{ data.entity_id }}</span>
        </template>
      </Column>

      <!-- Action -->
      <Column field="action" header="Action">
        <template #body="{ data }: { data: AuditTrailEntry }">
          <span
            :title="data.action"
            class="truncate max-w-xs block text-gray-200"
          >
            {{
              data.action.length > 80
                ? data.action.substring(0, 80) + '...'
                : data.action
            }}
          </span>
        </template>
      </Column>

      <!-- Expand -->
      <Column style="width: 3rem">
        <template #body="{ data }: { data: AuditTrailEntry }">
          <Button
            :icon="
              expandedRowId === data.id
                ? 'pi pi-chevron-up'
                : 'pi pi-chevron-down'
            "
            text
            rounded
            aria-label="Expand row"
            @click="toggleRowExpansion(data.id)"
          />
        </template>
      </Column>

      <!-- Row Expansion -->
      <template #expansion="{ data }: { data: AuditTrailEntry }">
        <div v-if="expandedRowId === data.id" class="p-4 bg-gray-900">
          <div class="grid grid-cols-1 md:grid-cols-2 gap-6">
            <!-- Entry Details -->
            <div>
              <h3 class="text-sm font-bold text-gray-300 uppercase mb-3">
                Details
              </h3>
              <div class="space-y-2 text-sm">
                <div class="flex gap-2">
                  <span class="text-gray-500 w-32">Full Timestamp:</span>
                  <span class="text-white">{{
                    formatTimestamp(data.created_at)
                  }}</span>
                </div>
                <div class="flex gap-2">
                  <span class="text-gray-500 w-32">Correlation ID:</span>
                  <span class="text-white font-mono text-xs">
                    {{ data.correlation_id || 'N/A' }}
                  </span>
                </div>
                <div class="flex gap-2">
                  <span class="text-gray-500 w-32">Entity ID:</span>
                  <span class="text-white font-mono text-xs">{{
                    data.entity_id
                  }}</span>
                </div>
                <div class="flex gap-2">
                  <span class="text-gray-500 w-32">Full Action:</span>
                  <span class="text-white">{{ data.action }}</span>
                </div>
              </div>
            </div>

            <!-- Metadata -->
            <div>
              <h3 class="text-sm font-bold text-gray-300 uppercase mb-3">
                Metadata
              </h3>
              <div
                v-if="Object.keys(data.metadata).length > 0"
                class="space-y-2 text-sm"
              >
                <div
                  v-for="(value, key) in data.metadata"
                  :key="String(key)"
                  class="flex gap-2"
                >
                  <span class="text-gray-500 w-40"
                    >{{ formatMetadataKey(String(key)) }}:</span
                  >
                  <span
                    class="text-white font-mono text-xs whitespace-pre-wrap"
                  >
                    {{ formatMetadataValue(value) }}
                  </span>
                </div>
              </div>
              <p v-else class="text-gray-500 text-sm">No additional metadata</p>
            </div>
          </div>
        </div>
      </template>

      <!-- Empty State -->
      <template #empty>
        <div class="text-center py-8 text-gray-400">
          No audit trail entries found
        </div>
      </template>

      <!-- Loading State -->
      <template #loading>
        <div class="text-center py-8 text-gray-400">Loading audit trail...</div>
      </template>
    </DataTable>
  </div>
</template>

<style scoped>
.audit-trail-log {
  @apply bg-gray-900 rounded-lg;
}

:deep(.p-datatable) {
  @apply bg-gray-800;
}

:deep(.p-datatable .p-datatable-header) {
  @apply bg-gray-800 text-white;
}

:deep(.p-datatable .p-datatable-tbody > tr) {
  @apply bg-gray-800 text-white;
}

:deep(.p-datatable .p-datatable-tbody > tr:hover) {
  @apply bg-gray-700;
}

:deep(.p-paginator) {
  @apply bg-gray-800 text-white;
}

:deep(.p-calendar) {
  @apply bg-gray-700 text-white;
}

:deep(.p-dropdown) {
  @apply bg-gray-700 text-white;
}

:deep(.p-inputtext) {
  @apply bg-gray-700 text-white border-gray-600;
}
</style>
