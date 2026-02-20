<template>
  <div>
    <!-- Error banner -->
    <div
      v-if="store.error"
      class="mb-4 p-3 rounded-md bg-red-900/30 border border-red-700 text-red-300 text-sm"
    >
      {{ store.error }}
    </div>

    <!-- Broker status badges -->
    <div class="flex items-center gap-3 mb-4">
      <span class="text-xs text-gray-500 uppercase tracking-wider"
        >Brokers:</span
      >
      <span
        v-for="(connected, name) in store.brokersConnected"
        :key="name"
        class="inline-flex items-center gap-1.5 px-2 py-0.5 rounded text-xs font-medium"
        :class="
          connected
            ? 'bg-green-900/30 text-green-400 border border-green-700'
            : 'bg-gray-800 text-gray-500 border border-gray-700'
        "
      >
        <span
          class="w-1.5 h-1.5 rounded-full"
          :class="connected ? 'bg-green-400' : 'bg-gray-600'"
        ></span>
        {{ name }}
      </span>
    </div>

    <!-- Loading skeleton -->
    <div v-if="store.isLoading" class="space-y-3">
      <div
        v-for="i in 3"
        :key="i"
        class="h-12 bg-[#131d33] rounded animate-pulse"
      ></div>
    </div>

    <!-- Empty state -->
    <div
      v-else-if="store.orders.length === 0"
      class="text-center py-16 text-gray-500"
    >
      <i class="pi pi-inbox text-4xl mb-3 block"></i>
      <p class="text-lg font-medium">No pending orders</p>
      <p class="text-sm mt-1">
        Orders placed through the system will appear here.
      </p>
    </div>

    <!-- Orders table -->
    <div v-else class="overflow-x-auto">
      <table class="w-full text-sm text-left">
        <thead
          class="text-xs text-gray-500 uppercase tracking-wider border-b border-[#1e2d4a]"
        >
          <tr>
            <th
              v-for="col in columns"
              :key="col.key"
              class="px-3 py-3 cursor-pointer hover:text-gray-300 select-none"
              @click="toggleSort(col.key)"
            >
              <span class="flex items-center gap-1">
                {{ col.label }}
                <i
                  v-if="sortKey === col.key"
                  :class="
                    sortAsc
                      ? 'pi pi-sort-amount-up-alt'
                      : 'pi pi-sort-amount-down'
                  "
                  class="text-xs text-blue-400"
                ></i>
              </span>
            </th>
            <th class="px-3 py-3">Actions</th>
          </tr>
        </thead>
        <tbody>
          <template v-for="order in sortedOrders" :key="order.order_id">
            <!-- OCO group header -->
            <tr
              v-if="isOcoGroupStart(order)"
              class="bg-blue-900/10 border-t border-blue-800/30"
            >
              <td
                :colspan="columns.length + 1"
                class="px-3 py-1.5 text-xs text-blue-400 font-medium"
              >
                OCO Group: {{ order.oco_group_id }}
              </td>
            </tr>

            <!-- Order row -->
            <tr
              class="border-b border-[#1a2236] hover:bg-white/[0.02] transition-colors"
              :class="{ 'pl-6': order.is_oco }"
            >
              <td class="px-3 py-3 font-mono text-gray-300">
                {{ order.symbol || '--' }}
              </td>
              <td class="px-3 py-3">
                <span
                  class="px-2 py-0.5 rounded text-xs font-medium"
                  :class="
                    order.broker === 'alpaca'
                      ? 'bg-purple-900/30 text-purple-300'
                      : 'bg-indigo-900/30 text-indigo-300'
                  "
                >
                  {{ order.broker }}
                </span>
              </td>
              <td class="px-3 py-3">
                <span
                  class="px-2 py-0.5 rounded text-xs font-bold uppercase"
                  :class="
                    order.side === 'buy' || order.side === 'BUY'
                      ? 'bg-green-900/30 text-green-400'
                      : 'bg-red-900/30 text-red-400'
                  "
                >
                  {{ order.side || '--' }}
                </span>
              </td>
              <td class="px-3 py-3 text-gray-400">
                {{ order.order_type || '--' }}
              </td>
              <td class="px-3 py-3 font-mono text-gray-300">
                {{ order.remaining_quantity }}
              </td>
              <td class="px-3 py-3 font-mono text-gray-300">
                {{ order.limit_price ?? '--' }}
              </td>
              <td class="px-3 py-3">
                <span
                  class="px-2 py-0.5 rounded text-xs font-medium"
                  :class="statusClass(order.status)"
                >
                  {{ order.status }}
                </span>
              </td>
              <td class="px-3 py-3 text-gray-500 text-xs">
                {{ formatAge(order.created_at) }}
              </td>
              <td class="px-3 py-3">
                <div class="flex items-center gap-2">
                  <button
                    class="px-2 py-1 rounded text-xs font-medium text-red-400 hover:bg-red-900/30 transition-colors"
                    :disabled="store.isSaving"
                    @click="handleCancel(order.order_id)"
                  >
                    Cancel
                  </button>
                </div>
              </td>
            </tr>
          </template>
        </tbody>
      </table>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import { useOrdersStore } from '@/stores/orders'
