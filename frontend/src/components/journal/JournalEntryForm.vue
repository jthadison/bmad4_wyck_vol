<script setup lang="ts">
/**
 * JournalEntryForm - Create or edit a trade journal entry
 *
 * Includes symbol, entry type, notes textarea, emotional state pills,
 * and the 4-point Wyckoff criteria checklist.
 *
 * Feature P2-8 (Trade Journal)
 */
import { ref, computed, watch } from 'vue'
import type {
  JournalEntry,
  JournalEntryCreate,
  JournalEntryUpdate,
  WyckoffChecklist,
} from '@/services/journalService'

const props = defineProps<{
  /** Existing entry for editing; null/undefined for new entry */
  entry?: JournalEntry | null
  /** Optional pre-filled campaign ID */
  campaignId?: string | null
  /** Whether the save operation is in progress */
  saving?: boolean
}>()

const emit = defineEmits<{
  save: [payload: JournalEntryCreate | JournalEntryUpdate]
  cancel: []
}>()

// ---- Form State ----
const symbol = ref(props.entry?.symbol ?? '')
const entryType = ref<'pre_trade' | 'post_trade' | 'observation'>(
  props.entry?.entry_type ?? 'observation'
)
const notes = ref(props.entry?.notes ?? '')
const emotionalState = ref<string>(props.entry?.emotional_state ?? 'neutral')

const checklist = ref<WyckoffChecklist>({
  phase_confirmed: props.entry?.wyckoff_checklist?.phase_confirmed ?? false,
  volume_confirmed: props.entry?.wyckoff_checklist?.volume_confirmed ?? false,
  creek_identified: props.entry?.wyckoff_checklist?.creek_identified ?? false,
  pattern_confirmed: props.entry?.wyckoff_checklist?.pattern_confirmed ?? false,
})

// Sync when entry prop changes (edit mode)
watch(
  () => props.entry,
  (updatedEntry: JournalEntry | null | undefined) => {
    if (updatedEntry) {
      symbol.value = updatedEntry.symbol
      entryType.value = updatedEntry.entry_type
      notes.value = updatedEntry.notes ?? ''
      emotionalState.value = updatedEntry.emotional_state ?? 'neutral'
      checklist.value = {
        phase_confirmed:
          updatedEntry.wyckoff_checklist?.phase_confirmed ?? false,
        volume_confirmed:
          updatedEntry.wyckoff_checklist?.volume_confirmed ?? false,
        creek_identified:
          updatedEntry.wyckoff_checklist?.creek_identified ?? false,
        pattern_confirmed:
          updatedEntry.wyckoff_checklist?.pattern_confirmed ?? false,
      }
    }
  }
)

// ---- Computed ----
const checklistScore = computed(
  () =>
    [
      checklist.value.phase_confirmed,
      checklist.value.volume_confirmed,
      checklist.value.creek_identified,
      checklist.value.pattern_confirmed,
    ].filter(Boolean).length
)

const isEditMode = computed(() => !!props.entry)

// ---- Emotional state options ----
const emotionalOptions = [
  { value: 'disciplined', label: 'Disciplined', emoji: '🎯' },
  { value: 'confident', label: 'Confident', emoji: '💪' },
  { value: 'neutral', label: 'Neutral', emoji: '😐' },
  { value: 'uncertain', label: 'Uncertain', emoji: '🤔' },
  { value: 'fomo', label: 'FOMO', emoji: '😰' },
]

// ---- Actions ----
function handleSubmit(): void {
  if (!symbol.value.trim()) return

  const payload: JournalEntryCreate | JournalEntryUpdate = {
    symbol: symbol.value.trim().toUpperCase(),
    entry_type: entryType.value,
    notes: notes.value.trim() || null,
    emotional_state:
      emotionalState.value as JournalEntryCreate['emotional_state'],
    wyckoff_checklist: { ...checklist.value },
  }

  if (!isEditMode.value) {
    ;(payload as JournalEntryCreate).campaign_id = props.campaignId ?? null
  }

  emit('save', payload)
}
</script>

