import { defineStore } from 'pinia'
import { ref, computed } from 'vue'

export const usePortfolioStore = defineStore('portfolio', () => {
  // State
  const totalHeat = ref(0)
  const availableCapacity = ref(100)
  const activeCampaigns = ref(0)

  // Getters
  const heatPercentage = computed(() => {
    if (availableCapacity.value === 0) return 0
    return (totalHeat.value / availableCapacity.value) * 100
  })

  const isNearLimit = computed(() => {
    return heatPercentage.value >= 80
  })

  // Actions
  const fetchPortfolioMetrics = async () => {
    // To be implemented with API integration
    try {
      // Placeholder - will be replaced with actual API call
      totalHeat.value = 0
      availableCapacity.value = 100
      activeCampaigns.value = 0
    } catch (e) {
      console.error('Failed to fetch portfolio metrics:', e)
    }
  }

  return {
    // State
    totalHeat,
    availableCapacity,
    activeCampaigns,

    // Getters
    heatPercentage,
    isNearLimit,

    // Actions
    fetchPortfolioMetrics,
  }
})
