<script setup lang="ts">
/**
 * JournalView - Main Trade Journal page
 *
 * Shows a list of journal entries with search, filter tabs, and
 * the ability to create/view/edit/delete entries via modal forms.
 *
 * Feature P2-8 (Trade Journal)
 */
import { ref, computed, onMounted } from 'vue'
import { useJournalStore } from '@/stores/journal'
import JournalEntryForm from '@/components/journal/JournalEntryForm.vue'
import JournalEntryDetail from '@/components/journal/JournalEntryDetail.vue'
import type {
  JournalEntry,
  JournalEntryCreate,
  JournalEntryUpdate,
} from '@/services/journalService'

const store = useJournalStore()

// ---- Filter state ----
const searchQuery = ref('')
const activeFilter = ref<'all' | 'pre_trade' | 'post_trade' | 'observation'>(
  'all'
)

// ---- Modal state ----
type ModalMode = 'none' | 'create' | 'view' | 'edit'
const modalMode = ref<ModalMode>('none')
const selectedEntry = ref<JournalEntry | null>(null)

// ---- Computed ----
const filteredEntries = computed(() => {
  let result = store.entries
  if (searchQuery.value.trim()) {
    const q = searchQuery.value.toLowerCase()
    result = result.filter(
      (entry: JournalEntry) =>
        entry.symbol.toLowerCase().includes(q) ||
        (entry.notes ?? '').toLowerCase().includes(q)
    )
  }
  return result
})

const filterTabs = [
  { key: 'all', label: 'All' },
  { key: 'pre_trade', label: 'Pre-Trade' },
  { key: 'post_trade', label: 'Post-Trade' },
  { key: 'observation', label: 'Observations' },
] as const

// ---- Data loading ----
async function loadData(): Promise<void> {
  const params: Record<string, string> = {}
  if (activeFilter.value !== 'all') {
    params.entry_type = activeFilter.value
  }
  await store.loadEntries(params)
}

async function onFilterChange(key: typeof activeFilter.value): Promise<void> {
  activeFilter.value = key
  await loadData()
}

onMounted(loadData)

// ---- Entry type badge helpers ----
function entryTypeBadgeClass(type: string): string {
  switch (type) {
    case 'pre_trade':
      return 'bg-blue-900 text-blue-300'
    case 'post_trade':
      return 'bg-green-900 text-green-300'
    default:
      return 'bg-gray-800 text-gray-400'
  }
}

function entryTypeLabel(type: string): string {
  switch (type) {
    case 'pre_trade':
      return 'Pre-Trade'
    case 'post_trade':
      return 'Post-Trade'
    default:
      return 'Observation'
  }
}

function emotionalEmoji(state: string | null): string {
  const map: Record<string, string> = {
    disciplined: '🎯',
    confident: '💪',
    neutral: '😐',
    uncertain: '🤔',
    fomo: '😰',
  }
  return map[state ?? 'neutral'] ?? '😐'
}

function formatDate(iso: string): string {
  return new Date(iso).toLocaleDateString(undefined, { dateStyle: 'medium' })
}

function notePreview(notes: string | null): string {
  if (!notes) return ''
  return notes.length > 100 ? notes.slice(0, 100) + '…' : notes
}

// ---- Modal handlers ----
function openCreate(): void {
  selectedEntry.value = null
  modalMode.value = 'create'
}

function openView(entry: JournalEntry): void {
  selectedEntry.value = entry
  modalMode.value = 'view'
}

function openEdit(): void {
  modalMode.value = 'edit'
}

function closeModal(): void {
  modalMode.value = 'none'
  selectedEntry.value = null
}

async function handleSave(
  payload: JournalEntryCreate | JournalEntryUpdate
): Promise<void> {
  if (modalMode.value === 'create') {
    const result = await store.createEntry(payload as JournalEntryCreate)
    if (result) closeModal()
  } else if (modalMode.value === 'edit' && selectedEntry.value) {
    const result = await store.updateEntry(
      selectedEntry.value.id,
      payload as JournalEntryUpdate
    )
    if (result) {
      selectedEntry.value = result
      modalMode.value = 'view'
    }
  }
}

async function handleDelete(): Promise<void> {
  if (!selectedEntry.value) return
  const ok = await store.deleteEntry(selectedEntry.value.id)
  if (ok) closeModal()
}
</script>

