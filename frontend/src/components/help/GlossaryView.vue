<template>
  <div class="glossary-view">
    <h2 class="glossary-title">Wyckoff Glossary</h2>
    <p class="glossary-description">
      Essential Wyckoff terminology and concepts used throughout the system.
    </p>

    <!-- Filters -->
    <div class="glossary-filters">
      <!-- Phase Filter -->
      <div class="filter-group">
        <label for="phase-filter">Filter by Phase:</label>
        <Dropdown
          id="phase-filter"
          v-model="selectedPhase"
          :options="phaseOptions"
          option-label="label"
          option-value="value"
          placeholder="All Phases"
          class="phase-dropdown"
        />
      </div>

      <!-- Search Filter -->
      <div class="filter-group">
        <label for="search-filter">Search Terms:</label>
        <IconField icon-position="left" class="search-field">
          <InputIcon class="pi pi-search" />
          <InputText
            id="search-filter"
            v-model="searchFilter"
            placeholder="Filter terms..."
            class="w-full"
          />
        </IconField>
      </div>
    </div>

    <!-- Alphabetical Index -->
    <div class="alpha-index">
      <Button
        v-for="letter in alphabet"
        :key="letter"
        :label="letter"
        class="p-button-text p-button-sm alpha-btn"
        :class="{ disabled: !hasTermsStartingWith(letter) }"
        :disabled="!hasTermsStartingWith(letter)"
        @click="scrollToLetter(letter)"
      />
    </div>

    <!-- Loading State -->
    <div v-if="helpStore.isLoading" class="loading-state">
      <i class="pi pi-spin pi-spinner" style="font-size: 2rem"></i>
      <p>Loading glossary terms...</p>
    </div>

    <!-- Error State -->
    <Message v-else-if="helpStore.error" severity="error" :closable="false">
      {{ helpStore.error }}
    </Message>

    <!-- Empty State -->
    <Message
      v-else-if="filteredTerms.length === 0"
      severity="info"
      :closable="false"
    >
      No terms found matching your search criteria.
    </Message>

    <!-- Glossary Terms -->
    <DataView
      v-else
      :value="filteredTerms"
      :layout="'list'"
      data-key="id"
      class="glossary-dataview"
    >
      <template #list="slotProps">
        <div class="glossary-terms-list">
          <div
            v-for="term in slotProps.items"
            :id="`term-${term.slug}`"
            :key="term.id"
            class="term-card"
            :class="{ expanded: expandedTermId === term.id }"
            @click="toggleTerm(term.id)"
          >
            <!-- Term Header -->
            <div class="term-header">
              <div class="term-title-group">
                <h3 class="term-name">{{ term.term }}</h3>
                <Tag
                  v-if="term.wyckoff_phase"
                  :value="`Phase ${term.wyckoff_phase}`"
                  :severity="getPhaseSeverity(term.wyckoff_phase)"
                  class="phase-tag"
                />
              </div>
              <Button
                :icon="
                  expandedTermId === term.id
                    ? 'pi pi-chevron-up'
                    : 'pi pi-chevron-down'
                "
                class="p-button-text p-button-sm expand-btn"
                aria-label="Expand term"
              />
            </div>

            <!-- Short Definition (always visible) -->
            <p class="short-definition">{{ term.short_definition }}</p>

            <!-- Expanded Content -->
            <div v-if="expandedTermId === term.id" class="expanded-content">
              <!-- Full Description -->
              <!-- eslint-disable vue/no-v-html -->
              <div
                class="full-description"
                v-html="term.full_description_html"
              ></div>
              <!-- eslint-enable vue/no-v-html -->

              <!-- Related Terms -->
              <div v-if="term.related_terms.length > 0" class="related-terms">
                <h4>Related Terms:</h4>
                <div class="related-chips">
                  <Chip
                    v-for="relatedSlug in term.related_terms"
                    :key="relatedSlug"
                    :label="getTermLabelBySlug(relatedSlug)"
                    class="related-chip"
                    @click.stop="scrollToTermBySlug(relatedSlug)"
                  />
                </div>
              </div>

              <!-- Tags -->
              <div v-if="term.tags.length > 0" class="term-tags">
                <Tag
                  v-for="tag in term.tags"
                  :key="tag"
                  :value="tag"
                  severity="secondary"
                  class="tag-item"
                />
              </div>
            </div>

            <!-- Read More Link -->
            <Button
              v-if="expandedTermId !== term.id"
              label="Read more"
              icon="pi pi-angle-right"
              class="p-button-text p-button-sm read-more-btn"
              @click.stop="toggleTerm(term.id)"
            />
          </div>
        </div>
      </template>
    </DataView>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useHelpStore } from '@/stores/helpStore'
