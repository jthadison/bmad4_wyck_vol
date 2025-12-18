<!--
Article View Component (Story 11.8c - Task 6)

Purpose:
--------
Displays full help articles with table of contents, related articles, and feedback.
Generates TOC from h2/h3 headers in content_html.

Features:
---------
- Article title, metadata (category, date, view count)
- Rendered HTML content (v-html, sanitized from backend)
- Auto-generated table of contents from h2/h3 headers
- TOC sticky sidebar on desktop, collapsible accordion on mobile
- TOC links with smooth scroll and id attributes on headers
- Related articles section (if article has related_slugs)
- ArticleFeedback component integration
- Share button (copy URL to clipboard)
- Print button (window.print())
- 404 handling with link back to help home

Integration:
-----------
- Uses route param /help/article/:slug
- Calls helpStore.fetchArticle(slug) on mount
- ArticleFeedback component for feedback collection

Author: Story 11.8c (Task 6)
-->

<script setup lang="ts">
import { ref, computed, onMounted, nextTick } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useHelpStore } from '@/stores/helpStore'
import { sanitizeHtml } from '@/utils/sanitize'
import { useToast } from 'primevue/usetoast'
import Message from 'primevue/message'
import Tag from 'primevue/tag'
import Button from 'primevue/button'
import ProgressSpinner from 'primevue/progressspinner'
import Accordion from 'primevue/accordion'
import AccordionTab from 'primevue/accordiontab'
import ArticleFeedback from './ArticleFeedback.vue'

interface TocItem {
  id: string
  text: string
  level: number
}

const route = useRoute()
const router = useRouter()
const helpStore = useHelpStore()
const toast = useToast()

// State
const tableOfContents = ref<TocItem[]>([])
const isMobile = ref(window.innerWidth < 1024)

// Computed
const article = computed(() => helpStore.currentArticle)

const sanitizedArticleContent = computed(() => {
  if (!article.value) return ''

  // Apply client-side sanitization as defense-in-depth
  // (Backend already sanitizes, but this adds extra protection)
  return sanitizeHtml(article.value.content_html)
})

// Methods
const formatDate = (dateString: string): string => {
  return new Date(dateString).toLocaleDateString('en-US', {
    year: 'numeric',
    month: 'long',
    day: 'numeric',
  })
}

const generateTableOfContents = () => {
  if (!article.value) return

  const articleBody = document.querySelector('.article-body')
  if (!articleBody) return

  const headers = articleBody.querySelectorAll('h2, h3')
  const toc: TocItem[] = []

  headers.forEach((header, index) => {
    const text = header.textContent || ''
    const level = parseInt(header.tagName.substring(1)) // h2 → 2, h3 → 3
    const id = `heading-${index}`

    // Add id attribute to header for smooth scroll
    header.setAttribute('id', id)

    toc.push({
      id,
      text,
      level,
    })
  })

  tableOfContents.value = toc
}

const scrollToHeading = (headingId: string) => {
  const element = document.getElementById(headingId)
  if (element) {
    element.scrollIntoView({
      behavior: 'smooth',
      block: 'start',
    })
  }
}

const copyArticleUrl = async () => {
  const url = window.location.href

  try {
    await navigator.clipboard.writeText(url)
    toast.add({
      severity: 'success',
      summary: 'Link Copied',
      detail: 'Article URL copied to clipboard',
      life: 3000,
    })
  } catch (error) {
    console.error('Failed to copy URL:', error)
    toast.add({
      severity: 'error',
      summary: 'Copy Failed',
      detail: 'Failed to copy article URL',
      life: 3000,
    })
  }
}

const printArticle = () => {
  window.print()
}

const handleResize = () => {
  isMobile.value = window.innerWidth < 1024
}

// Lifecycle
onMounted(async () => {
  const slug = route.params.slug as string
  await helpStore.fetchArticle(slug)

  // Generate TOC after article loads
  await nextTick()
  generateTableOfContents()

  // Add resize listener
  window.addEventListener('resize', handleResize)
})

// Cleanup
import { onUnmounted } from 'vue'
onUnmounted(() => {
  window.removeEventListener('resize', handleResize)
})
</script>

