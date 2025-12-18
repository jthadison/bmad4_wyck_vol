<!--
Search Results View Component (Story 11.8c - Task 5)

Purpose:
--------
Displays search results from help content with highlighting, filtering, and keyboard navigation.
Uses route query param /help/search?q={query} to fetch and display results.

Features:
---------
- PrimeVue DataView for result display (list mode)
- Category badges (color-coded: GLOSSARY=blue, FAQ=green, TUTORIAL=purple)
- Search snippet with <mark> highlighting (from backend)
- Total result count display
- Keyboard navigation (Arrow Up/Down, Enter)
- Visual focus indicator for selected result
- Empty state with suggestions
- Loading state with ProgressSpinner
- Click to navigate to article

Integration:
-----------
- Uses route.query.q for search query
- Calls helpStore.searchHelp(query) on mount and when query changes
- Navigates to /help/article/{slug}, /help/glossary, or /help/tutorials/{slug}

Author: Story 11.8c (Task 5)
-->

<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useHelpStore } from '@/stores/helpStore'
import DataView from 'primevue/dataview'
import Tag from 'primevue/tag'
import Message from 'primevue/message'
import ProgressSpinner from 'primevue/progressspinner'

const route = useRoute()
const router = useRouter()
const helpStore = useHelpStore()

// State
const selectedIndex = ref(0)

// Computed
const searchQuery = computed(() => {
  return (route.query.q as string) || ''
})

const totalResults = computed(() => {
  return helpStore.searchResults.length
})

// Methods
const getCategorySeverity = (
  category: string
):
  | 'success'
  | 'info'
  | 'warn'
  | 'danger'
  | 'secondary'
  | 'contrast'
  | undefined => {
  switch (category) {
    case 'GLOSSARY':
      return 'info' // blue
    case 'FAQ':
      return 'success' // green
    case 'TUTORIAL':
      return 'warn' // purple/orange
    case 'REFERENCE':
      return 'secondary'
    default:
      return 'secondary'
  }
}

const navigateToResult = (slug: string, category: string) => {
  // Determine the correct route based on category
  if (category === 'GLOSSARY') {
    router.push('/help/glossary') // Could enhance to scroll to specific term
  } else if (category === 'TUTORIAL') {
    router.push(`/tutorials/${slug}`)
  } else {
    router.push(`/help/article/${slug}`)
  }
}

const handleResultClick = (index: number) => {
  const result = helpStore.searchResults[index]
  if (result) {
    navigateToResult(result.slug, result.category)
  }
}

const handleKeyDown = (event: KeyboardEvent) => {
  if (helpStore.searchResults.length === 0) return

  switch (event.key) {
    case 'ArrowDown':
      event.preventDefault()
      selectedIndex.value = Math.min(
        selectedIndex.value + 1,
        helpStore.searchResults.length - 1
      )
      scrollToSelected()
      break

    case 'ArrowUp':
      event.preventDefault()
      selectedIndex.value = Math.max(selectedIndex.value - 1, 0)
      scrollToSelected()
      break

    case 'Enter':
      event.preventDefault()
      handleResultClick(selectedIndex.value)
      break
  }
}

const scrollToSelected = () => {
  const selectedElement = document.querySelector('.result-item.selected')
  if (selectedElement) {
    selectedElement.scrollIntoView({
      behavior: 'smooth',
      block: 'nearest',
    })
  }
}

const performSearch = async (query: string) => {
  selectedIndex.value = 0
  if (query && query.trim().length > 0) {
    await helpStore.searchHelp(query.trim(), 50)
  }
}

// Lifecycle
onMounted(async () => {
  if (searchQuery.value) {
    await performSearch(searchQuery.value)
  }

  // Add keyboard listener
  window.addEventListener('keydown', handleKeyDown)
})

// Watch for query changes
watch(searchQuery, async (newQuery) => {
  if (newQuery) {
    await performSearch(newQuery)
  }
})

// Cleanup
import { onUnmounted } from 'vue'
onUnmounted(() => {
  window.removeEventListener('keydown', handleKeyDown)
})
</script>

