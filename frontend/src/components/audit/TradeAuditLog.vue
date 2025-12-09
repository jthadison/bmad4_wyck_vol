<script setup lang="ts">
/**
 * Trade Audit Log Table (Story 10.8)
 *
 * Full-featured audit log with filtering, sorting, pagination, row expansion,
 * and CSV/JSON export functionality.
 *
 * Features:
 * - PrimeVue DataTable with lazy loading and virtual scrolling
 * - Filtering: date range, pattern types, symbols, statuses, confidence
 * - Full-text search across all fields
 * - Sorting by column headers
 * - Row expansion with validation chain and Wyckoff educational layer
 * - CSV/JSON export with filter application
 * - Pagination (50 rows/page)
 *
 * Author: Story 10.8
 */

import { ref, reactive, computed, onMounted, watch } from 'vue'
import { useToast } from 'primevue/usetoast'
import DataTable from 'primevue/datatable'
import type { DataTableSortEvent, DataTablePageEvent } from 'primevue/datatable'
import Column from 'primevue/column'
import Button from 'primevue/button'
import SplitButton from 'primevue/splitbutton'
import Calendar from 'primevue/calendar'
import MultiSelect from 'primevue/multiselect'
import InputText from 'primevue/inputtext'
import Tag from 'primevue/tag'
import Chip from 'primevue/chip'
import Big from 'big.js'
import {
  getAuditLog,
  type AuditLogEntry,
  type AuditLogQueryParams,
} from '@/services/api'

// Composables
const toast = useToast()

// State
const auditLogEntries = ref<AuditLogEntry[]>([])
const totalCount = ref(0)
const isLoading = ref(false)
const expandedRowId = ref<string | null>(null)

// Filter state
const filters = reactive({
  dateRange: null as Date[] | null,
  selectedPatterns: [] as string[],
  selectedStatuses: [] as string[],
  selectedSymbols: [] as string[],
  searchText: '',
})

// Pagination state
const currentPage = ref(0)
const rowsPerPage = ref(50)

// Sorting state
const sortField = ref('timestamp')
const sortOrder = ref<1 | -1>(-1) // -1 = desc, 1 = asc

// Options for filters
const patternOptions = [
  { label: 'Spring', value: 'SPRING' },
  { label: 'UTAD', value: 'UTAD' },
  { label: 'SOS', value: 'SOS' },
  { label: 'LPS', value: 'LPS' },
  { label: 'SC', value: 'SC' },
  { label: 'AR', value: 'AR' },
  { label: 'ST', value: 'ST' },
]

const statusOptions = [
  { label: 'Pending', value: 'PENDING' },
  { label: 'Approved', value: 'APPROVED' },
  { label: 'Rejected', value: 'REJECTED' },
  { label: 'Filled', value: 'FILLED' },
  { label: 'Stopped', value: 'STOPPED' },
  { label: 'Target Hit', value: 'TARGET_HIT' },
  { label: 'Expired', value: 'EXPIRED' },
]

// Mock symbol options (in production, fetch from API)
const symbolOptions = ref([
  'AAPL',
  'TSLA',
  'MSFT',
  'NVDA',
  'GOOGL',
  'META',
  'AMZN',
  'NFLX',
  'AMD',
])

// Wyckoff rule explanations (for educational tooltips)
const wyckoffRuleExplanations: Record<string, string> = {
  'Law #1: Supply & Demand':
    'Volume confirms absence/presence of selling/buying pressure. Low volume indicates absorption by strong hands.',
  'Law #2: Cause & Effect':
    'Campaign risk allocation and position sizing based on accumulation. Larger cause creates larger effect.',
  'Law #3: Effort vs Result':
    'Narrow spread on low volume indicates absorption. Effort (volume) should match result (price movement).',
  'Phase Progression':
    'Pattern requires specific Wyckoff phase (e.g., Spring requires Phase C Testing phase). Phases must progress logically.',
  'Test Principle':
    'Support/resistance must be tested with 3-15 bar confirmation. Tests validate strength of accumulation/distribution.',
  'Wyckoff Schematics':
    'Price must follow Wyckoff accumulation/distribution structure. Pattern structure must match established schematics.',
}