<template>
  <div class="article-view">
    <!-- Loading State -->
    <div v-if="helpStore.isLoading" class="loading-state">
      <ProgressSpinner />
      <p>Loading article...</p>
    </div>

    <!-- Error State / 404 -->
    <div v-else-if="helpStore.error || !article" class="error-state">
      <Message severity="warn" :closable="false" class="error-message">
        <div class="error-content">
          <i class="pi pi-exclamation-triangle" style="font-size: 2rem"></i>
          <h2>Article Not Found</h2>
          <p>The article you're looking for doesn't exist or has been moved.</p>
          <Button
            label="Back to Help Center"
            icon="pi pi-home"
            @click="router.push('/help')"
          />
        </div>
      </Message>
    </div>

    <!-- Article Content -->
    <div v-else class="article-container">
      <!-- Main Content Area -->
      <div class="article-main">
        <!-- Article Header -->
        <div class="article-header">
          <h1 class="article-title">{{ article.title }}</h1>

          <!-- Metadata -->
          <div class="article-metadata">
            <Tag
              :value="article.category"
              severity="info"
              class="category-tag"
            />
            <span class="metadata-item">
              <i class="pi pi-calendar"></i>
              Updated {{ formatDate(article.last_updated) }}
            </span>
            <span class="metadata-item">
              <i class="pi pi-eye"></i>
              {{ article.view_count }} views
            </span>
          </div>

          <!-- Action Buttons -->
          <div class="article-actions">
            <Button
              icon="pi pi-share-alt"
              label="Share"
              severity="secondary"
              outlined
              size="small"
              @click="copyArticleUrl"
            />
            <Button
              icon="pi pi-print"
              label="Print"
              severity="secondary"
              outlined
              size="small"
              @click="printArticle"
            />
          </div>
        </div>

        <!-- Article Body -->
        <!-- eslint-disable-next-line vue/no-v-html -->
        <div class="article-body" v-html="sanitizedArticleContent"></div>

        <!-- Tags -->
        <div v-if="article.tags.length > 0" class="article-tags">
          <h4 class="tags-title">Tags</h4>
          <div class="tags-list">
            <Tag
              v-for="tag in article.tags"
              :key="tag"
              :value="tag"
              severity="secondary"
              class="tag-item"
            />
          </div>
        </div>

        <!-- Related Articles Section (placeholder - would need related_slugs field) -->
        <!-- This would be populated if article model has related_slugs field -->

        <!-- Article Feedback -->
        <div class="feedback-section">
          <ArticleFeedback
            :article-id="article.id"
            :article-slug="article.slug"
          />
        </div>
      </div>

      <!-- Table of Contents Sidebar (Desktop) -->
      <aside v-if="!isMobile && tableOfContents.length > 0" class="toc-sidebar">
        <div class="toc-sticky">
          <h3 class="toc-title">On This Page</h3>
          <nav class="toc-nav">
            <a
              v-for="item in tableOfContents"
              :key="item.id"
              :class="['toc-link', `toc-level-${item.level}`]"
              @click.prevent="scrollToHeading(item.id)"
            >
              {{ item.text }}
            </a>
          </nav>
        </div>
      </aside>

      <!-- Table of Contents Accordion (Mobile) -->
      <div v-if="isMobile && tableOfContents.length > 0" class="toc-mobile">
        <Accordion>
          <AccordionTab header="Table of Contents">
            <nav class="toc-nav">
              <a
                v-for="item in tableOfContents"
                :key="item.id"
                :class="['toc-link', `toc-level-${item.level}`]"
                @click.prevent="scrollToHeading(item.id)"
              >
                {{ item.text }}
              </a>
            </nav>
          </AccordionTab>
        </Accordion>
      </div>
    </div>
  </div>
</template>