<template>
  <form class="space-y-5" @submit.prevent="handleSubmit">
    <!-- Symbol + Entry Type row -->
    <div class="flex gap-4">
      <div class="flex-1">
        <label class="block text-xs text-gray-400 mb-1 uppercase tracking-wider"
          >Symbol</label
        >
        <input
          v-model="symbol"
          type="text"
          placeholder="e.g. AAPL"
          maxlength="20"
          required
          class="w-full bg-[#0d1322] border border-[#1e2d4a] rounded-md px-3 py-2 text-sm text-gray-100 placeholder-gray-600 focus:outline-none focus:border-blue-500"
          data-testid="journal-symbol"
        />
      </div>

      <div>
        <label class="block text-xs text-gray-400 mb-1 uppercase tracking-wider"
          >Type</label
        >
        <select
          v-model="entryType"
          class="bg-[#0d1322] border border-[#1e2d4a] rounded-md px-3 py-2 text-sm text-gray-100 focus:outline-none focus:border-blue-500"
          data-testid="journal-entry-type"
        >
          <option value="pre_trade">Pre-Trade</option>
          <option value="post_trade">Post-Trade</option>
          <option value="observation">Observation</option>
        </select>
      </div>
    </div>

    <!-- Notes -->
    <div>
      <label class="block text-xs text-gray-400 mb-1 uppercase tracking-wider"
        >Notes</label
      >
      <textarea
        v-model="notes"
        rows="5"
        placeholder="Describe your Wyckoff analysis, reasoning, or observations..."
        class="w-full bg-[#0d1322] border border-[#1e2d4a] rounded-md px-3 py-2 text-sm text-gray-100 placeholder-gray-600 focus:outline-none focus:border-blue-500 resize-y"
        data-testid="journal-notes"
      ></textarea>
    </div>

    <!-- Emotional State -->
    <div>
      <label class="block text-xs text-gray-400 mb-2 uppercase tracking-wider">
        Emotional State
      </label>
      <div class="flex flex-wrap gap-2" data-testid="journal-emotional-state">
        <button
          v-for="opt in emotionalOptions"
          :key="opt.value"
          type="button"
          class="px-3 py-1.5 rounded-full text-sm border transition-colors"
          :class="
            emotionalState === opt.value
              ? 'bg-blue-600 border-blue-500 text-white'
              : 'bg-[#0d1322] border-[#1e2d4a] text-gray-400 hover:border-blue-600 hover:text-gray-200'
          "
          @click="emotionalState = opt.value"
        >
          {{ opt.emoji }} {{ opt.label }}
        </button>
      </div>
    </div>

    <!-- Wyckoff Checklist -->
    <div class="bg-[#0a0e1a] border border-[#1e2d4a] rounded-lg p-4">
      <div class="flex items-center justify-between mb-3">
        <h3 class="text-xs text-gray-400 uppercase tracking-wider">
          Wyckoff Criteria
        </h3>
        <span
          class="text-xs font-semibold px-2 py-0.5 rounded"
          :class="
            checklistScore === 4
              ? 'bg-green-900 text-green-300'
              : checklistScore >= 2
                ? 'bg-yellow-900 text-yellow-300'
                : 'bg-gray-800 text-gray-400'
          "
          data-testid="checklist-score"
        >
          {{ checklistScore }}/4 met
        </span>
      </div>

      <div class="space-y-2.5">
        <label
          class="flex items-start gap-3 cursor-pointer group"
          data-testid="check-phase"
        >
          <input
            v-model="checklist.phase_confirmed"
            type="checkbox"
            class="mt-0.5 h-4 w-4 rounded border-gray-600 bg-gray-800 text-blue-500 focus:ring-blue-500"
          />
          <div>
            <span class="text-sm text-gray-200 group-hover:text-white"
              >Phase confirmed</span
            >
            <p class="text-xs text-gray-500">
              Wyckoff phase (A/B/C/D/E) clearly identified before entry
            </p>
          </div>
        </label>

        <label
          class="flex items-start gap-3 cursor-pointer group"
          data-testid="check-volume"
        >
          <input
            v-model="checklist.volume_confirmed"
            type="checkbox"
            class="mt-0.5 h-4 w-4 rounded border-gray-600 bg-gray-800 text-blue-500 focus:ring-blue-500"
          />
          <div>
            <span class="text-sm text-gray-200 group-hover:text-white"
              >Volume confirmed</span
            >
            <p class="text-xs text-gray-500">
              Low vol Spring or high vol SOS verified
            </p>
          </div>
        </label>

        <label
          class="flex items-start gap-3 cursor-pointer group"
          data-testid="check-creek"
        >
          <input
            v-model="checklist.creek_identified"
            type="checkbox"
            class="mt-0.5 h-4 w-4 rounded border-gray-600 bg-gray-800 text-blue-500 focus:ring-blue-500"
          />
          <div>
            <span class="text-sm text-gray-200 group-hover:text-white"
              >Creek/Ice identified</span
            >
            <p class="text-xs text-gray-500">
              Key resistance/support level mapped
            </p>
          </div>
        </label>

        <label
          class="flex items-start gap-3 cursor-pointer group"
          data-testid="check-pattern"
        >
          <input
            v-model="checklist.pattern_confirmed"
            type="checkbox"
            class="mt-0.5 h-4 w-4 rounded border-gray-600 bg-gray-800 text-blue-500 focus:ring-blue-500"
          />
          <div>
            <span class="text-sm text-gray-200 group-hover:text-white"
              >Pattern confirmed</span
            >
            <p class="text-xs text-gray-500">
              Spring/SOS/LPS/UTAD pattern clearly formed
            </p>
          </div>
        </label>
      </div>
    </div>

    <!-- Actions -->
    <div class="flex justify-end gap-3 pt-2">
      <button
        type="button"
        class="px-4 py-2 text-sm text-gray-400 hover:text-gray-200 transition-colors"
        @click="emit('cancel')"
      >
        Cancel
      </button>
      <button
        type="submit"
        :disabled="saving || !symbol.trim()"
        class="px-5 py-2 text-sm font-medium rounded-md bg-blue-600 text-white hover:bg-blue-500 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
        data-testid="journal-save-btn"
      >
        {{ saving ? 'Saving...' : isEditMode ? 'Update Entry' : 'Save Entry' }}
      </button>
    </div>
  </form>
</template>
