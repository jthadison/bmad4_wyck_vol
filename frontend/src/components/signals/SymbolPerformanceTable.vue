<script setup lang="ts">
import { ref } from 'vue'
import DataTable from 'primevue/datatable'
import Column from 'primevue/column'
import type { SymbolPerformance } from '@/services/api'

interface Props {
  data: SymbolPerformance[]
  loading?: boolean
}

withDefaults(defineProps<Props>(), {
  loading: false,
})

const sortField = ref('win_rate')
const sortOrder = ref(-1)

function formatPnl(pnl: string): string {
  const value = parseFloat(pnl)
  const formatted = new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'USD',
    minimumFractionDigits: 0,
    maximumFractionDigits: 0,
  }).format(value)
  return value >= 0 ? `+${formatted}` : formatted
}

function getPnlClass(pnl: string): string {
  const value = parseFloat(pnl)
  return value >= 0 ? 'text-green-400' : 'text-red-400'
}

function getWinRateClass(rate: number): string {
  if (rate >= 60) return 'text-green-400'
  if (rate >= 50) return 'text-yellow-400'
  return 'text-red-400'
}
</script>

<template>
  <div
    class="symbol-performance-table bg-gray-800 rounded-lg p-4 border border-gray-700"
  >
    <h3 class="text-lg font-semibold text-white mb-4">
      Top Performing Symbols
    </h3>

    <div v-if="loading" class="space-y-2">
      <div
        v-for="i in 5"
        :key="i"
        class="animate-pulse flex justify-between p-3 bg-gray-700 rounded"
      >
        <div class="h-4 w-16 bg-gray-600 rounded"></div>
        <div class="h-4 w-12 bg-gray-600 rounded"></div>
        <div class="h-4 w-12 bg-gray-600 rounded"></div>
        <div class="h-4 w-16 bg-gray-600 rounded"></div>
      </div>
    </div>

    <div
      v-else-if="data.length === 0"
      class="h-48 flex items-center justify-center"
    >
      <div class="text-center text-gray-500">
        <i class="pi pi-table text-4xl mb-2"></i>
        <p>No symbol data available</p>
      </div>
    </div>

    <DataTable
      v-else
      v-model:sort-field="sortField"
      v-model:sort-order="sortOrder"
      :value="data"
      :rows="10"
      striped-rows
      class="symbol-table"
      :pt="{
        root: { class: 'bg-transparent' },
        header: { class: 'bg-gray-700 text-gray-300 border-gray-600' },
        bodyRow: { class: 'bg-gray-800 hover:bg-gray-700 border-gray-700' },
      }"
    >
      <Column field="symbol" header="Symbol" sortable>
        <template #body="{ data: row }">
          <span class="font-semibold text-white">{{ row.symbol }}</span>
        </template>
      </Column>

      <Column field="total_signals" header="Signals" sortable>
        <template #body="{ data: row }">
          <span class="text-gray-300">{{ row.total_signals }}</span>
        </template>
      </Column>

      <Column field="win_rate" header="Win Rate" sortable>
        <template #body="{ data: row }">
          <span :class="getWinRateClass(row.win_rate)">
            {{ row.win_rate.toFixed(1) }}%
          </span>
        </template>
      </Column>

      <Column field="avg_r_multiple" header="Avg R" sortable>
        <template #body="{ data: row }">
          <span class="text-gray-300">{{ row.avg_r_multiple.toFixed(2) }}</span>
        </template>
      </Column>

      <Column field="total_pnl" header="P&L" sortable>
        <template #body="{ data: row }">
          <span :class="getPnlClass(row.total_pnl)">
            {{ formatPnl(row.total_pnl) }}
          </span>
        </template>
      </Column>
    </DataTable>
  </div>
</template>

<style scoped>
.symbol-table :deep(.p-datatable-thead > tr > th) {
  background-color: #374151;
  color: #9ca3af;
  border-color: #4b5563;
  padding: 0.75rem 1rem;
}

.symbol-table :deep(.p-datatable-tbody > tr > td) {
  padding: 0.75rem 1rem;
  border-color: #374151;
}

.symbol-table :deep(.p-datatable-tbody > tr:hover) {
  background-color: #374151 !important;
}

.symbol-table :deep(.p-sortable-column-icon) {
  color: #9ca3af;
}
</style>
