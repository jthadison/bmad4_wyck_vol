<!--
FAQ View Component (Story 11.8c - Task 1)

Purpose:
--------
Displays FAQ articles using PrimeVue Accordion with real-time search filtering.
Each FAQ item includes an ArticleFeedback component for user feedback collection.

Features:
---------
- PrimeVue Accordion for Q&A display (multiple items can be open)
- Real-time search filtering (matches title or content_markdown)
- Search term highlighting in accordion headers
- Related articles section for each FAQ
- ArticleFeedback component integration
- Empty and loading states
- Computed filtering for performance

Integration:
-----------
- Uses helpStore.fetchArticles('FAQ')
- Renders HTML with v-html (sanitized from backend)
- Shows ArticleFeedback at bottom of each accordion item

Author: Story 11.8c (Task 1)
-->

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useHelpStore } from '@/stores/helpStore'
import { sanitizeHtml } from '@/utils/sanitize'
import Accordion from 'primevue/accordion'
import AccordionTab from 'primevue/accordiontab'
import InputText from 'primevue/inputtext'
import IconField from 'primevue/iconfield'
import InputIcon from 'primevue/inputicon'
import Message from 'primevue/message'
import ProgressSpinner from 'primevue/progressspinner'
import Tag from 'primevue/tag'
import ArticleFeedback from './ArticleFeedback.vue'
import type { HelpArticle } from '@/stores/helpStore'

const helpStore = useHelpStore()

// State
const searchQuery = ref('')

// Computed
const filteredFAQs = computed(() => {
  const query = searchQuery.value.toLowerCase().trim()

  if (!query) {
    return helpStore.articles
  }

  return helpStore.articles.filter((article) => {
    const titleMatch = article.title.toLowerCase().includes(query)
    const contentMatch = article.content_markdown.toLowerCase().includes(query)
    const tagsMatch = article.tags.some((tag) =>
      tag.toLowerCase().includes(query)
    )

    return titleMatch || contentMatch || tagsMatch
  })
})

// Methods
const highlightSearchTerm = (text: string): string => {
  const query = searchQuery.value.trim()

  if (!query) {
    return text
  }

  const regex = new RegExp(`(${query})`, 'gi')
  const highlighted = text.replace(regex, '<mark>$1</mark>')

  // Sanitize the highlighted HTML to prevent XSS
  return sanitizeHtml(highlighted)
}

const sanitizedContent = (article: HelpArticle): string => {
  // Apply client-side sanitization as defense-in-depth
  // (Backend already sanitizes, but this adds extra protection)
  return sanitizeHtml(article.content_html)
}

// Lifecycle
onMounted(async () => {
  await helpStore.fetchArticles('FAQ', 100, 0)
})
</script>

<template>
  <!-- eslint-disable vue/no-v-html -->
  <div class="faq-view">
    <!-- Header -->
    <div class="faq-header">
      <h1 class="faq-title">Frequently Asked Questions</h1>
      <p class="faq-subtitle">
        Find answers to common questions about the Wyckoff trading system
      </p>
    </div>

    <!-- Search Box -->
    <div class="search-section">
      <IconField icon-position="left" class="search-field">
        <InputIcon class="pi pi-search" />
        <InputText
          v-model="searchQuery"
          placeholder="Search FAQ articles..."
          class="search-input"
          data-search-input
        />
      </IconField>
      <p v-if="searchQuery" class="search-results-count">
        Found {{ filteredFAQs.length }} article{{
          filteredFAQs.length !== 1 ? 's' : ''
        }}
      </p>
    </div>

    <!-- Loading State -->
    <div v-if="helpStore.isLoading" class="loading-state">
      <ProgressSpinner />
      <p>Loading FAQ articles...</p>
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

    <!-- Empty State -->
    <Message
      v-else-if="filteredFAQs.length === 0 && searchQuery"
      severity="info"
      :closable="false"
      class="empty-state"
    >
      <div class="empty-state-content">
        <i class="pi pi-search" style="font-size: 2rem"></i>
        <p>No FAQ articles found matching "{{ searchQuery }}"</p>
        <p class="empty-state-hint">
          Try different keywords or
          <a @click="searchQuery = ''">browse all FAQs</a>
        </p>
      </div>
    </Message>

    <Message
      v-else-if="filteredFAQs.length === 0"
      severity="info"
      :closable="false"
      class="empty-state"
    >
      No FAQ articles available yet.
    </Message>

    <!-- FAQ Accordion -->
    <div v-else class="faq-content">
      <Accordion :multiple="true" class="faq-accordion">
        <AccordionTab
          v-for="article in filteredFAQs"
          :key="article.id"
          class="faq-item"
        >
          <template #header>
            <div class="accordion-header">
              <i class="pi pi-question-circle header-icon"></i>
              <!-- eslint-disable-next-line vue/no-v-html -->
              <span
                class="header-title"
                v-html="highlightSearchTerm(article.title)"
              ></span>
              <Tag
                v-if="article.tags.length > 0"
                :value="article.tags[0]"
                severity="secondary"
                class="header-tag"
              />
            </div>
          </template>

          <div class="accordion-content">
            <!-- Article Content -->
            <!-- eslint-disable-next-line vue/no-v-html -->
            <div
              class="article-content"
              v-html="sanitizedContent(article)"
            ></div>

            <!-- Tags -->
            <div v-if="article.tags.length > 1" class="tags-section">
              <span class="tags-label">Tags:</span>
              <Tag
                v-for="tag in article.tags"
                :key="tag"
                :value="tag"
                severity="secondary"
                class="tag"
              />
            </div>

            <!-- Related Articles (placeholder - would need related_slugs field) -->
            <!-- This would be populated if article has a related_slugs field -->

            <!-- Article Metadata -->
            <div class="article-metadata">
              <span class="metadata-item">
                <i class="pi pi-eye"></i>
                {{ article.view_count }} views
              </span>
              <span class="metadata-item">
                <i class="pi pi-calendar"></i>
                Updated
                {{ new Date(article.last_updated).toLocaleDateString() }}
              </span>
            </div>

            <!-- Article Feedback -->
            <div class="feedback-section">
              <ArticleFeedback
                :article-id="article.id"
                :article-slug="article.slug"
              />
            </div>
          </div>
        </AccordionTab>
      </Accordion>
    </div>
  </div>
