<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useSignalStore } from '@/stores/signalStore'
import TabView from 'primevue/tabview'
import TabPanel from 'primevue/tabpanel'
import Badge from 'primevue/badge'
import Dropdown from 'primevue/dropdown'
import MultiSelect from 'primevue/multiselect'
import InputText from 'primevue/inputtext'
import Calendar from 'primevue/calendar'
import Button from 'primevue/button'
import ProgressSpinner from 'primevue/progressspinner'
import SignalCard from './SignalCard.vue'

const signalStore = useSignalStore()

// Tab state
const activeTabIndex = ref(0)

// Sorting state
const sortBy = ref('timestamp_desc')
const sortOptions = [
  { label: 'Most Recent', value: 'timestamp_desc' },
  { label: 'Oldest First', value: 'timestamp_asc' },
  { label: 'Highest Confidence', value: 'confidence_desc' },
  { label: 'Highest R-Multiple', value: 'r_multiple_desc' },
]

// Filtering state
const selectedPatterns = ref<string[]>([])
const patternOptions = [
  { label: 'SPRING', value: 'SPRING' },
  { label: 'SOS', value: 'SOS' },
  { label: 'LPS', value: 'LPS' },
  { label: 'UTAD', value: 'UTAD' },
]
const symbolFilter = ref('')
const dateRange = ref<Date[] | null>(null)

// Infinite scroll state
const isLoadingMore = ref(false)

// Tab data
const executedSignals = computed(() => signalStore.executedSignals)
const pendingSignals = computed(() => signalStore.pendingSignals)
const rejectedSignals = computed(() => signalStore.rejectedSignals)
const allSignals = computed(() => signalStore.signals)

// Tab counts
const executedCount = computed(() => signalStore.executedCount)
const pendingCount = computed(() => signalStore.pendingCount)
const rejectedCount = computed(() => signalStore.rejectedCount)
const allCount = computed(() => allSignals.value.length)

// Active tab signals
const activeTabSignals = computed(() => {
  switch (activeTabIndex.value) {
    case 0:
      return executedSignals.value
    case 1:
      return pendingSignals.value
    case 2:
      return rejectedSignals.value
    case 3:
      return allSignals.value
    default:
      return []
  }
})

// Check if filters are active
const hasFilters = computed(
  () =>
    selectedPatterns.value.length > 0 ||
    symbolFilter.value !== '' ||
    dateRange.value !== null
)

// Filter signals
const filteredSignals = computed(() => {
  let filtered = [...activeTabSignals.value]

  // Pattern type filter
  if (selectedPatterns.value.length > 0) {
    filtered = filtered.filter((s) =>
      selectedPatterns.value.includes(s.pattern_type)
    )
  }

  // Symbol filter (case-insensitive)
  if (symbolFilter.value) {
    const searchTerm = symbolFilter.value.toUpperCase()
    filtered = filtered.filter((s) =>
      s.symbol.toUpperCase().includes(searchTerm)
    )
  }

  // Date range filter
  if (dateRange.value && dateRange.value.length === 2) {
    const [startDate, endDate] = dateRange.value
    filtered = filtered.filter((s) => {
      const signalDate = new Date(s.timestamp)
      return signalDate >= startDate && signalDate <= endDate
    })
  }

  return filtered
})

// Sort signals
const sortedSignals = computed(() => {
  const signals = [...filteredSignals.value]

  switch (sortBy.value) {
    case 'timestamp_desc':
      return signals.sort(
        (a, b) =>
          new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime()
      )
    case 'timestamp_asc':
      return signals.sort(
        (a, b) =>
          new Date(a.timestamp).getTime() - new Date(b.timestamp).getTime()
      )
    case 'confidence_desc':
      return signals.sort((a, b) => b.confidence_score - a.confidence_score)
    case 'r_multiple_desc':
      return signals.sort((a, b) => {
        const aR = parseFloat(a.r_multiple)
        const bR = parseFloat(b.r_multiple)
        return bR - aR
      })
    default:
      return signals
  }
})

// Final displayed signals
const displayedSignals = computed(() => sortedSignals.value)

// Clear all filters
function clearFilters() {
  selectedPatterns.value = []
  symbolFilter.value = ''
  dateRange.value = null
}

// Retry fetch on error
async function retryFetch() {
  await signalStore.fetchSignals()
}

