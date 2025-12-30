<template>
  <div v-if="paperTradingStore.isEnabled" class="paper-trading-banner">
    <i class="pi pi-exclamation-triangle"></i>
    <span class="banner-text">
      ⚠️ PAPER TRADING MODE - No real capital at risk
    </span>
    <span class="equity-info">
      Equity: ${{ formatNumber(paperTradingStore.currentEquity) }} | Heat:
      {{ formatPercent(paperTradingStore.currentHeat) }}
    </span>
  </div>
</template>

<script setup lang="ts">
import { onMounted } from 'vue'
import { usePaperTradingStore } from '@/stores/paperTradingStore'

/**
 * Paper Trading Banner Component (Story 12.8 Task 10)
 *
 * Always-visible banner shown when paper trading is active.
 * Displays warning and key metrics.
 *
 * Author: Story 12.8
 */

const paperTradingStore = usePaperTradingStore()

onMounted(() => {
  paperTradingStore.initialize()
})

function formatNumber(value: number): string {
  return value.toLocaleString('en-US', {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })
}

function formatPercent(value: number): string {
  return `${value.toFixed(2)}%`
}
</script>

<style scoped>
.paper-trading-banner {
  position: fixed;
  top: 60px;
  left: 0;
  right: 0;
  z-index: 999;
  background: linear-gradient(135deg, #ff9800 0%, #f57c00 100%);
  color: white;
  padding: 0.75rem 1.5rem;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 1rem;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.15);
  font-weight: 600;
  font-size: 0.9375rem;
}

.paper-trading-banner i {
  font-size: 1.25rem;
  animation: pulse 2s ease-in-out infinite;
}

.banner-text {
  font-size: 1rem;
  letter-spacing: 0.5px;
}

.equity-info {
  margin-left: auto;
  font-size: 0.875rem;
  opacity: 0.95;
}

@keyframes pulse {
  0%,
  100% {
    opacity: 1;
  }
  50% {
    opacity: 0.6;
  }
}
</style>
