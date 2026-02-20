<template>
  <div>
    <!-- Error banner -->
    <div
      v-if="store.error"
      class="mb-4 p-3 rounded-md bg-red-900/30 border border-red-700 text-red-300 text-sm"
    >
      {{ store.error }}
    </div>

    <!-- Modify notice banner -->
    <div
      v-if="modifyNotice"
      class="mb-4 p-3 rounded-md bg-yellow-900/30 border border-yellow-700 text-yellow-300 text-sm flex items-center justify-between"
    >
      <span>{{ modifyNotice }}</span>
      <button
        class="ml-4 text-yellow-400 hover:text-yellow-200 text-xs font-medium"
        @click="dismissNotice"
      >
        Dismiss
      </button>
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
                <!-- Inline edit mode -->
                <div
                  v-if="editingOrderId === order.order_id"
                  class="flex items-center gap-2"
                >
                  <input
                    v-model="editPrice"
                    type="text"
                    placeholder="New price"
                    class="w-24 px-2 py-1 rounded bg-[#1a2236] border border-[#2a3a5c] text-gray-200 text-xs focus:border-blue-500 focus:outline-none"
                  />
                  <button
                    class="px-2 py-1 rounded text-xs font-medium bg-blue-600 hover:bg-blue-700 text-white disabled:opacity-50"
                    :disabled="store.isSaving"
                    @click="submitModify(order)"
                  >
                    Save
                  </button>
                  <button
                    class="px-2 py-1 rounded text-xs font-medium text-gray-400 hover:text-gray-200"
                    @click="cancelEdit()"
                  >
                    Cancel
                  </button>
                </div>
                <!-- Normal actions -->
                <div v-else class="flex items-center gap-2">
                  <button
                    class="px-2 py-1 rounded text-xs font-medium text-blue-400 hover:bg-blue-900/30 transition-colors"
                    :disabled="store.isSaving"
                    @click="startEdit(order)"
                  >
                    Modify
                  </button>
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
import { ref, computed } from 'vue'
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

// Inline editing
const editingOrderId = ref<string | null>(null)
const editPrice = ref('')
const modifyNotice = ref<string | null>(null)

function startEdit(order: PendingOrder): void {
  editingOrderId.value = order.order_id
  editPrice.value = order.limit_price ?? order.stop_price ?? ''
}

function cancelEdit(): void {
  editingOrderId.value = null
  editPrice.value = ''
}

async function submitModify(order: PendingOrder): Promise<void> {
  if (!editPrice.value.trim()) {
    cancelEdit()
    return
  }
  const payload: Record<string, string> = {}
  if (order.limit_price !== null) {
    payload.limit_price = editPrice.value
  } else if (order.stop_price !== null) {
    payload.stop_price = editPrice.value
  } else {
    payload.limit_price = editPrice.value
  }
  const result = await store.modifyOrder(order.order_id, payload)
  if (result !== false) {
    cancelEdit()
    modifyNotice.value = result
  }
}

function dismissNotice(): void {
  modifyNotice.value = null
}

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
