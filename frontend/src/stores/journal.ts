/**
 * Journal Store - Pinia state management for Trade Journal
 *
 * Feature P2-8 (Trade Journal)
 */

import { defineStore } from 'pinia'
import { ref } from 'vue'
import journalService, {
  type JournalEntry,
  type JournalEntryCreate,
  type JournalEntryUpdate,
  type JournalListParams,
} from '@/services/journalService'

export const useJournalStore = defineStore('journal', () => {
  // State
  const entries = ref<JournalEntry[]>([])
  const currentEntry = ref<JournalEntry | null>(null)
  const totalCount = ref(0)
  const isLoading = ref(false)
  const isSaving = ref(false)
  const error = ref<string | null>(null)

  // Actions
  async function loadEntries(params: JournalListParams = {}): Promise<void> {
    isLoading.value = true
    error.value = null
    try {
      const result = await journalService.listEntries(params)
      entries.value = result.data
      totalCount.value = result.pagination.total_count
    } catch (e) {
      error.value =
        e instanceof Error ? e.message : 'Failed to load journal entries'
    } finally {
      isLoading.value = false
    }
  }

  async function loadEntry(id: string): Promise<void> {
    isLoading.value = true
    error.value = null
    try {
      currentEntry.value = await journalService.getEntry(id)
    } catch (e) {
      error.value =
        e instanceof Error ? e.message : 'Failed to load journal entry'
    } finally {
      isLoading.value = false
    }
  }

  async function createEntry(
    payload: JournalEntryCreate
  ): Promise<JournalEntry | null> {
    isSaving.value = true
    error.value = null
    try {
      const entry = await journalService.createEntry(payload)
      entries.value.unshift(entry)
      totalCount.value += 1
      return entry
    } catch (e) {
      error.value =
        e instanceof Error ? e.message : 'Failed to create journal entry'
      return null
    } finally {
      isSaving.value = false
    }
  }

  async function updateEntry(
    id: string,
    payload: JournalEntryUpdate
  ): Promise<JournalEntry | null> {
    isSaving.value = true
    error.value = null
    try {
      const updated = await journalService.updateEntry(id, payload)
      // Update in list if present
      const idx = entries.value.findIndex((e) => e.id === id)
      if (idx !== -1) {
        entries.value[idx] = updated
      }
      if (currentEntry.value?.id === id) {
        currentEntry.value = updated
      }
      return updated
    } catch (e) {
      error.value =
        e instanceof Error ? e.message : 'Failed to update journal entry'
      return null
    } finally {
      isSaving.value = false
    }
  }

  async function deleteEntry(id: string): Promise<boolean> {
    error.value = null
    try {
      await journalService.deleteEntry(id)
      entries.value = entries.value.filter((e) => e.id !== id)
      totalCount.value = Math.max(0, totalCount.value - 1)
      if (currentEntry.value?.id === id) {
        currentEntry.value = null
      }
      return true
    } catch (e) {
      error.value =
        e instanceof Error ? e.message : 'Failed to delete journal entry'
      return false
    }
  }

  function clearError(): void {
    error.value = null
  }

  return {
    // State
    entries,
    currentEntry,
    totalCount,
    isLoading,
    isSaving,
    error,
    // Actions
    loadEntries,
    loadEntry,
    createEntry,
    updateEntry,
    deleteEntry,
    clearError,
  }
})