import type { PendingOrder } from '@/services/ordersService'

const store = useOrdersStore()

// Sorting
const sortKey = ref<string>('created_at')
const sortAsc = ref(false)

const columns = [
  { key: 'symbol', label: 'Symbol' },
  { key: 'broker', label: 'Broker' },
  { key: 'side', label: 'Side' },
  { key: 'order_type', label: 'Type' },
  { key: 'remaining_quantity', label: 'Qty Remaining' },
  { key: 'limit_price', label: 'Limit Price' },
  { key: 'status', label: 'Status' },
  { key: 'created_at', label: 'Age' },
]

function toggleSort(key: string): void {
  if (sortKey.value === key) {
    sortAsc.value = !sortAsc.value
  } else {
    sortKey.value = key
    sortAsc.value = true
  }
}

const sortedOrders = computed(() => {
  const key = sortKey.value as keyof PendingOrder
  const dir = sortAsc.value ? 1 : -1
  return [...store.orders].sort((a, b) => {
    const aVal = String(a[key] ?? '')
    const bVal = String(b[key] ?? '')
    return aVal.localeCompare(bVal) * dir
  })
})

async function handleCancel(orderId: string): Promise<void> {
  await store.cancelOrder(orderId)
}

// OCO group detection - computed from sortedOrders so it resets on data change
const ocoGroupFirstOrderIds = computed(() => {
  const seen = new Set<string>()
  const firstIds = new Set<string>()
  for (const order of sortedOrders.value) {
    if (order.is_oco && order.oco_group_id && !seen.has(order.oco_group_id)) {
      seen.add(order.oco_group_id)
      firstIds.add(order.order_id)
    }
  }
  return firstIds
})

function isOcoGroupStart(order: PendingOrder): boolean {
  return ocoGroupFirstOrderIds.value.has(order.order_id)
}

// Status badge styling
function statusClass(status: string): string {
  switch (status) {
    case 'pending':
      return 'bg-yellow-900/30 text-yellow-400 border border-yellow-700/50'
    case 'partial':
      return 'bg-blue-900/30 text-blue-400 border border-blue-700/50'
    case 'rejected':
      return 'bg-red-900/30 text-red-400 border border-red-700/50'
    default:
      return 'bg-gray-800 text-gray-400'
  }
}

// Age formatting
function formatAge(dateStr: string): string {
  if (!dateStr) return '--'
  const created = new Date(dateStr)
  const now = new Date()
  const diffMs = now.getTime() - created.getTime()
  const diffMin = Math.floor(diffMs / 60000)
  if (diffMin < 1) return '<1m'
  if (diffMin < 60) return `${diffMin}m`
  const diffHr = Math.floor(diffMin / 60)
  if (diffHr < 24) return `${diffHr}h`
  const diffDay = Math.floor(diffHr / 24)
  return `${diffDay}d`
}
</script>
