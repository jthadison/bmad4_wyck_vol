/**
 * Audit Trail Pinia Store (Task #2 - Correlation Override Audit Trail)
 *
 * State management for the audit trail admin dashboard.
 * Handles filtering, pagination, and data fetching.
 */

import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { getAuditTrail } from '@/services/api'
import type {
  AuditTrailEntry,
  AuditTrailQueryParams,
} from '@/types/audit-trail'

export const useAuditTrailStore = defineStore('auditTrail', () => {
  // State
  const entries = ref<AuditTrailEntry[]>([])
  const totalCount = ref(0)
  const isLoading = ref(false)
  const error = ref<string | null>(null)

  // Pagination
  const currentPage = ref(0)
  const rowsPerPage = ref(100)

  // Filters
  const eventTypeFilter = ref<string | null>(null)
  const entityTypeFilter = ref<string | null>(null)
  const actorFilter = ref<string | null>(null)
  const startDate = ref<Date | null>(null)
  const endDate = ref<Date | null>(null)

  // Computed
  const hasEntries = computed(() => entries.value.length > 0)
  const totalPages = computed(() =>
    Math.ceil(totalCount.value / rowsPerPage.value)
  )

  /**
   * Count how many unique actors have more than `threshold` overrides
   * in the current result set. Used for suspicious pattern highlighting.
   */
  const suspiciousActors = computed(() => {
    const threshold = 5
    const actorCounts = new Map<string, number>()
    for (const entry of entries.value) {
      if (entry.event_type === 'CORRELATION_OVERRIDE') {
        actorCounts.set(entry.actor, (actorCounts.get(entry.actor) || 0) + 1)
      }
    }
    const suspicious = new Set<string>()
    for (const [actor, count] of actorCounts) {
      if (count >= threshold) {
        suspicious.add(actor)
      }
    }
    return suspicious
  })

  // Actions
  async function fetchEntries() {
    isLoading.value = true
    error.value = null

    try {
      const params: AuditTrailQueryParams = {
        limit: rowsPerPage.value,
        offset: currentPage.value * rowsPerPage.value,
      }

      if (eventTypeFilter.value) params.event_type = eventTypeFilter.value
      if (entityTypeFilter.value) params.entity_type = entityTypeFilter.value
      if (actorFilter.value) params.actor = actorFilter.value
      if (startDate.value) params.start_date = startDate.value.toISOString()
      if (endDate.value) params.end_date = endDate.value.toISOString()

      const response = await getAuditTrail(params)
      entries.value = response.data
      totalCount.value = response.total_count
    } catch (err) {
      error.value =
        err instanceof Error ? err.message : 'Failed to fetch audit trail'
      console.error('Failed to fetch audit trail:', err)
    } finally {
      isLoading.value = false
    }
  }

  function setPage(page: number) {
    currentPage.value = page
    fetchEntries()
  }

  function clearFilters() {
    eventTypeFilter.value = null
    entityTypeFilter.value = null
    actorFilter.value = null
    startDate.value = null
    endDate.value = null
    currentPage.value = 0
    fetchEntries()
  }

  function isActorSuspicious(actor: string): boolean {
    return suspiciousActors.value.has(actor)
  }

  return {
    // State
    entries,
    totalCount,
    isLoading,
    error,
    currentPage,
    rowsPerPage,
    eventTypeFilter,
    entityTypeFilter,
    actorFilter,
    startDate,
    endDate,
    // Computed
    hasEntries,
    totalPages,
    suspiciousActors,
    // Actions
    fetchEntries,
    setPage,
    clearFilters,
    isActorSuspicious,
  }
})