// Note: Using PrimeVue's DataTableSortEvent and DataTablePageEvent types

// Computed
const activeFilterCount = computed(() => {
  let count = 0
  if (filters.dateRange && filters.dateRange.length === 2) count++
  if (filters.selectedPatterns.length > 0) count++
  if (filters.selectedStatuses.length > 0) count++
  if (filters.selectedSymbols.length > 0) count++
  if (filters.searchText) count++
  return count
})

// Methods
async function fetchAuditLog() {
  isLoading.value = true

  try {
    // Build query parameters
    const params: AuditLogQueryParams = {
      order_by: sortField.value as AuditLogQueryParams['order_by'],
      order_direction: sortOrder.value === -1 ? 'desc' : 'asc',
      limit: rowsPerPage.value,
      offset: currentPage.value * rowsPerPage.value,
    }

    // Date range
    if (filters.dateRange && filters.dateRange.length === 2) {
      params.start_date = filters.dateRange[0].toISOString()
      params.end_date = filters.dateRange[1].toISOString()
    }

    // Multi-select filters
    if (filters.selectedSymbols.length > 0) {
      params.symbols = filters.selectedSymbols
    }
    if (filters.selectedPatterns.length > 0) {
      params.pattern_types = filters.selectedPatterns
    }
    if (filters.selectedStatuses.length > 0) {
      params.statuses = filters.selectedStatuses
    }

    // Search
    if (filters.searchText) {
      params.search_text = filters.searchText
    }

    // Fetch from API using typed client
    const response = await getAuditLog(params)

    auditLogEntries.value = response.data
    totalCount.value = response.total_count
  } catch (error) {
    console.error('Failed to fetch audit log:', error)
    toast.add({
      severity: 'error',
      summary: 'Error',
      detail: 'Failed to load audit log',
      life: 3000,
    })
  } finally {
    isLoading.value = false
  }
}

function onSort(event: DataTableSortEvent) {
  sortField.value = (event.sortField as string) || 'timestamp'
  sortOrder.value = (event.sortOrder as 1 | -1) || -1
  fetchAuditLog()
}

function onPage(event: DataTablePageEvent) {
  currentPage.value = event.page || 0
  fetchAuditLog()
}

function clearFilters() {
  filters.dateRange = null
  filters.selectedPatterns = []
  filters.selectedStatuses = []
  filters.selectedSymbols = []
  filters.searchText = ''
  currentPage.value = 0
  fetchAuditLog()
}

// Export functions
function exportToCSV() {
  try {
    const headers = [
      'Timestamp',
      'Symbol',
      'Pattern',
      'Phase',
      'Confidence',
      'Status',
      'Rejection Reason',
    ]

    const csvRows = [
      headers.join(','),
      ...auditLogEntries.value.map((entry) => {
        const row = [
          entry.timestamp,
          entry.symbol,
          entry.pattern_type,
          entry.phase,
          entry.confidence_score.toString(),
          entry.status,
          entry.rejection_reason || '',
        ]
        return row.map((cell) => `"${cell}"`).join(',')
      }),
    ]

    const csvContent = csvRows.join('\n')
    const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' })
    const url = URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url

    const startDate =
      filters.dateRange?.[0]?.toISOString().split('T')[0] || 'all'
    const endDate = filters.dateRange?.[1]?.toISOString().split('T')[0] || 'all'
    link.download = `audit-log-${startDate}-${endDate}.csv`

    link.click()
    URL.revokeObjectURL(url)

    toast.add({
      severity: 'success',
      summary: 'Success',
      detail: `Exported ${auditLogEntries.value.length} entries to CSV`,
      life: 3000,
    })
  } catch (error) {
    console.error('Failed to export CSV:', error)
    toast.add({
      severity: 'error',
      summary: 'Error',
      detail: 'Failed to export CSV',
      life: 3000,
    })
  }
}

