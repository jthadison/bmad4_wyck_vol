<template>
  <div
    class="paper-trading-dashboard bg-gray-800 border border-gray-700 rounded-lg shadow-lg p-6"
  >
    <!-- Header with title and refresh button -->
    <div class="flex items-center justify-between mb-6">
      <h2 class="text-2xl font-bold text-gray-100 flex items-center gap-2">
        <i class="pi pi-chart-line text-green-400"></i>
        Paper Trading Dashboard
      </h2>
      <div class="flex items-center gap-4">
        <span v-if="lastUpdated" class="text-sm text-gray-400">
          Last updated: {{ formatLastUpdated(lastUpdated) }}
        </span>
        <button
          :disabled="loading"
          class="px-4 py-2 bg-blue-600 hover:bg-blue-700 disabled:bg-gray-600 disabled:cursor-not-allowed text-white rounded-lg transition-colors flex items-center gap-2"
          @click="handleRefresh"
        >
          <i class="pi pi-refresh" :class="{ 'pi-spin': loading }"></i>
          Refresh
        </button>
      </div>
    </div>

    <!-- Loading State -->
    <div
      v-if="loading && !isDataLoaded"
      class="flex items-center justify-center py-20"
    >
      <div class="text-center">
        <i class="pi pi-spin pi-spinner text-4xl text-blue-400 mb-4"></i>
        <p class="text-gray-300">Loading paper trading data...</p>
      </div>
    </div>

    <!-- Error State -->
    <div
      v-else-if="error"
      class="bg-red-900/30 border border-red-700 rounded-lg p-6 text-center"
    >
      <i class="pi pi-exclamation-triangle text-4xl text-red-400 mb-4"></i>
      <p class="text-red-300 mb-4">{{ error }}</p>
      <button
        class="px-4 py-2 bg-red-600 hover:bg-red-700 text-white rounded-lg transition-colors"
        @click="handleRefresh"
      >
        Try Again
      </button>
    </div>

    <!-- Main Content -->
    <div v-else-if="isDataLoaded" class="space-y-6">
      <!-- Account Metrics Cards -->
      <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <!-- Equity Card -->
        <div class="bg-gray-700/50 rounded-lg p-4 border border-gray-600">
          <div class="flex items-center justify-between mb-2">
            <span class="text-gray-400 text-sm">Equity</span>
            <i class="pi pi-wallet text-blue-400"></i>
          </div>
          <p class="text-2xl font-bold text-gray-100">
            ${{ formatNumber(account?.equity || 0) }}
          </p>
          <p class="text-xs text-gray-500 mt-1">
            Starting: ${{ formatNumber(account?.starting_capital || 0) }}
          </p>
        </div>

        <!-- Total P&L Card -->
        <div class="bg-gray-700/50 rounded-lg p-4 border border-gray-600">
          <div class="flex items-center justify-between mb-2">
            <span class="text-gray-400 text-sm">Total P&L</span>
            <i class="pi pi-chart-line" :class="totalPnlColor"></i>
          </div>
          <p class="text-2xl font-bold" :class="totalPnlColor">
            {{ totalPnlSign }}${{ formatNumber(Math.abs(totalPnl)) }}
          </p>
          <p class="text-xs text-gray-500 mt-1">
            Realized: ${{ formatNumber(account?.total_realized_pnl || 0) }}
          </p>
        </div>

        <!-- Win Rate Card -->
        <div class="bg-gray-700/50 rounded-lg p-4 border border-gray-600">
          <div class="flex items-center justify-between mb-2">
            <span class="text-gray-400 text-sm">Win Rate</span>
            <i class="pi pi-percentage text-purple-400"></i>
          </div>
          <p class="text-2xl font-bold text-gray-100">
            {{ formatNumber(account?.win_rate || 0, 1) }}%
          </p>
          <p class="text-xs text-gray-500 mt-1">
            {{ account?.winning_trades || 0 }}W /
            {{ account?.losing_trades || 0 }}L
          </p>
        </div>

        <!-- Portfolio Heat Card -->
        <div class="bg-gray-700/50 rounded-lg p-4 border border-gray-600">
          <div class="flex items-center justify-between mb-2">
            <span class="text-gray-400 text-sm">Portfolio Heat</span>
            <i class="pi pi-fire" :class="heatColor"></i>
          </div>
          <p class="text-2xl font-bold" :class="heatColor">
            {{ formatNumber(account?.current_heat || 0, 1) }}%
          </p>
          <p class="text-xs text-gray-500 mt-1">Limit: 10%</p>
        </div>
      </div>

      <!-- Additional Metrics Row -->
      <div class="grid grid-cols-1 md:grid-cols-3 gap-4">
        <!-- Average R-Multiple Card -->
        <div class="bg-gray-700/50 rounded-lg p-4 border border-gray-600">
          <div class="flex items-center justify-between mb-2">
            <span class="text-gray-400 text-sm">Avg R-Multiple</span>
            <i class="pi pi-bolt text-yellow-400"></i>
          </div>
          <p class="text-xl font-bold text-gray-100">
            {{ formatNumber(account?.average_r_multiple || 0, 2) }}R
          </p>
        </div>

        <!-- Max Drawdown Card -->
        <div class="bg-gray-700/50 rounded-lg p-4 border border-gray-600">
          <div class="flex items-center justify-between mb-2">
            <span class="text-gray-400 text-sm">Max Drawdown</span>
            <i class="pi pi-arrow-down text-red-400"></i>
          </div>
          <p class="text-xl font-bold text-red-300">
            {{ formatNumber(account?.max_drawdown || 0, 2) }}%
          </p>
        </div>

        <!-- Total Trades Card -->
        <div class="bg-gray-700/50 rounded-lg p-4 border border-gray-600">
          <div class="flex items-center justify-between mb-2">
            <span class="text-gray-400 text-sm">Total Trades</span>
            <i class="pi pi-list text-gray-400"></i>
          </div>
          <p class="text-xl font-bold text-gray-100">
            {{ account?.total_trades || 0 }}
          </p>
        </div>
      </div>

      <!-- Open Positions Table -->
      <div
        class="bg-gray-700/50 rounded-lg border border-gray-600 overflow-hidden"
      >
        <div class="p-4 border-b border-gray-600">
          <h3
            class="text-lg font-semibold text-gray-100 flex items-center gap-2"
          >
            <i class="pi pi-folder-open text-green-400"></i>
            Open Positions ({{ openPositions?.length || 0 }})
          </h3>
        </div>
        <DataTable
          :value="openPositions"
          :paginator="openPositions && openPositions.length > 10"
          :rows="10"
          :loading="loading"
          class="p-datatable-sm"
          responsive-layout="scroll"
        >
          <template #empty>
            <div class="text-center py-8 text-gray-400">
              <i class="pi pi-inbox text-4xl mb-2"></i>
              <p>No open positions</p>
            </div>
          </template>
          <Column field="symbol" header="Symbol" :sortable="true">
            <template #body="{ data }">
              <span class="font-mono font-semibold text-blue-300">{{
                data.symbol
              }}</span>
            </template>
          </Column>
          <Column field="quantity" header="Quantity" :sortable="true">
            <template #body="{ data }">
              <span class="font-mono">{{
                formatNumber(data.quantity, 0)
              }}</span>
            </template>
          </Column>
          <Column field="entry_price" header="Entry Price" :sortable="true">
            <template #body="{ data }">
              <span class="font-mono"
                >${{ formatNumber(data.entry_price, 2) }}</span
              >
            </template>
          </Column>
          <Column field="current_price" header="Current Price" :sortable="true">
            <template #body="{ data }">
              <span class="font-mono"
                >${{ formatNumber(data.current_price, 2) }}</span
              >
            </template>
          </Column>
          <Column
            field="unrealized_pnl"
            header="Unrealized P&L"
            :sortable="true"
          >
            <template #body="{ data }">
              <span
                class="font-mono font-semibold"
                :class="
                  data.unrealized_pnl >= 0 ? 'text-green-400' : 'text-red-400'
                "
              >
                {{ data.unrealized_pnl >= 0 ? '+' : '' }}${{
                  formatNumber(data.unrealized_pnl, 2)
                }}
              </span>
            </template>
          </Column>
          <Column field="stop_loss" header="Stop Loss" :sortable="true">
            <template #body="{ data }">
              <span class="font-mono text-red-300"
                >${{ formatNumber(data.stop_loss, 2) }}</span
              >
            </template>
          </Column>
          <Column field="target_1" header="Target" :sortable="true">
            <template #body="{ data }">
              <span class="font-mono text-green-300"
                >${{ formatNumber(data.target_1, 2) }}</span
              >
            </template>
          </Column>
          <Column field="status" header="Status" :sortable="true">
            <template #body="{ data }">
              <span
                class="px-2 py-1 rounded text-xs font-semibold"
                :class="getStatusClass(data.status)"
              >
                {{ data.status }}
              </span>
            </template>
          </Column>
          <Column field="entry_time" header="Entry Time" :sortable="true">
            <template #body="{ data }">
              <span class="text-sm text-gray-400">{{
                formatDateTime(data.entry_time)
              }}</span>
            </template>
          </Column>
        </DataTable>
      </div>

      <!-- Recent Trades Table -->
      <div
        class="bg-gray-700/50 rounded-lg border border-gray-600 overflow-hidden"
      >
        <div class="p-4 border-b border-gray-600">
          <h3
            class="text-lg font-semibold text-gray-100 flex items-center gap-2"
          >
            <i class="pi pi-history text-purple-400"></i>
            Recent Trades ({{ recentTrades?.length || 0 }})
          </h3>
        </div>
        <DataTable
          :value="recentTrades"
          :paginator="recentTrades && recentTrades.length > 10"
          :rows="10"
          :loading="loading"
          class="p-datatable-sm"
          responsive-layout="scroll"
        >
          <template #empty>
            <div class="text-center py-8 text-gray-400">
              <i class="pi pi-inbox text-4xl mb-2"></i>
              <p>No trades yet</p>
            </div>
          </template>
          <Column field="symbol" header="Symbol" :sortable="true">
            <template #body="{ data }">
              <span class="font-mono font-semibold text-blue-300">{{
                data.symbol
              }}</span>
            </template>
          </Column>
          <Column field="quantity" header="Quantity" :sortable="true">
            <template #body="{ data }">
              <span class="font-mono">{{
                formatNumber(data.quantity, 0)
              }}</span>
            </template>
          </Column>
          <Column field="entry_price" header="Entry" :sortable="true">
            <template #body="{ data }">
              <span class="font-mono"
                >${{ formatNumber(data.entry_price, 2) }}</span
              >
            </template>
          </Column>
          <Column field="exit_price" header="Exit" :sortable="true">
            <template #body="{ data }">
              <span class="font-mono"
                >${{ formatNumber(data.exit_price, 2) }}</span
              >
            </template>
          </Column>
          <Column field="realized_pnl" header="Realized P&L" :sortable="true">
            <template #body="{ data }">
              <span
                class="font-mono font-semibold"
                :class="
                  data.realized_pnl >= 0 ? 'text-green-400' : 'text-red-400'
                "
              >
                {{ data.realized_pnl >= 0 ? '+' : '' }}${{
                  formatNumber(data.realized_pnl, 2)
                }}
              </span>
            </template>
          </Column>
          <Column
            field="r_multiple_achieved"
            header="R-Multiple"
            :sortable="true"
          >
            <template #body="{ data }">
              <span
                class="font-mono font-semibold"
                :class="
                  data.r_multiple_achieved >= 0
                    ? 'text-green-400'
                    : 'text-red-400'
                "
              >
                {{ data.r_multiple_achieved >= 0 ? '+' : ''
                }}{{ formatNumber(data.r_multiple_achieved, 2) }}R
              </span>
            </template>
          </Column>
          <Column field="exit_reason" header="Exit Reason" :sortable="true">
            <template #body="{ data }">
              <span
                class="px-2 py-1 rounded text-xs font-semibold"
                :class="getExitReasonClass(data.exit_reason)"
              >
                {{ data.exit_reason }}
              </span>
            </template>
          </Column>
          <Column field="commission_total" header="Commission" :sortable="true">
            <template #body="{ data }">
              <span class="font-mono text-gray-400 text-sm"
                >${{ formatNumber(data.commission_total, 2) }}</span
              >
            </template>
          </Column>
          <Column field="exit_time" header="Exit Time" :sortable="true">
            <template #body="{ data }">
              <span class="text-sm text-gray-400">{{
                formatDateTime(data.exit_time)
              }}</span>
            </template>
          </Column>
        </DataTable>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { storeToRefs } from 'pinia'