<template>
  <div class="journal-view">
    <!-- Page header -->
    <div class="flex items-center justify-between mb-6">
      <div>
        <h1 class="text-xl font-semibold text-gray-100">Trade Journal</h1>
        <p class="text-sm text-gray-500 mt-0.5">
          Retrospective analysis to build Wyckoff skill
        </p>
      </div>
      <button
        class="px-4 py-2 bg-blue-600 hover:bg-blue-500 text-white text-sm font-medium rounded-md transition-colors"
        data-testid="new-entry-btn"
        @click="openCreate"
      >
        + New Entry
      </button>
    </div>

    <!-- Search + Filter bar -->
    <div class="flex flex-col sm:flex-row gap-3 mb-5">
      <input
        v-model="searchQuery"
        type="text"
        placeholder="Search by symbol or notes..."
        class="flex-1 bg-[#0d1322] border border-[#1e2d4a] rounded-md px-3 py-2 text-sm text-gray-100 placeholder-gray-600 focus:outline-none focus:border-blue-500"
        data-testid="journal-search"
      />

      <!-- Filter tabs -->
      <div
        class="flex gap-1 bg-[#0a0e1a] border border-[#1e2d4a] rounded-md p-1"
      >
        <button
          v-for="tab in filterTabs"
          :key="tab.key"
          class="px-3 py-1 text-xs rounded transition-colors"
          :class="
            activeFilter === tab.key
              ? 'bg-blue-600 text-white'
              : 'text-gray-400 hover:text-gray-200'
          "
          @click="onFilterChange(tab.key)"
        >
          {{ tab.label }}
        </button>
      </div>
    </div>

    <!-- Error state -->
    <div
      v-if="store.error"
      class="mb-4 px-4 py-3 bg-red-900/30 border border-red-800 rounded-md text-sm text-red-300"
    >
      {{ store.error }}
    </div>

    <!-- Loading skeleton -->
    <div v-if="store.isLoading" class="space-y-3">
      <div
        v-for="i in 4"
        :key="i"
        class="h-20 bg-[#0d1322] border border-[#1e2d4a] rounded-lg animate-pulse"
      ></div>
    </div>

    <!-- Empty state -->
    <div
      v-else-if="filteredEntries.length === 0"
      class="text-center py-16 text-gray-600"
    >
      <div class="text-4xl mb-3">📓</div>
      <p class="text-sm">No journal entries yet.</p>
      <p class="text-xs mt-1">Start by recording your pre-trade reasoning.</p>
      <button
        class="mt-4 px-4 py-2 bg-blue-600 hover:bg-blue-500 text-white text-sm rounded-md transition-colors"
        @click="openCreate"
      >
        Create First Entry
      </button>
    </div>

    <!-- Entry list -->
    <div v-else class="space-y-3">
      <div
        v-for="entry in filteredEntries"
        :key="entry.id"
        class="bg-[#0d1322] border border-[#1e2d4a] rounded-lg p-4 cursor-pointer hover:border-blue-700 transition-colors group"
        @click="openView(entry)"
      >
        <div class="flex items-start justify-between gap-3">
          <!-- Left: symbol + type + date -->
          <div class="flex items-center gap-2 flex-shrink-0">
            <span class="font-semibold text-gray-100 text-sm">{{
              entry.symbol
            }}</span>
            <span
              class="text-xs px-1.5 py-0.5 rounded-full"
              :class="entryTypeBadgeClass(entry.entry_type)"
            >
              {{ entryTypeLabel(entry.entry_type) }}
            </span>
            <span class="text-xs" :title="entry.emotional_state ?? 'neutral'">
              {{ emotionalEmoji(entry.emotional_state) }}
            </span>
          </div>

          <!-- Right: date + checklist score -->
          <div class="flex items-center gap-3 flex-shrink-0">
            <span
              class="text-xs font-medium px-1.5 py-0.5 rounded"
              :class="
                entry.checklist_score === 4
                  ? 'bg-green-900 text-green-300'
                  : entry.checklist_score >= 2
                    ? 'bg-yellow-900 text-yellow-300'
                    : 'bg-gray-800 text-gray-500'
              "
            >
              {{ entry.checklist_score }}/4
            </span>
            <span class="text-xs text-gray-600">{{
              formatDate(entry.created_at)
            }}</span>
          </div>
        </div>

        <!-- Note preview -->
        <p v-if="entry.notes" class="mt-2 text-xs text-gray-500 line-clamp-2">
          {{ notePreview(entry.notes) }}
        </p>
      </div>
    </div>

    <!-- Modal overlay -->
    <Teleport to="body">
      <div
        v-if="modalMode !== 'none'"
        class="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4"
        @click.self="closeModal"
      >
        <div
          class="w-full max-w-lg bg-[#0f1729] border border-[#1e2d4a] rounded-xl shadow-2xl overflow-hidden"
        >
          <!-- Modal header -->
          <div
            class="flex items-center justify-between px-5 py-4 border-b border-[#1e2d4a]"
          >
            <h2 class="text-sm font-semibold text-gray-200">
              {{
                modalMode === 'create'
                  ? 'New Journal Entry'
                  : modalMode === 'edit'
                    ? 'Edit Entry'
                    : 'Journal Entry'
              }}
            </h2>
            <button
              class="text-gray-500 hover:text-gray-300 transition-colors"
              @click="closeModal"
            >
              <svg class="w-4 h-4" viewBox="0 0 16 16" fill="currentColor">
                <path
                  d="M3.72 3.72a.75.75 0 0 1 1.06 0L8 6.94l3.22-3.22a.749.749 0 0 1 1.275.326.749.749 0 0 1-.215.734L9.06 8l3.22 3.22a.749.749 0 0 1-.326 1.275.749.749 0 0 1-.734-.215L8 9.06l-3.22 3.22a.751.751 0 0 1-1.042-.018.751.751 0 0 1-.018-1.042L6.94 8 3.72 4.78a.75.75 0 0 1 0-1.06Z"
                />
              </svg>
            </button>
          </div>

          <!-- Modal body -->
          <div class="px-5 py-5 max-h-[75vh] overflow-y-auto">
            <!-- View mode -->
            <JournalEntryDetail
              v-if="modalMode === 'view' && selectedEntry"
              :entry="selectedEntry"
              @edit="openEdit"
              @delete="handleDelete"
              @close="closeModal"
            />

            <!-- Create / Edit form -->
            <JournalEntryForm
              v-if="modalMode === 'create' || modalMode === 'edit'"
              :entry="modalMode === 'edit' ? selectedEntry : null"
              :saving="store.isSaving"
              @save="handleSave"
              @cancel="closeModal"
            />
          </div>
        </div>
      </div>
    </Teleport>
  </div>
</template>

<style scoped>
.journal-view {
  @apply min-h-screen;
}

.line-clamp-2 {
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
</style>