<template>
  <div class="search-results-view">
    <!-- Header -->
    <div class="search-header">
      <h1 class="search-title">Search Results</h1>
      <p v-if="searchQuery" class="search-query">
        Results for: <strong>"{{ searchQuery }}"</strong>
      </p>
    </div>

    <!-- Loading State -->
    <div v-if="helpStore.isLoading" class="loading-state">
      <ProgressSpinner />
      <p>Searching help content...</p>
    </div>

    <!-- Error State -->
    <Message
      v-else-if="helpStore.error"
      severity="error"
      :closable="false"
      class="error-message"
    >
      {{ helpStore.error }}
    </Message>

    <!-- Empty State (No Query) -->
    <Message
      v-else-if="!searchQuery"
      severity="info"
      :closable="false"
      class="empty-state"
    >
      <div class="empty-state-content">
        <i class="pi pi-search" style="font-size: 2rem"></i>
        <p>Enter a search query to find help articles</p>
      </div>
    </Message>

    <!-- Empty State (No Results) -->
    <Message
      v-else-if="totalResults === 0"
      severity="info"
      :closable="false"
      class="empty-state"
    >
      <div class="empty-state-content">
        <i class="pi pi-info-circle" style="font-size: 2rem"></i>
        <p>No results found for "{{ searchQuery }}"</p>
        <div class="suggestions">
          <p class="suggestions-title">Try these suggestions:</p>
          <ul>
            <li>Check your spelling</li>
            <li>Try different keywords</li>
            <li>Use more general terms</li>
            <li>
              <router-link to="/help/glossary">Browse the glossary</router-link>
            </li>
            <li><router-link to="/help/faq">View FAQ</router-link></li>
          </ul>
        </div>
      </div>
    </Message>

    <!-- Results -->
    <div v-else class="results-container">
      <!-- Result Count -->
      <div class="results-count">
        Found <strong>{{ totalResults }}</strong> result{{
          totalResults !== 1 ? 's' : ''
        }}
      </div>

      <!-- Results List -->
      <DataView :value="helpStore.searchResults" class="results-list">
        <template #list="slotProps">
          <div
            v-for="(result, index) in slotProps.items"
            :key="result.id"
            class="result-item"
            :class="{ selected: index === selectedIndex }"
            @click="handleResultClick(index)"
            @mouseenter="selectedIndex = index"
          >
            <div class="result-header">
              <h3 class="result-title">{{ result.title }}</h3>
              <Tag
                :value="result.category"
                :severity="getCategorySeverity(result.category)"
                class="category-badge"
              />
            </div>

            <!-- Snippet with highlighting -->
            <!-- eslint-disable-next-line vue/no-v-html -->
            <div class="result-snippet" v-html="result.snippet"></div>

            <!-- Metadata -->
            <div class="result-metadata">
              <span class="metadata-item">
                <i class="pi pi-tag"></i>
                {{ result.category }}
              </span>
              <span class="metadata-item">
                <i class="pi pi-link"></i>
                {{ result.slug }}
              </span>
              <span class="metadata-item rank">
                <i class="pi pi-star"></i>
                Relevance: {{ Math.round(result.rank * 100) }}%
              </span>
            </div>
          </div>
        </template>
      </DataView>

      <!-- Keyboard Navigation Hint -->
      <div class="navigation-hint">
        <i class="pi pi-info-circle"></i>
        Use <kbd>↑</kbd> <kbd>↓</kbd> to navigate, <kbd>Enter</kbd> to open
      </div>
    </div>
  </div>
</template>

<style scoped>
.search-results-view {
  max-width: 1000px;
  margin: 0 auto;
  padding: 2rem;
}

.search-header {
  margin-bottom: 2rem;
}

.search-title {
  font-size: 2rem;
  font-weight: 600;
  margin: 0 0 0.5rem 0;
  color: var(--primary-color);
}

.search-query {
  font-size: 1.1rem;
  color: var(--text-color-secondary);
  margin: 0;
}

.search-query strong {
  color: var(--text-color);
}

.loading-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 4rem 2rem;
  gap: 1rem;
  color: var(--text-color-secondary);
}