import DataTable from 'primevue/datatable'
import Column from 'primevue/column'
import { usePaperTradingStore } from '@/stores/paperTradingStore'

const store = usePaperTradingStore()
const { account, openPositions, recentTrades, loading, error } =
  storeToRefs(store)

const lastUpdated = ref<Date | null>(null)

const isDataLoaded = computed(() => account.value !== null)

const totalPnl = computed(() => {
  if (!account.value) return 0
  return (
    parseFloat(account.value.total_realized_pnl || '0') +
    parseFloat(account.value.total_unrealized_pnl || '0')
  )
})

const totalPnlColor = computed(() => {
  return totalPnl.value >= 0 ? 'text-green-400' : 'text-red-400'
})

const totalPnlSign = computed(() => {
  return totalPnl.value >= 0 ? '+' : ''
})

const heatColor = computed(() => {
  const heat = parseFloat(account.value?.current_heat || '0')
  if (heat >= 10) return 'text-red-400'
  if (heat >= 8) return 'text-orange-400'
  if (heat >= 5) return 'text-yellow-400'
  return 'text-green-400'
})

const formatNumber = (value: number | string, decimals: number = 2): string => {
  const num = typeof value === 'string' ? parseFloat(value) : value
  return num.toFixed(decimals).replace(/\B(?=(\d{3})+(?!\d))/g, ',')
}