</template>

<style scoped>
.faq-view {
  max-width: 1000px;
  margin: 0 auto;
  padding: 2rem;
}

.faq-header {
  margin-bottom: 2rem;
}

.faq-title {
  font-size: 2rem;
  font-weight: 600;
  margin: 0 0 0.5rem 0;
  color: var(--primary-color);
}

.faq-subtitle {
  font-size: 1.1rem;
  color: var(--text-color-secondary);
  margin: 0;
}

.search-section {
  margin-bottom: 2rem;
}

.search-field {
  width: 100%;
}

.search-input {
  width: 100%;
}

.search-results-count {
  margin-top: 0.5rem;
  font-size: 0.9rem;
  color: var(--text-color-secondary);
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
  padding: 1rem;
}

.empty-state-content i {
  color: var(--text-color-secondary);
  margin-bottom: 1rem;
}

.empty-state-content p {
  margin: 0.5rem 0;
}

.empty-state-hint {
  font-size: 0.9rem;
  color: var(--text-color-secondary);
}

.empty-state-hint a {
  color: var(--primary-color);
  cursor: pointer;
  text-decoration: underline;
}

.faq-content {
  margin-top: 2rem;
}

.faq-accordion {
  border: 1px solid var(--surface-border);
  border-radius: 6px;
}

.accordion-header {
  display: flex;
  align-items: center;
  gap: 1rem;
  width: 100%;
}

.header-icon {
  color: var(--primary-color);
  font-size: 1.25rem;
  flex-shrink: 0;
}

.header-title {
  flex: 1;
  font-weight: 500;
  font-size: 1.1rem;
}

.header-title :deep(mark) {
  background-color: var(--highlight-bg, #fff3cd);
  font-weight: 600;
  padding: 0.125rem 0.25rem;
  border-radius: 2px;
}

.header-tag {
  flex-shrink: 0;
  font-size: 0.75rem;
}

.accordion-content {
  padding: 1rem 0;
}

.article-content {
  line-height: 1.8;
  margin-bottom: 1.5rem;
}

.article-content :deep(h1),
.article-content :deep(h2),
.article-content :deep(h3) {
  margin-top: 1.5rem;
  margin-bottom: 0.75rem;
  color: var(--text-color);
}

.article-content :deep(h1) {
  font-size: 1.75rem;
}

.article-content :deep(h2) {
  font-size: 1.5rem;
}

.article-content :deep(h3) {
  font-size: 1.25rem;
}

.article-content :deep(p) {
  margin-bottom: 1rem;
}

.article-content :deep(code) {
  background-color: var(--surface-ground);
  padding: 0.125rem 0.375rem;
  border-radius: 3px;
  font-family: monospace;
  font-size: 0.9em;
}

.article-content :deep(pre) {
  background-color: var(--surface-ground);
  padding: 1rem;
  border-radius: 6px;
  overflow-x: auto;
  margin-bottom: 1rem;
}

.article-content :deep(ul),
.article-content :deep(ol) {
  margin-bottom: 1rem;
  padding-left: 2rem;
}

.article-content :deep(li) {
  margin-bottom: 0.5rem;
}

.article-content :deep(a) {
  color: var(--primary-color);
  text-decoration: none;
}

.article-content :deep(a:hover) {
  text-decoration: underline;
}

.tags-section {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 0.5rem;
  margin-bottom: 1.5rem;
  padding-top: 1rem;
  border-top: 1px solid var(--surface-border);
}

.tags-label {
  font-weight: 500;
  font-size: 0.9rem;
  color: var(--text-color-secondary);
}

.tag {
  font-size: 0.75rem;
}

.article-metadata {
  display: flex;
  gap: 1.5rem;
  margin-bottom: 1.5rem;
  padding: 0.75rem;
  background-color: var(--surface-ground);
  border-radius: 6px;
}

.metadata-item {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  font-size: 0.9rem;
  color: var(--text-color-secondary);
}

.metadata-item i {
  font-size: 0.875rem;
}

.feedback-section {
  padding-top: 1.5rem;
  border-top: 1px solid var(--surface-border);
}

/* Responsive */
@media (max-width: 768px) {
  .faq-view {
    padding: 1rem;
  }

  .faq-title {
    font-size: 1.5rem;
  }

  .faq-subtitle {
    font-size: 1rem;
  }

  .accordion-header {
    gap: 0.5rem;
  }

  .header-title {
    font-size: 1rem;
  }

  .article-metadata {
    flex-direction: column;
    gap: 0.5rem;
  }
}
</style>