import Dropdown from 'primevue/dropdown'
import InputText from 'primevue/inputtext'
import IconField from 'primevue/iconfield'
import InputIcon from 'primevue/inputicon'
import DataView from 'primevue/dataview'
import Button from 'primevue/button'
import Tag from 'primevue/tag'
import Chip from 'primevue/chip'
import Message from 'primevue/message'

// Composables
const helpStore = useHelpStore()

// State
const selectedPhase = ref<string | null>(null)
const searchFilter = ref('')
const expandedTermId = ref<string | null>(null)

// Phase Options
const phaseOptions = [
  { label: 'All Phases', value: null },
  { label: 'Phase A (Stopping Trend)', value: 'A' },
  { label: 'Phase B (Building Cause)', value: 'B' },
  { label: 'Phase C (The Test)', value: 'C' },
  { label: 'Phase D (Trend Emergence)', value: 'D' },
  { label: 'Phase E (Trend Confirmation)', value: 'E' },
]

// Alphabet for index
const alphabet = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'.split('')

// ============================================================================
// Computed Properties
// ============================================================================

/**
 * Filter glossary terms by phase and search query
 */
const filteredTerms = computed(() => {
  let terms = helpStore.glossaryTerms

  // Filter by phase
  if (selectedPhase.value) {
    terms = terms.filter((term) => term.wyckoff_phase === selectedPhase.value)
  }

  // Filter by search query
  if (searchFilter.value.trim()) {
    const query = searchFilter.value.toLowerCase()
    terms = terms.filter(
      (term) =>
        term.term.toLowerCase().includes(query) ||
        term.short_definition.toLowerCase().includes(query) ||
        term.tags.some((tag) => tag.toLowerCase().includes(query))
    )
  }

  // Sort alphabetically
  return terms.slice().sort((a, b) => a.term.localeCompare(b.term))
})

// ============================================================================
// Methods
// ============================================================================

/**
 * Get PrimeVue severity for phase tag color coding
 */
function getPhaseSeverity(phase: string): string {
  const severityMap: Record<string, string> = {
    A: 'danger', // Red
    B: 'warning', // Yellow
    C: 'info', // Blue
    D: 'success', // Green
    E: 'secondary', // Purple/gray
  }
  return severityMap[phase] || 'secondary'
}

/**
 * Toggle expanded state for a term
 */
function toggleTerm(termId: string) {
  if (expandedTermId.value === termId) {
    expandedTermId.value = null
  } else {
    expandedTermId.value = termId
  }
}

/**
 * Get term label by slug for related terms
 */
function getTermLabelBySlug(slug: string): string {
  const term = helpStore.glossaryTerms.find((t) => t.slug === slug)
  return term ? term.term : slug
}

/**
 * Scroll to a term by slug (for related terms)
 */
function scrollToTermBySlug(slug: string) {
  const element = document.getElementById(`term-${slug}`)
  if (element) {
    element.scrollIntoView({ behavior: 'smooth', block: 'center' })
    // Expand the term
    const term = helpStore.glossaryTerms.find((t) => t.slug === slug)
    if (term) {
      expandedTermId.value = term.id
    }
  }
}

/**
 * Check if there are terms starting with a letter
 */
function hasTermsStartingWith(letter: string): boolean {
  return filteredTerms.value.some((term) =>
    term.term.toUpperCase().startsWith(letter)
  )
}

/**
 * Scroll to first term starting with a letter
 */
function scrollToLetter(letter: string) {
  const term = filteredTerms.value.find((t) =>
    t.term.toUpperCase().startsWith(letter)
  )
  if (term) {
    scrollToTermBySlug(term.slug)
  }
}

// ============================================================================
// Lifecycle
// ============================================================================