const formatDateTime = (dateString: string): string => {
  if (!dateString) return 'N/A'
  const date = new Date(dateString)
  return date.toLocaleString('en-US', {
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  })
}

const formatLastUpdated = (date: Date): string => {
  const now = new Date()
  const diff = Math.floor((now.getTime() - date.getTime()) / 1000) // seconds

  if (diff < 60) return `${diff}s ago`
  if (diff < 3600) return `${Math.floor(diff / 60)}m ago`
  if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`
  return date.toLocaleString('en-US', {
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  })
}

const getStatusClass = (status: string): string => {
  const statusMap: Record<string, string> = {
    OPEN: 'bg-green-900/50 text-green-300 border border-green-700',
    STOPPED: 'bg-red-900/50 text-red-300 border border-red-700',
    TARGET_1_HIT: 'bg-blue-900/50 text-blue-300 border border-blue-700',
    TARGET_2_HIT: 'bg-purple-900/50 text-purple-300 border border-purple-700',
    CLOSED: 'bg-gray-700 text-gray-300 border border-gray-600',
  }
  return statusMap[status] || 'bg-gray-700 text-gray-300'
}

const getExitReasonClass = (reason: string): string => {
  const reasonMap: Record<string, string> = {
    STOP_LOSS: 'bg-red-900/50 text-red-300 border border-red-700',
    TARGET_1: 'bg-green-900/50 text-green-300 border border-green-700',
    TARGET_2: 'bg-blue-900/50 text-blue-300 border border-blue-700',
    MANUAL: 'bg-yellow-900/50 text-yellow-300 border border-yellow-700',
    TIMEOUT: 'bg-orange-900/50 text-orange-300 border border-orange-700',
  }
  return reasonMap[reason] || 'bg-gray-700 text-gray-300'
}

const handleRefresh = async () => {
  await store.fetchAccount()
  await store.fetchPositions()
  await store.fetchTrades()
  lastUpdated.value = new Date()
}

onMounted(async () => {
  await store.initialize()
  lastUpdated.value = new Date()
})
</script>

<style scoped>
/* PrimeVue DataTable dark theme customization */
:deep(.p-datatable) {
  background: transparent;
  color: #e5e7eb;
}

:deep(.p-datatable .p-datatable-thead > tr > th) {
  background: #374151;
  color: #d1d5db;
  border-color: #4b5563;
  padding: 0.75rem 1rem;
}

:deep(.p-datatable .p-datatable-tbody > tr) {
  background: transparent;
  color: #e5e7eb;
}

:deep(.p-datatable .p-datatable-tbody > tr > td) {
  border-color: #4b5563;
  padding: 0.75rem 1rem;
}

:deep(.p-datatable .p-datatable-tbody > tr:hover) {
  background: rgba(55, 65, 81, 0.5);
}

:deep(.p-paginator) {
  background: #374151;
  color: #d1d5db;
  border-color: #4b5563;
}

:deep(.p-paginator .p-paginator-pages .p-paginator-page) {
  color: #d1d5db;
}

:deep(.p-paginator .p-paginator-pages .p-paginator-page.p-highlight) {
  background: #3b82f6;
  color: white;
}
</style>
