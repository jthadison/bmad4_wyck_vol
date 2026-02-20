<template>
  <div>
    <!-- Header -->
    <div class="flex items-center gap-4 mb-6">
      <Button
        icon="pi pi-arrow-left"
        severity="secondary"
        text
        rounded
        @click="$router.back()"
      />
      <h1 class="text-2xl font-bold text-white">Multi-Timeframe Analysis</h1>
    </div>

    <!-- Symbol Input -->
    <div class="flex items-center gap-3 mb-6">
      <label for="mtf-symbol" class="text-sm text-gray-400">Symbol</label>
      <InputText
        id="mtf-symbol"
        v-model="symbolInput"
        class="w-32 uppercase"
        placeholder="SPY"
        @keydown.enter="applySymbol"
      />
      <Button label="Load" size="small" @click="applySymbol" />
    </div>

    <!-- MTF Panel -->
    <MultiTimeframePanel :symbol="currentSymbol" />
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import MultiTimeframePanel from '@/components/charts/MultiTimeframePanel.vue'
import InputText from 'primevue/inputtext'
import Button from 'primevue/button'

const route = useRoute()
const router = useRouter()

const currentSymbol = ref('SPY')
const symbolInput = ref('SPY')

function applySymbol() {
  const sym = symbolInput.value.trim().toUpperCase()
  if (sym) {
    currentSymbol.value = sym
    router.replace({ query: { symbol: sym } })
  }
}

onMounted(() => {
  const sym = route.query.symbol
  if (typeof sym === 'string' && sym.trim()) {
    currentSymbol.value = sym.trim().toUpperCase()
    symbolInput.value = currentSymbol.value
  }
})
</script>