// Infinite scroll - load more signals
async function loadMore() {
  if (!signalStore.loading && signalStore.hasMore && !isLoadingMore.value) {
    isLoadingMore.value = true
    await signalStore.fetchMoreSignals()
    isLoadingMore.value = false
  }
}

// Handle scroll event for infinite scroll
function handleScroll(event: Event) {
  const target = event.target as HTMLElement
  const scrollBottom =
    target.scrollHeight - target.scrollTop - target.clientHeight

  // Load more when within 200px of bottom
  if (scrollBottom < 200) {
    loadMore()
  }
}

// Keyboard navigation for signal cards
function handleCardKeyDown(event: KeyboardEvent) {
  if (event.key === 'Enter' || event.key === ' ') {
    event.preventDefault()
    // Future: Expand signal details (Story 10.5)
  }
}

// Initialize
onMounted(async () => {
  await signalStore.fetchSignals()
})

// Expose internal state for testing
defineExpose({
  selectedPatterns,
  symbolFilter,
  dateRange,
  sortBy,
  displayedSignals,
  hasFilters,
  clearFilters,
  signalStore,
})
</script>

<template>
  <div class="live-signals-dashboard">
    <!-- Header -->
    <div class="flex items-center justify-between mb-6">
      <h2 class="text-2xl font-bold text-white">Live Signals Dashboard</h2>

      <!-- Sort dropdown -->
      <Dropdown
        v-model="sortBy"
        :options="sortOptions"
        option-label="label"
        option-value="value"
        placeholder="Sort by"
        class="w-56"
      />
    </div>

    <!-- Filter bar -->
    <div class="flex flex-wrap gap-4 mb-6 p-4 bg-gray-800 rounded-lg">
      <MultiSelect
        v-model="selectedPatterns"
        :options="patternOptions"
        option-label="label"
        option-value="value"
        placeholder="Filter by pattern"
        class="w-64"
        display="chip"
      />

      <InputText
        v-model="symbolFilter"
        placeholder="Search symbol (e.g., AAPL)"
        class="w-48"
      />

      <Calendar
        v-model="dateRange"
        selection-mode="range"
        :show-icon="true"
        placeholder="Select date range"
        date-format="yy-mm-dd"
        class="w-64"
      />

      <Button
        v-if="hasFilters"
        label="Clear Filters"
        severity="secondary"
        outlined
        @click="clearFilters"
      />
    </div>

    <!-- Error state -->
    <div
      v-if="signalStore.error"
      class="bg-red-900 border border-red-700 rounded-lg p-4 mb-6"
    >
      <p class="text-white font-bold">Failed to load signals</p>
      <p class="text-red-300 text-sm">{{ signalStore.error }}</p>
      <Button
        label="Retry"
        severity="danger"
        class="mt-2"
        @click="retryFetch"
      />
    </div>

    <!-- Tabs -->
    <TabView
      v-model:active-index="activeTabIndex"
      role="tablist"
      class="signals-tabs"
    >
      <!-- Executed Tab -->
      <TabPanel role="tab" aria-label="Executed signals tab">
        <template #header>
          <span class="mr-2">Executed</span>
          <Badge :value="executedCount" severity="success" />
        </template>

        <div class="signals-list-container" @scroll="handleScroll">
          <!-- Loading state (initial) -->
          <div
            v-if="signalStore.loading && executedSignals.length === 0"
            class="flex flex-col justify-center items-center py-12"
          >
            <ProgressSpinner />
            <span class="ml-4 text-gray-400 mt-4">Loading signals...</span>
          </div>

          <!-- Empty state -->
          <div
            v-else-if="
              !signalStore.loading &&
              displayedSignals.length === 0 &&
              !hasFilters
            "
            class="text-center py-12"
          >
            <i class="pi pi-inbox text-6xl text-gray-600 mb-4"></i>
            <p class="text-xl text-gray-400">No executed signals yet</p>
            <p class="text-sm text-gray-500 mt-2">
              Executed signals will appear here once trades are filled
            </p>
          </div>

          <!-- Empty state with filters -->
          <div
            v-else-if="
              !signalStore.loading &&
              displayedSignals.length === 0 &&
              hasFilters
            "
            class="text-center py-12"
          >
            <p class="text-xl text-gray-400">No signals match your filters</p>
            <Button label="Clear Filters" class="mt-4" @click="clearFilters" />
          </div>

          <!-- Signal cards -->
          <div v-else class="signals-list space-y-4">
            <SignalCard
              v-for="signal in displayedSignals"
              :key="signal.id"
              v-memo="[signal.id, signal.status, signal.timestamp]"
              :signal="signal"
              @keydown="handleCardKeyDown"
            />

            <!-- Loading more indicator -->
            <div
              v-if="isLoadingMore"
              class="flex justify-center items-center py-4"
            >
              <ProgressSpinner style="width: 30px; height: 30px" />
              <span class="ml-2 text-gray-400">Loading more...</span>
            </div>

            <!-- No more signals -->
            <div
              v-if="
                !signalStore.hasMore &&
                displayedSignals.length > 0 &&
                !isLoadingMore
              "
              class="text-center py-4 text-gray-500"
            >
              No more signals
            </div>
          </div>
        </div>
      </TabPanel>

      <!-- Pending Review Tab -->
      <TabPanel role="tab" aria-label="Pending signals tab">
        <template #header>
          <span class="mr-2">Pending Review</span>
          <Badge :value="pendingCount" severity="warning" />
        </template>

        <div class="signals-list-container" @scroll="handleScroll">
          <!-- Loading state (initial) -->
          <div
            v-if="signalStore.loading && pendingSignals.length === 0"
            class="flex flex-col justify-center items-center py-12"
          >
            <ProgressSpinner />
            <span class="ml-4 text-gray-400 mt-4">Loading signals...</span>
          </div>

          <!-- Empty state -->
          <div
            v-else-if="
              !signalStore.loading &&
              displayedSignals.length === 0 &&
              !hasFilters
            "
            class="text-center py-12"
          >
            <i class="pi pi-inbox text-6xl text-gray-600 mb-4"></i>
            <p class="text-xl text-gray-400">No pending signals</p>
            <p class="text-sm text-gray-500 mt-2">
              Pending signals will appear here when patterns are detected
            </p>
          </div>

          <!-- Empty state with filters -->
          <div
            v-else-if="
              !signalStore.loading &&
              displayedSignals.length === 0 &&
              hasFilters
            "
            class="text-center py-12"
          >
            <p class="text-xl text-gray-400">No signals match your filters</p>
            <Button label="Clear Filters" class="mt-4" @click="clearFilters" />
          </div>

          <!-- Signal cards -->
          <div v-else class="signals-list space-y-4">
            <SignalCard
              v-for="signal in displayedSignals"
              :key="signal.id"
              v-memo="[signal.id, signal.status, signal.timestamp]"
              :signal="signal"
              @keydown="handleCardKeyDown"
            />

            <!-- Loading more indicator -->
            <div
              v-if="isLoadingMore"
              class="flex justify-center items-center py-4"
            >
              <ProgressSpinner style="width: 30px; height: 30px" />
              <span class="ml-2 text-gray-400">Loading more...</span>
            </div>

            <!-- No more signals -->
            <div
              v-if="
                !signalStore.hasMore &&
                displayedSignals.length > 0 &&
                !isLoadingMore
              "
              class="text-center py-4 text-gray-500"
            >
              No more signals
            </div>
          </div>
        </div>
      </TabPanel>

      <!-- Rejected Tab -->
      <TabPanel role="tab" aria-label="Rejected signals tab">
        <template #header>
          <span class="mr-2">Rejected</span>
          <Badge :value="rejectedCount" severity="danger" />
        </template>

        <div class="signals-list-container" @scroll="handleScroll">
          <!-- Loading state (initial) -->
          <div
            v-if="signalStore.loading && rejectedSignals.length === 0"
            class="flex flex-col justify-center items-center py-12"
          >
            <ProgressSpinner />
            <span class="ml-4 text-gray-400 mt-4">Loading signals...</span>
          </div>

          <!-- Empty state -->
          <div
            v-else-if="
              !signalStore.loading &&
              displayedSignals.length === 0 &&
              !hasFilters
            "
            class="text-center py-12"
          >
            <i class="pi pi-inbox text-6xl text-gray-600 mb-4"></i>
            <p class="text-xl text-gray-400">No rejected signals</p>
            <p class="text-sm text-gray-500 mt-2">
              Rejected signals will appear here after validation fails
            </p>
          </div>

          <!-- Empty state with filters -->
          <div
            v-else-if="
              !signalStore.loading &&
              displayedSignals.length === 0 &&
              hasFilters
            "
            class="text-center py-12"
          >
            <p class="text-xl text-gray-400">No signals match your filters</p>
            <Button label="Clear Filters" class="mt-4" @click="clearFilters" />
          </div>

          <!-- Signal cards -->
          <div v-else class="signals-list space-y-4">
            <SignalCard
              v-for="signal in displayedSignals"
              :key="signal.id"
              v-memo="[signal.id, signal.status, signal.timestamp]"
              :signal="signal"
              @keydown="handleCardKeyDown"
            />

            <!-- Loading more indicator -->
            <div
              v-if="isLoadingMore"
              class="flex justify-center items-center py-4"
            >
              <ProgressSpinner style="width: 30px; height: 30px" />
              <span class="ml-2 text-gray-400">Loading more...</span>
            </div>

            <!-- No more signals -->
            <div
              v-if="
                !signalStore.hasMore &&
                displayedSignals.length > 0 &&
                !isLoadingMore
              "
              class="text-center py-4 text-gray-500"
            >
              No more signals
            </div>
          </div>
        </div>
      </TabPanel>

      <!-- All Tab -->
      <TabPanel role="tab" aria-label="All signals tab">
        <template #header>
          <span class="mr-2">All</span>
          <Badge :value="allCount" />
        </template>

        <div class="signals-list-container" @scroll="handleScroll">
          <!-- Loading state (initial) -->
          <div
            v-if="signalStore.loading && allSignals.length === 0"
            class="flex flex-col justify-center items-center py-12"
          >
            <ProgressSpinner />
            <span class="ml-4 text-gray-400 mt-4">Loading signals...</span>
          </div>

          <!-- Empty state -->
          <div
            v-else-if="
              !signalStore.loading &&
              displayedSignals.length === 0 &&
              !hasFilters
            "
            class="text-center py-12"
          >
            <i class="pi pi-inbox text-6xl text-gray-600 mb-4"></i>
            <p class="text-xl text-gray-400">No signals found</p>
            <p class="text-sm text-gray-500 mt-2">
              Signals will appear here as patterns are detected
            </p>
          </div>

          <!-- Empty state with filters -->
          <div
            v-else-if="
              !signalStore.loading &&
              displayedSignals.length === 0 &&
              hasFilters
            "
            class="text-center py-12"
          >
            <p class="text-xl text-gray-400">No signals match your filters</p>
            <Button label="Clear Filters" class="mt-4" @click="clearFilters" />
          </div>

          <!-- Signal cards -->
          <div v-else class="signals-list space-y-4">
            <SignalCard
              v-for="signal in displayedSignals"
              :key="signal.id"
              v-memo="[signal.id, signal.status, signal.timestamp]"
              :signal="signal"
              @keydown="handleCardKeyDown"
            />

            <!-- Loading more indicator -->
            <div
              v-if="isLoadingMore"
              class="flex justify-center items-center py-4"
            >
              <ProgressSpinner style="width: 30px; height: 30px" />
              <span class="ml-2 text-gray-400">Loading more...</span>
            </div>

            <!-- No more signals -->
            <div
              v-if="
                !signalStore.hasMore &&
                displayedSignals.length > 0 &&
                !isLoadingMore
              "
              class="text-center py-4 text-gray-500"
            >
              No more signals
            </div>
          </div>
        </div>
      </TabPanel>
    </TabView>
  </div>
</template>

<style scoped>
.live-signals-dashboard {
  @apply bg-gray-900 text-white p-6 rounded-lg;
}

.signals-tabs {
  @apply bg-gray-900;
}

.signals-list-container {
  @apply max-h-[800px] overflow-y-auto pr-2;
}

.signals-list-container::-webkit-scrollbar {
  @apply w-2;
}

.signals-list-container::-webkit-scrollbar-track {
  @apply bg-gray-800 rounded;
}

.signals-list-container::-webkit-scrollbar-thumb {
  @apply bg-gray-600 rounded;
}

.signals-list-container::-webkit-scrollbar-thumb:hover {
  @apply bg-gray-500;
}
</style>