.error-message,
.empty-state {
  margin-top: 2rem;
}

.empty-state-content {
  text-align: center;
  padding: 2rem;
}

.empty-state-content i {
  color: var(--text-color-secondary);
  margin-bottom: 1rem;
}

.empty-state-content p {
  margin: 1rem 0;
  font-size: 1.1rem;
}

.suggestions {
  margin-top: 2rem;
  text-align: left;
  display: inline-block;
}

.suggestions-title {
  font-weight: 600;
  margin-bottom: 0.75rem;
  color: var(--text-color);
}

.suggestions ul {
  list-style: none;
  padding-left: 0;
}

.suggestions li {
  margin-bottom: 0.5rem;
  padding-left: 1.5rem;
  position: relative;
}

.suggestions li::before {
  content: '•';
  position: absolute;
  left: 0.5rem;
  color: var(--primary-color);
}

.suggestions a {
  color: var(--primary-color);
  text-decoration: none;
}

.suggestions a:hover {
  text-decoration: underline;
}

.results-container {
  margin-top: 2rem;
}

.results-count {
  margin-bottom: 1.5rem;
  font-size: 1rem;
  color: var(--text-color-secondary);
}

.results-count strong {
  color: var(--text-color);
  font-weight: 600;
}

.results-list {
  border: none;
}

.result-item {
  padding: 1.5rem;
  margin-bottom: 1rem;
  background-color: var(--surface-card);
  border: 2px solid var(--surface-border);
  border-radius: 8px;
  cursor: pointer;
  transition:
    all 0.2s,
    border-color 0.2s;
}

.result-item:hover,
.result-item.selected {
  border-color: var(--primary-color);
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
  transform: translateY(-2px);
}

.result-item.selected {
  background-color: var(--highlight-bg, rgba(var(--primary-color-rgb), 0.05));
}

.result-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 1rem;
  margin-bottom: 0.75rem;
}

.result-title {
  font-size: 1.25rem;
  font-weight: 600;
  margin: 0;
  color: var(--text-color);
  flex: 1;
}

.category-badge {
  flex-shrink: 0;
  font-size: 0.75rem;
  text-transform: uppercase;
  font-weight: 600;
}

.result-snippet {
  font-size: 0.95rem;
  color: var(--text-color-secondary);
  line-height: 1.6;
  margin-bottom: 1rem;
}

.result-snippet :deep(mark) {
  background-color: var(--highlight-bg, #fff3cd);
  font-weight: 600;
  padding: 0.125rem 0.25rem;
  border-radius: 2px;
  color: var(--text-color);
}

.result-metadata {
  display: flex;
  flex-wrap: wrap;
  gap: 1.5rem;
  font-size: 0.875rem;
  color: var(--text-color-secondary);
  border-top: 1px solid var(--surface-border);
  padding-top: 0.75rem;
}

.metadata-item {
  display: flex;
  align-items: center;
  gap: 0.375rem;
}

.metadata-item i {
  font-size: 0.75rem;
}

.metadata-item.rank {
  margin-left: auto;
  font-weight: 500;
}

.navigation-hint {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 0.5rem;
  margin-top: 2rem;
  padding: 1rem;
  background-color: var(--surface-ground);
  border-radius: 6px;
  font-size: 0.9rem;
  color: var(--text-color-secondary);
}

.navigation-hint kbd {
  display: inline-block;
  padding: 0.25rem 0.5rem;
  background: var(--surface-card);
  border: 1px solid var(--surface-border);
  border-radius: 4px;
  font-family: 'Courier New', monospace;
  font-size: 0.85rem;
  font-weight: 600;
  margin: 0 0.25rem;
}

/* Responsive */
@media (max-width: 768px) {
  .search-results-view {
    padding: 1rem;
  }

  .search-title {
    font-size: 1.5rem;
  }

  .result-header {
    flex-direction: column;
    align-items: flex-start;
  }

  .category-badge {
    align-self: flex-start;
  }

  .result-metadata {
    flex-direction: column;
    gap: 0.5rem;
  }

  .metadata-item.rank {
    margin-left: 0;
  }
}
</style>