function exportToJSON() {
  try {
    const jsonContent = JSON.stringify(auditLogEntries.value, null, 2)
    const blob = new Blob([jsonContent], {
      type: 'application/json;charset=utf-8;',
    })
    const url = URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url

    const startDate =
      filters.dateRange?.[0]?.toISOString().split('T')[0] || 'all'
    const endDate = filters.dateRange?.[1]?.toISOString().split('T')[0] || 'all'
    link.download = `audit-log-${startDate}-${endDate}.json`

    link.click()
    URL.revokeObjectURL(url)

    toast.add({
      severity: 'success',
      summary: 'Success',
      detail: `Exported ${auditLogEntries.value.length} entries to JSON`,
      life: 3000,
    })
  } catch (error) {
    console.error('Failed to export JSON:', error)
    toast.add({
      severity: 'error',
      summary: 'Error',
      detail: 'Failed to export JSON',
      life: 3000,
    })
  }
}

// Formatters
function formatTimestamp(timestamp: string): string {
  const date = new Date(timestamp)
  const now = new Date()
  const diffMs = now.getTime() - date.getTime()
  const diffHours = Math.floor(diffMs / (1000 * 60 * 60))

  if (diffHours < 24) {
    return `${diffHours} hours ago`
  } else {
    const diffDays = Math.floor(diffHours / 24)
    return `${diffDays} days ago`
  }
}

function formatPrice(price: string | null): string {
  if (!price) return 'N/A'
  return new Big(price).toFixed(2)
}

function getStatusColor(
  status: string
): 'success' | 'danger' | 'warning' | 'secondary' | undefined {
  switch (status) {
    case 'FILLED':
    case 'TARGET_HIT':
      return 'success'
    case 'REJECTED':
      return 'danger'
    case 'PENDING':
    case 'APPROVED':
      return 'warning'
    case 'STOPPED':
    case 'EXPIRED':
      return 'secondary'
    default:
      return undefined
  }
}

function getConfidenceColor(confidence: number): string {
  if (confidence >= 80) return 'text-green-500'
  if (confidence >= 70) return 'text-yellow-500'
  return 'text-gray-500'
}

function toggleRowExpansion(entryId: string) {
  expandedRowId.value = expandedRowId.value === entryId ? null : entryId
}

// Watch for filter changes (debounced)
let filterDebounceTimer: number | null = null
watch(
  () => [
    filters.dateRange,
    filters.selectedPatterns,
    filters.selectedStatuses,
    filters.selectedSymbols,
    filters.searchText,
  ],
  () => {
    if (filterDebounceTimer) {
      clearTimeout(filterDebounceTimer)
    }
    filterDebounceTimer = window.setTimeout(() => {
      currentPage.value = 0
      fetchAuditLog()
    }, 500) // 500ms debounce
  },
  { deep: true }
)

// Initialize
onMounted(() => {
  // Set default date range to last 30 days
  const endDate = new Date()
  const startDate = new Date()
  startDate.setDate(startDate.getDate() - 30)
  filters.dateRange = [startDate, endDate]

  fetchAuditLog()
})
</script>