<style scoped>
.article-view {
  max-width: 1400px;
  margin: 0 auto;
  padding: 2rem;
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

.error-state {
  padding: 2rem;
}

.error-message {
  margin: 0;
}

.error-content {
  text-align: center;
  padding: 2rem;
}

.error-content i {
  color: var(--text-color-secondary);
  margin-bottom: 1rem;
}

.error-content h2 {
  margin: 1rem 0;
  color: var(--text-color);
}

.error-content p {
  margin-bottom: 2rem;
  color: var(--text-color-secondary);
}

.article-container {
  display: grid;
  grid-template-columns: 1fr 300px;
  gap: 3rem;
  align-items: start;
}

.article-main {
  min-width: 0; /* Prevent grid blowout */
}

.article-header {
  margin-bottom: 2rem;
  padding-bottom: 1.5rem;
  border-bottom: 2px solid var(--surface-border);
}

.article-title {
  font-size: 2.5rem;
  font-weight: 700;
  margin: 0 0 1rem 0;
  color: var(--primary-color);
  line-height: 1.2;
}

.article-metadata {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 1rem;
  margin-bottom: 1rem;
}

.category-tag {
  font-size: 0.875rem;
  text-transform: uppercase;
  font-weight: 600;
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

.article-actions {
  display: flex;
  gap: 0.75rem;
}

.article-body {
  line-height: 1.8;
  font-size: 1.05rem;
  margin-bottom: 3rem;
  color: var(--text-color);
}

/* Article Body Styling */
.article-body :deep(h1),
.article-body :deep(h2),
.article-body :deep(h3),
.article-body :deep(h4) {
  margin-top: 2rem;
  margin-bottom: 1rem;
  color: var(--text-color);
  font-weight: 600;
  line-height: 1.3;
}

.article-body :deep(h1) {
  font-size: 2rem;
}

.article-body :deep(h2) {
  font-size: 1.75rem;
  padding-top: 1rem;
  scroll-margin-top: 2rem; /* Offset for smooth scroll */
}

.article-body :deep(h3) {
  font-size: 1.4rem;
  scroll-margin-top: 2rem;
}

.article-body :deep(h4) {
  font-size: 1.2rem;
}

.article-body :deep(p) {
  margin-bottom: 1.25rem;
}

.article-body :deep(a) {
  color: var(--primary-color);
  text-decoration: none;
  font-weight: 500;
}

.article-body :deep(a:hover) {
  text-decoration: underline;
}

.article-body :deep(code) {
  background-color: var(--surface-ground);
  padding: 0.2rem 0.4rem;
  border-radius: 4px;
  font-family: 'Courier New', monospace;
  font-size: 0.9em;
  color: var(--text-color);
}

.article-body :deep(pre) {
  background-color: var(--surface-ground);
  padding: 1.5rem;
  border-radius: 8px;
  overflow-x: auto;
  margin-bottom: 1.5rem;
  border: 1px solid var(--surface-border);
}

.article-body :deep(pre code) {
  background: none;
  padding: 0;
}

.article-body :deep(ul),
.article-body :deep(ol) {
  margin-bottom: 1.5rem;
  padding-left: 2.5rem;
}

.article-body :deep(li) {
  margin-bottom: 0.75rem;
  line-height: 1.7;
}

.article-body :deep(blockquote) {
  margin: 1.5rem 0;
  padding: 1rem 1.5rem;
  border-left: 4px solid var(--primary-color);
  background-color: var(--surface-ground);
  font-style: italic;
  color: var(--text-color-secondary);
}

.article-body :deep(img) {
  max-width: 100%;
  height: auto;
  border-radius: 8px;
  margin: 1.5rem 0;
}

.article-body :deep(table) {
  width: 100%;
  border-collapse: collapse;
  margin: 1.5rem 0;
}

.article-body :deep(th),
.article-body :deep(td) {
  padding: 0.75rem;
  text-align: left;
  border: 1px solid var(--surface-border);
}

.article-body :deep(th) {
  background-color: var(--surface-ground);
  font-weight: 600;
}

.article-tags {
  margin-bottom: 3rem;
  padding-top: 2rem;
  border-top: 1px solid var(--surface-border);
}

.tags-title {
  font-size: 0.9rem;
  font-weight: 600;
  text-transform: uppercase;
  color: var(--text-color-secondary);
  margin: 0 0 1rem 0;
}

.tags-list {
  display: flex;
  flex-wrap: wrap;
  gap: 0.5rem;
}

.tag-item {
  font-size: 0.85rem;
}

.feedback-section {
  margin-top: 3rem;
  padding-top: 3rem;
  border-top: 2px solid var(--surface-border);
}

/* Table of Contents Sidebar */
.toc-sidebar {
  position: relative;
}

.toc-sticky {
  position: sticky;
  top: 2rem;
  padding: 1.5rem;
  background-color: var(--surface-card);
  border: 1px solid var(--surface-border);
  border-radius: 8px;
  max-height: calc(100vh - 4rem);
  overflow-y: auto;
}

.toc-title {
  font-size: 0.95rem;
  font-weight: 600;
  text-transform: uppercase;
  color: var(--text-color-secondary);
  margin: 0 0 1rem 0;
}

.toc-nav {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.toc-link {
  display: block;
  padding: 0.5rem 0.75rem;
  color: var(--text-color-secondary);
  text-decoration: none;
  border-left: 2px solid transparent;
  transition:
    all 0.2s,
    border-color 0.2s;
  cursor: pointer;
  font-size: 0.9rem;
  line-height: 1.4;
}

.toc-link:hover {
  color: var(--primary-color);
  background-color: var(--surface-hover);
  border-left-color: var(--primary-color);
}

.toc-level-2 {
  padding-left: 0.75rem;
}

.toc-level-3 {
  padding-left: 1.5rem;
  font-size: 0.85rem;
}

/* Mobile TOC */
.toc-mobile {
  margin-bottom: 2rem;
}

/* Print Styles */
@media print {
  .article-actions,
  .toc-sidebar,
  .toc-mobile,
  .feedback-section {
    display: none !important;
  }

  .article-container {
    grid-template-columns: 1fr;
  }
}

/* Responsive */
@media (max-width: 1024px) {
  .article-container {
    grid-template-columns: 1fr;
  }

  .toc-sidebar {
    display: none;
  }
}

@media (max-width: 768px) {
  .article-view {
    padding: 1rem;
  }

  .article-title {
    font-size: 1.75rem;
  }

  .article-metadata {
    flex-direction: column;
    align-items: flex-start;
    gap: 0.5rem;
  }

  .article-actions {
    width: 100%;
  }

  .article-actions button {
    flex: 1;
  }

  .article-body {
    font-size: 1rem;
  }

  .article-body :deep(h2) {
    font-size: 1.5rem;
  }

  .article-body :deep(h3) {
    font-size: 1.25rem;
  }
}
</style>
