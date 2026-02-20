<script setup lang="ts">
/**
 * JournalEntryDetail - View a single trade journal entry
 *
 * Shows full notes, Wyckoff checklist progress, emotional state,
 * and linked campaign summary if campaign_id is present.
 *
 * Feature P2-8 (Trade Journal)
 */
import { computed } from 'vue'
import type { JournalEntry } from '@/services/journalService'

const props = defineProps<{
  entry: JournalEntry
}>()

const emit = defineEmits<{
  edit: []
  delete: []
  close: []
}>()

const entryTypeLabel = computed(() => {
  switch (props.entry.entry_type) {
    case 'pre_trade':
      return 'Pre-Trade'
    case 'post_trade':
      return 'Post-Trade'
    default:
      return 'Observation'
  }
})

const entryTypeBadgeClass = computed(() => {
  switch (props.entry.entry_type) {
    case 'pre_trade':
      return 'bg-blue-900 text-blue-300'
    case 'post_trade':
      return 'bg-green-900 text-green-300'
    default:
      return 'bg-gray-800 text-gray-400'
  }
})

const emotionalEmoji = computed(() => {
  const map: Record<string, string> = {
    disciplined: '🎯',
    confident: '💪',
    neutral: '😐',
    uncertain: '🤔',
    fomo: '😰',
  }
  return map[props.entry.emotional_state ?? 'neutral'] ?? '😐'
})

const checklistItems = computed(() => {
  const cl = props.entry.wyckoff_checklist
  return [
    {
      key: 'phase_confirmed',
      label: 'Phase confirmed',
      checked: cl?.phase_confirmed ?? false,
    },
    {
      key: 'volume_confirmed',
      label: 'Volume confirmed',
      checked: cl?.volume_confirmed ?? false,
    },
    {
      key: 'creek_identified',
      label: 'Creek/Ice identified',
      checked: cl?.creek_identified ?? false,
    },
    {
      key: 'pattern_confirmed',
      label: 'Pattern confirmed',
      checked: cl?.pattern_confirmed ?? false,
    },
  ]
})

const checklistScore = computed(() => props.entry.checklist_score)

function formatDate(iso: string): string {
  return new Date(iso).toLocaleString(undefined, {
    dateStyle: 'medium',
    timeStyle: 'short',
  })
}
</script>

<template>
  <div class="space-y-5">
    <!-- Header -->
    <div class="flex items-start justify-between">
      <div class="flex items-center gap-3">
        <span class="text-lg font-semibold text-gray-100">{{
          entry.symbol
        }}</span>
        <span
          class="text-xs px-2 py-0.5 rounded-full font-medium"
          :class="entryTypeBadgeClass"
        >
          {{ entryTypeLabel }}
        </span>
        <span class="text-sm" :title="entry.emotional_state ?? 'neutral'">
          {{ emotionalEmoji }}
          <span class="text-xs text-gray-500 ml-1 capitalize">{{
            entry.emotional_state ?? 'neutral'
          }}</span>
        </span>
      </div>
      <div class="flex items-center gap-2">
        <button
          class="px-3 py-1.5 text-xs text-blue-400 border border-blue-800 rounded hover:bg-blue-900/30 transition-colors"
          @click="emit('edit')"
        >
          Edit
        </button>
        <button
          class="px-3 py-1.5 text-xs text-red-400 border border-red-900 rounded hover:bg-red-900/30 transition-colors"
          @click="emit('delete')"
        >
          Delete
        </button>
      </div>
    </div>

    <!-- Timestamp -->
    <p class="text-xs text-gray-500">
      Created {{ formatDate(entry.created_at) }}
      <span v-if="entry.updated_at !== entry.created_at">
        · Updated {{ formatDate(entry.updated_at) }}
      </span>
    </p>

    <!-- Campaign link -->
    <div
      v-if="entry.campaign_id"
      class="flex items-center gap-2 bg-[#0a0e1a] border border-[#1e2d4a] rounded-md px-3 py-2"
    >
      <span class="text-xs text-gray-500">Linked campaign:</span>
      <code class="text-xs text-blue-400 font-mono">{{
        entry.campaign_id
      }}</code>
    </div>

    <!-- Notes -->
    <div
      v-if="entry.notes"
      class="bg-[#0a0e1a] border border-[#1e2d4a] rounded-lg p-4"
    >
      <h3 class="text-xs text-gray-400 uppercase tracking-wider mb-2">Notes</h3>
      <p class="text-sm text-gray-200 whitespace-pre-wrap leading-relaxed">
        {{ entry.notes }}
      </p>
    </div>
    <div v-else class="text-sm text-gray-600 italic">No notes recorded.</div>

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
        >
          {{ checklistScore }}/4 criteria met
        </span>
      </div>

      <!-- Progress bar -->
      <div class="h-1.5 bg-gray-800 rounded-full mb-4 overflow-hidden">
        <div
          class="h-full rounded-full transition-all"
          :class="
            checklistScore === 4
              ? 'bg-green-500'
              : checklistScore >= 2
                ? 'bg-yellow-500'
                : 'bg-gray-600'
          "
          :style="{ width: `${(checklistScore / 4) * 100}%` }"
        ></div>
      </div>

      <ul class="space-y-2">
        <li
          v-for="item in checklistItems"
          :key="item.key"
          class="flex items-center gap-2 text-sm"
          :class="item.checked ? 'text-gray-200' : 'text-gray-600'"
        >
          <span class="w-4 h-4 flex-shrink-0">
            <svg
              v-if="item.checked"
              class="text-green-400"
              viewBox="0 0 16 16"
              fill="currentColor"
            >
              <path
                fill-rule="evenodd"
                d="M12.416 3.376a.75.75 0 0 1 .208 1.04l-5 7.5a.75.75 0 0 1-1.154.114l-3-3a.75.75 0 0 1 1.06-1.06l2.353 2.353 4.493-6.74a.75.75 0 0 1 1.04-.207Z"
                clip-rule="evenodd"
              />
            </svg>
            <svg
              v-else
              class="text-gray-700"
              viewBox="0 0 16 16"
              fill="currentColor"
            >
              <path
                d="M8 15A7 7 0 1 1 8 1a7 7 0 0 1 0 14zm0 1A8 8 0 1 0 8 0a8 8 0 0 0 0 16z"
              />
            </svg>
          </span>
          {{ item.label }}
        </li>
      </ul>
    </div>

    <!-- Close button -->
    <div class="flex justify-end pt-2">
      <button
        class="px-4 py-2 text-sm text-gray-400 hover:text-gray-200 transition-colors"
        @click="emit('close')"
      >
        Close
      </button>
    </div>
  </div>
</template>
