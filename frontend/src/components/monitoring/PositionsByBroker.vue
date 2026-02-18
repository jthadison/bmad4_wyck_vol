<template>
  <Card class="positions-by-broker">
    <template #title>
      <div class="flex items-center gap-2">
        <i class="pi pi-briefcase text-blue-500"></i>
        <span>Positions by Broker</span>
      </div>
    </template>
    <template #content>
      <div
        v-if="brokerNames.length === 0"
        class="text-gray-400 text-sm py-4 text-center"
      >
        No open positions
      </div>
      <div v-for="broker in brokerNames" :key="broker" class="mb-4 last:mb-0">
        <h4
          class="text-sm font-semibold text-gray-300 mb-2 uppercase tracking-wide"
        >
          {{ broker }}
        </h4>
        <DataTable
          :value="positions[broker]"
          size="small"
          striped-rows
          class="p-datatable-sm"
        >
          <Column field="symbol" header="Symbol" />
          <Column field="side" header="Side">
            <template #body="{ data }">
              <span
                :class="
                  data.side === 'LONG' ? 'text-green-400' : 'text-red-400'
                "
              >
                {{ data.side }}
              </span>
            </template>
          </Column>
          <Column field="size" header="Size" />
          <Column field="entry_price" header="Entry">
            <template #body="{ data }">
              {{ formatPrice(data.entry_price) }}
            </template>
          </Column>
          <Column field="current_price" header="Current">
            <template #body="{ data }">
              {{ formatPrice(data.current_price) }}
            </template>
          </Column>
          <Column field="unrealized_pnl" header="P&L">
            <template #body="{ data }">
              <span
                :class="
                  data.unrealized_pnl >= 0 ? 'text-green-400' : 'text-red-400'
                "
              >
                {{ formatPnl(data.unrealized_pnl) }}
              </span>
            </template>
          </Column>
        </DataTable>
      </div>
    </template>
  </Card>
</template>

<script setup lang="ts">
/**
 * PositionsByBroker.vue - Positions grouped by broker
 *
 * Story 23.13: Production Monitoring Dashboard
 *
 * Displays open positions in a PrimeVue DataTable, grouped by broker name.
 */
import { computed } from 'vue'
import Card from 'primevue/card'
import DataTable from 'primevue/datatable'
import Column from 'primevue/column'
import type { PositionByBroker } from '@/types/monitoring'

interface Props {
  positions: Record<string, PositionByBroker[]>
}

const props = defineProps<Props>()

const brokerNames = computed(() => Object.keys(props.positions))

function formatPrice(value: number): string {
  return value.toFixed(2)
}

function formatPnl(value: number): string {
  const prefix = value >= 0 ? '+' : ''
  return `${prefix}${value.toFixed(2)}`
}
</script>
