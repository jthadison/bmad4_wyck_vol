<template>
  <div>
    <div class="flex items-center justify-between mb-6">
      <div>
        <h1 class="text-2xl font-bold text-gray-100">Order Management</h1>
        <p class="text-sm text-gray-500 mt-1">
          View and manage pending orders across all brokers
        </p>
      </div>
      <button
        class="px-3 py-2 rounded-md text-sm font-medium bg-[#1a2236] border border-[#2a3a5c] text-gray-300 hover:bg-[#1e2d4a] transition-colors"
        :disabled="store.isLoading"
        @click="store.fetchOrders()"
      >
        <i class="pi pi-refresh mr-1"></i>
        Refresh
      </button>
    </div>

    <OrderTable />
  </div>
</template>

<script setup lang="ts">
import { onMounted } from 'vue'
import OrderTable from '@/components/orders/OrderTable.vue'
import { useOrdersStore } from '@/stores/orders'

const store = useOrdersStore()

onMounted(() => {
  store.fetchOrders()
})
</script>