onMounted(async () => {
  // Fetch glossary terms
  await helpStore.fetchGlossary()
})
</script>

<style scoped>
.glossary-view {
  max-width: 1200px;
}

.glossary-title {
  margin-top: 0;
  color: var(--primary-color);
}

.glossary-description {
  margin-bottom: 2rem;
  color: var(--text-color-secondary);
}

/* Filters */
.glossary-filters {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
  gap: 1.5rem;
  margin-bottom: 2rem;
  padding: 1.5rem;
  background-color: var(--surface-ground);
  border-radius: 6px;
}

.filter-group {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.filter-group label {
  font-weight: 600;
  color: var(--text-color);
}

.phase-dropdown {
  width: 100%;
}

.search-field {
  width: 100%;
}

/* Alphabetical Index */
.alpha-index {
  display: flex;
  flex-wrap: wrap;
  gap: 0.25rem;
  margin-bottom: 1.5rem;
  padding: 1rem;
  background-color: var(--surface-ground);
  border-radius: 6px;
}

.alpha-btn {
  min-width: 2rem;
  padding: 0.25rem 0.5rem;
  font-weight: 600;
}

.alpha-btn.disabled {
  opacity: 0.3;
}

/* Loading/Error States */
.loading-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 3rem;
  color: var(--text-color-secondary);
}

/* DataView */
.glossary-dataview {
  border: none;
}

.glossary-terms-list {
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

/* Term Card */
.term-card {
  padding: 1.5rem;
  background-color: var(--surface-card);
  border: 1px solid var(--surface-border);
  border-radius: 6px;
  cursor: pointer;
  transition: all 0.3s;
}

.term-card:hover {
  border-color: var(--primary-color);
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
}

.term-card.expanded {
  border-color: var(--primary-color);
}

/* Term Header */
.term-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 0.75rem;
}

.term-title-group {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  flex: 1;
}

.term-name {
  margin: 0;
  font-size: 1.25rem;
  color: var(--text-color);
}

.phase-tag {
  font-size: 0.75rem;
  padding: 0.25rem 0.5rem;
}

.expand-btn {
  margin-left: auto;
}

/* Short Definition */
.short-definition {
  margin: 0 0 0.75rem 0;
  color: var(--text-color-secondary);
  line-height: 1.6;
}

/* Expanded Content */
.expanded-content {
  margin-top: 1rem;
  padding-top: 1rem;
  border-top: 1px solid var(--surface-border);
}

.full-description {
  margin-bottom: 1.5rem;
  line-height: 1.7;
  color: var(--text-color);
}

.full-description :deep(h1),
.full-description :deep(h2),
.full-description :deep(h3) {
  margin-top: 1.5rem;
  margin-bottom: 0.75rem;
  color: var(--text-color);
}

.full-description :deep(p) {
  margin-bottom: 1rem;
}

.full-description :deep(code) {
  background-color: var(--surface-ground);
  padding: 0.125rem 0.25rem;
  border-radius: 3px;
  font-family: monospace;
}

.full-description :deep(a) {
  color: var(--primary-color);
  text-decoration: none;
}

.full-description :deep(a:hover) {
  text-decoration: underline;
}

/* Related Terms */
.related-terms {
  margin-bottom: 1rem;
}

.related-terms h4 {
  margin-bottom: 0.75rem;
  font-size: 0.875rem;
  font-weight: 600;
  text-transform: uppercase;
  color: var(--text-color-secondary);
}

.related-chips {
  display: flex;
  flex-wrap: wrap;
  gap: 0.5rem;
}

.related-chip {
  cursor: pointer;
  transition: background-color 0.2s;
}

.related-chip:hover {
  background-color: var(--primary-color);
  color: white;
}

/* Tags */
.term-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 0.5rem;
  margin-top: 1rem;
}

.tag-item {
  font-size: 0.75rem;
}

/* Read More Button */
.read-more-btn {
  margin-top: 0.5rem;
}

/* Responsive */
@media (max-width: 768px) {
  .glossary-filters {
    grid-template-columns: 1fr;
  }

  .alpha-index {
    gap: 0.125rem;
  }

  .alpha-btn {
    min-width: 1.75rem;
    font-size: 0.875rem;
  }

  .term-name {
    font-size: 1.1rem;
  }
}
</style>