<template>
  <div class="trade-audit-log p-4">
    <div class="mb-4">
      <h2 class="text-2xl font-bold text-white mb-2">Trade Audit Log</h2>
      <p class="text-gray-400 text-sm">
        Complete history of pattern detections (executed and rejected)
      </p>
    </div>

    <!-- Filters -->
    <div class="bg-gray-800 rounded-lg p-4 mb-4">
      <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <!-- Date Range -->
        <div>
          <label class="block text-sm font-medium text-gray-300 mb-2"
            >Date Range</label
          >
          <Calendar
            v-model="filters.dateRange"
            selection-mode="range"
            :show-icon="true"
            :show-button-bar="true"
            date-format="yy-mm-dd"
            placeholder="Select date range"
            class="w-full"
          />
        </div>

        <!-- Pattern Type -->
        <div>
          <label class="block text-sm font-medium text-gray-300 mb-2"
            >Pattern Type</label
          >
          <MultiSelect
            v-model="filters.selectedPatterns"
            :options="patternOptions"
            option-label="label"
            option-value="value"
            placeholder="All patterns"
            class="w-full"
          />
        </div>

        <!-- Status -->
        <div>
          <label class="block text-sm font-medium text-gray-300 mb-2"
            >Status</label
          >
          <MultiSelect
            v-model="filters.selectedStatuses"
            :options="statusOptions"
            option-label="label"
            option-value="value"
            placeholder="All statuses"
            class="w-full"
          />
        </div>

        <!-- Symbol -->
        <div>
          <label class="block text-sm font-medium text-gray-300 mb-2"
            >Symbol</label
          >
          <MultiSelect
            v-model="filters.selectedSymbols"
            :options="symbolOptions"
            placeholder="All symbols"
            class="w-full"
          />
        </div>
      </div>

      <!-- Search and Clear -->
      <div class="flex items-center gap-4 mt-4">
        <div class="flex-1">
          <InputText
            v-model="filters.searchText"
            placeholder="Search across all fields..."
            class="w-full"
          />
        </div>
        <Button
          label="Clear Filters"
          severity="secondary"
          :disabled="activeFilterCount === 0"
          @click="clearFilters"
        />
        <SplitButton
          label="Export CSV"
          :model="[{ label: 'Export JSON', command: exportToJSON }]"
          @click="exportToCSV"
        />
      </div>

      <!-- Active Filters -->
      <div v-if="activeFilterCount > 0" class="flex flex-wrap gap-2 mt-4">
        <Chip
          v-if="filters.dateRange"
          label="Date Range"
          removable
          @remove="filters.dateRange = null"
        />
        <Chip
          v-for="pattern in filters.selectedPatterns"
          :key="pattern"
          :label="`Pattern: ${pattern}`"
          removable
          @remove="
            filters.selectedPatterns = filters.selectedPatterns.filter(
              (p) => p !== pattern
            )
          "
        />
        <Chip
          v-for="status in filters.selectedStatuses"
          :key="status"
          :label="`Status: ${status}`"
          removable
          @remove="
            filters.selectedStatuses = filters.selectedStatuses.filter(
              (s) => s !== status
            )
          "
        />
        <Chip
          v-for="symbol in filters.selectedSymbols"
          :key="symbol"
          :label="`Symbol: ${symbol}`"
          removable
          @remove="
            filters.selectedSymbols = filters.selectedSymbols.filter(
              (s) => s !== symbol
            )
          "
        />
        <Chip
          v-if="filters.searchText"
          :label="`Search: ${filters.searchText}`"
          removable
          @remove="filters.searchText = ''"
        />
      </div>
    </div>

    <!-- Data Table -->
    <DataTable
      :value="auditLogEntries"
      :loading="isLoading"
      :lazy="true"
      :paginator="true"
      :rows="rowsPerPage"
      :total-records="totalCount"
      :first="currentPage * rowsPerPage"
      :sort-field="sortField"
      :sort-order="sortOrder"
      paginator-template="FirstPageLink PrevPageLink PageLinks NextPageLink LastPageLink CurrentPageReport"
      :current-page-report-template="`Showing ${
        currentPage * rowsPerPage + 1
      }-${Math.min(
        (currentPage + 1) * rowsPerPage,
        totalCount
      )} of ${totalCount} results`"
      class="bg-gray-800"
      scrollable
      scroll-height="600px"
      @sort="onSort"
      @page="onPage"
    >
      <!-- Timestamp Column -->
      <Column field="timestamp" header="Timestamp" sortable>
        <template #body="{ data }">
          <span :title="new Date(data.timestamp).toLocaleString()">
            {{ formatTimestamp(data.timestamp) }}
          </span>
        </template>
      </Column>

      <!-- Symbol Column -->
      <Column field="symbol" header="Symbol" sortable>
        <template #body="{ data }">
          <span class="font-bold">{{ data.symbol }}</span>
        </template>
      </Column>

      <!-- Pattern Column -->
      <Column field="pattern_type" header="Pattern" sortable>
        <template #body="{ data }">
          <span>{{ data.pattern_type }}</span>
        </template>
      </Column>

      <!-- Phase Column -->
      <Column field="phase" header="Phase">
        <template #body="{ data }">
          <Tag :value="`Phase ${data.phase}`" severity="info" />
        </template>
      </Column>

      <!-- Confidence Column -->
      <Column field="confidence_score" header="Confidence" sortable>
        <template #body="{ data }">
          <span :class="getConfidenceColor(data.confidence_score)">
            {{ data.confidence_score }}%
          </span>
        </template>
      </Column>

      <!-- Status Column -->
      <Column field="status" header="Status" sortable>
        <template #body="{ data }">
          <Tag :value="data.status" :severity="getStatusColor(data.status)" />
        </template>
      </Column>

      <!-- Rejection Reason Column -->
      <Column field="rejection_reason" header="Rejection Reason">
        <template #body="{ data }">
          <span
            v-if="data.rejection_reason"
            :title="data.rejection_reason"
            class="truncate max-w-xs block"
          >
            {{ data.rejection_reason.substring(0, 50)
            }}{{ data.rejection_reason.length > 50 ? '...' : '' }}
          </span>
          <span v-else class="text-gray-500">-</span>
        </template>
      </Column>

      <!-- Expand Column -->
      <Column>
        <template #body="{ data }">
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

      <!-- Row Expansion Template -->
      <template #expansion="{ data }">
        <div v-if="expandedRowId === data.id" class="p-4 bg-gray-900">
          <h3 class="text-lg font-bold text-white mb-4">Validation Chain</h3>

          <!-- Validation Steps -->
          <div class="space-y-4">
            <div
              v-for="(step, index) in data.validation_chain"
              :key="index"
              class="flex items-start gap-4 p-3 rounded bg-gray-800"
            >
              <!-- Pass/Fail Icon -->
              <div class="flex-shrink-0 mt-1">
                <i
                  v-if="step.passed"
                  class="pi pi-check-circle text-green-500 text-xl"
                  aria-label="Passed"
                ></i>
                <i
                  v-else
                  class="pi pi-times-circle text-red-500 text-xl"
                  aria-label="Failed"
                ></i>
              </div>

              <!-- Step Details -->
              <div class="flex-1">
                <div class="flex items-center gap-2">
                  <h4 class="font-semibold text-white">{{ step.step_name }}</h4>
                  <!-- Wyckoff Rule Tooltip -->
                  <i
                    class="pi pi-info-circle text-blue-400 cursor-help"
                    :title="`${step.wyckoff_rule_reference}: ${
                      wyckoffRuleExplanations[step.wyckoff_rule_reference]
                    }`"
                  ></i>
                </div>
                <p class="text-sm text-gray-400 mt-1">{{ step.reason }}</p>
                <p class="text-xs text-gray-500 mt-2">
                  <strong>Wyckoff Rule:</strong>
                  {{ step.wyckoff_rule_reference }}
                </p>
              </div>
            </div>
          </div>

          <!-- Pattern Metadata -->
          <div v-if="data.entry_price" class="mt-6">
            <h3 class="text-lg font-bold text-white mb-3">Pattern Details</h3>
            <div class="grid grid-cols-2 md:grid-cols-4 gap-4">
              <div>
                <p class="text-xs text-gray-400">Entry Price</p>
                <p class="text-sm font-semibold text-white">
                  ${{ formatPrice(data.entry_price) }}
                </p>
              </div>
              <div>
                <p class="text-xs text-gray-400">Target Price</p>
                <p class="text-sm font-semibold text-white">
                  ${{ formatPrice(data.target_price) }}
                </p>
              </div>
              <div>
                <p class="text-xs text-gray-400">Stop Loss</p>
                <p class="text-sm font-semibold text-white">
                  ${{ formatPrice(data.stop_loss) }}
                </p>
              </div>
              <div>
                <p class="text-xs text-gray-400">R-Multiple</p>
                <p class="text-sm font-semibold text-white">
                  {{ data.r_multiple }}R
                </p>
              </div>
            </div>
          </div>
        </div>
      </template>

      <!-- Empty State -->
      <template #empty>
        <div class="text-center py-8 text-gray-400">
          No audit log entries found
        </div>
      </template>

      <!-- Loading State -->
      <template #loading>
        <div class="text-center py-8 text-gray-400">Loading audit log...</div>
      </template>
    </DataTable>
  </div>
</template>

<style scoped>
.trade-audit-log {
  @apply bg-gray-900 rounded-lg;
}

/* PrimeVue dark theme overrides */
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

:deep(.p-multiselect) {
  @apply bg-gray-700 text-white;
}

:deep(.p-inputtext) {
  @apply bg-gray-700 text-white border-gray-600;
}
</style>
