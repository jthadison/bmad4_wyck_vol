<template>
  <div class="help-center">
    <!-- Mobile Header with Hamburger Menu -->
    <div class="help-center-header">
      <Button
        icon="pi pi-bars"
        class="p-button-text mobile-menu-btn"
        aria-label="Toggle menu"
        @click="sidebarVisible = !sidebarVisible"
      />
      <h1 class="help-center-title">Help Center</h1>
    </div>

    <!-- Sidebar -->
    <Sidebar
      v-model:visible="sidebarVisible"
      :show-close-icon="true"
      :dismissable="true"
      :position="'left'"
      :class="{ 'desktop-sidebar': !isMobile }"
    >
      <template #header>
        <h2 class="sidebar-title">Navigation</h2>
      </template>

      <!-- Search Bar in Sidebar -->
      <div class="search-container">
        <IconField icon-position="left">
          <InputIcon class="pi pi-search" />
          <InputText
            v-model="searchQuery"
            placeholder="Search help..."
            class="w-full"
            @input="handleSearchInput"
          />
        </IconField>

        <!-- Search Results Overlay -->
        <OverlayPanel ref="searchResultsPanel">
          <div v-if="helpStore.isLoading" class="search-loading">
            <i class="pi pi-spin pi-spinner"></i> Searching...
          </div>
          <div
            v-else-if="helpStore.searchResults.length > 0"
            class="search-results"
          >
            <div
              v-for="result in helpStore.searchResults"
              :key="result.article_id"
              class="search-result-item"
              @click="navigateToArticle(result.slug)"
            >
              <div class="result-header">
                <span class="result-title">{{ result.title }}</span>
                <Tag
                  :value="result.category"
                  severity="info"
                  class="result-category"
                />
              </div>
              <!-- eslint-disable-next-line vue/no-v-html -->
              <div class="result-snippet" v-html="result.snippet"></div>
            </div>
          </div>
          <div v-else class="search-no-results">
            <i class="pi pi-info-circle"></i> No results found
          </div>
        </OverlayPanel>
      </div>

      <!-- Navigation Menu -->
      <Menu :model="menuItems" class="help-nav-menu" />
    </Sidebar>

    <!-- Desktop Sidebar (always visible) -->
    <div v-if="!isMobile" class="desktop-sidebar-container">
      <div class="search-container">
        <IconField icon-position="left">
          <InputIcon class="pi pi-search" />
          <InputText
            v-model="searchQuery"
            placeholder="Search help..."
            class="w-full"
            @input="handleSearchInput"
          />
        </IconField>

        <!-- Search Results Overlay -->
        <OverlayPanel ref="desktopSearchPanel">
          <div v-if="helpStore.isLoading" class="search-loading">
            <i class="pi pi-spin pi-spinner"></i> Searching...
          </div>
          <div
            v-else-if="helpStore.searchResults.length > 0"
            class="search-results"
          >
            <div
              v-for="result in helpStore.searchResults"
              :key="result.article_id"
              class="search-result-item"
              @click="navigateToArticle(result.slug)"
            >
              <div class="result-header">
                <span class="result-title">{{ result.title }}</span>
                <Tag
                  :value="result.category"
                  severity="info"
                  class="result-category"
                />
              </div>
              <!-- eslint-disable-next-line vue/no-v-html -->
              <div class="result-snippet" v-html="result.snippet"></div>
            </div>
          </div>
          <div v-else class="search-no-results">
            <i class="pi pi-info-circle"></i> No results found
          </div>
        </OverlayPanel>
      </div>

      <Menu :model="menuItems" class="help-nav-menu" />
    </div>

    <!-- Main Content Area -->
    <div class="help-content-area">
      <!-- Breadcrumb -->
      <Breadcrumb
        :home="breadcrumbHome"
        :model="breadcrumbItems"
        class="help-breadcrumb"
      />

      <!-- Router View for Nested Routes -->
      <div class="help-content">
        <router-view v-slot="{ Component }">
          <transition name="fade" mode="out-in">
            <component :is="Component" />
          </transition>
        </router-view>

        <!-- Home View (when at /help root) -->
        <div v-if="$route.path === '/help'" class="help-home">
          <h2>Welcome to the Help Center</h2>
          <p>Find answers and learn about the Wyckoff trading system.</p>

          <!-- Popular Topics -->
          <div class="popular-topics">
            <h3>Popular Topics</h3>
            <div class="topic-cards">
              <Card
                v-for="topic in popularTopics"
                :key="topic.slug"
                class="topic-card"
                @click="navigateToArticle(topic.slug)"
              >
                <template #header>
                  <i :class="topic.icon" class="topic-icon"></i>
                </template>
                <template #title>{{ topic.title }}</template>
                <template #content>
                  <p>{{ topic.description }}</p>
                </template>
              </Card>
            </div>
          </div>

          <!-- Recent Articles -->
          <div v-if="recentArticles.length > 0" class="recent-articles">
            <h3>Recent Articles</h3>
            <div class="article-list">
              <div
                v-for="article in recentArticles"
                :key="article.id"
                class="article-item"
                @click="navigateToArticle(article.slug)"
              >
                <span class="article-title">{{ article.title }}</span>
                <Tag :value="article.category" severity="secondary" />
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useHelpStore } from '@/stores/helpStore'
import Button from 'primevue/button'
import Sidebar from 'primevue/sidebar'
import Menu from 'primevue/menu'
import InputText from 'primevue/inputtext'
import IconField from 'primevue/iconfield'
import InputIcon from 'primevue/inputicon'
import OverlayPanel from 'primevue/overlaypanel'
import Breadcrumb from 'primevue/breadcrumb'
import Card from 'primevue/card'
import Tag from 'primevue/tag'

// Composables
const router = useRouter()
const route = useRoute()
const helpStore = useHelpStore()

// State
const sidebarVisible = ref(false)
const searchQuery = ref('')
const searchResultsPanel = ref()
const desktopSearchPanel = ref()
const isMobile = ref(window.innerWidth < 768)

// Debounce timer for search
let searchDebounceTimer: ReturnType<typeof setTimeout> | null = null

// Navigation Menu Items
const menuItems = computed(() => [
  {
    label: 'Home',
    icon: 'pi pi-home',
    command: () => router.push('/help'),
  },
  {
    label: 'Tutorials',
    icon: 'pi pi-graduation-cap',
    command: () => router.push('/tutorials'),
  },
  {
    label: 'Glossary',
    icon: 'pi pi-book',
    command: () => router.push('/help/glossary'),
  },
  {
    label: 'Keyboard Shortcuts',
    icon: 'pi pi-keyboard',
    command: () => showKeyboardShortcuts(),
  },
])

// Breadcrumb
const breadcrumbHome = { icon: 'pi pi-home', to: '/help' }
const breadcrumbItems = computed(() => {
  const items = []
  const meta = route.meta.breadcrumb as
    | Array<{ label: string; to?: string }>
    | undefined

  if (meta) {
    items.push(...meta)
  }

  return items
})

// Popular Topics (hardcoded for 11.8a)
const popularTopics = [
  {
    slug: 'what-is-wyckoff',
    title: 'What is Wyckoff?',
    description:
      'Learn about the Wyckoff methodology and its three fundamental laws.',
    icon: 'pi pi-question-circle',
  },
  {
    slug: 'how-are-signals-generated',
    title: 'How Signals Work',
    description: 'Understand how trading signals are detected and generated.',
    icon: 'pi pi-bolt',
  },
  {
    slug: 'how-is-risk-calculated',
    title: 'Risk Management',
    description: 'Learn about structural stops and R-multiple calculations.',
    icon: 'pi pi-shield',
  },
  {
    slug: 'spring',
    title: 'Spring Pattern',
    description:
      'Understand the Spring pattern and how it signals accumulation.',
    icon: 'pi pi-chart-line',
  },
]

// Recent Articles
const recentArticles = computed(() => {
  return helpStore.articles.slice(0, 5)
})

// ============================================================================
// Methods
// ============================================================================

function handleSearchInput() {
  // Clear previous timer
  if (searchDebounceTimer) {
    clearTimeout(searchDebounceTimer)
  }

  // Debounce search by 300ms
  searchDebounceTimer = setTimeout(async () => {
    if (searchQuery.value.trim().length > 0) {
      await helpStore.searchHelp(searchQuery.value)

      // Show overlay panel
      if (isMobile.value && searchResultsPanel.value) {
        searchResultsPanel.value.show(event)
      } else if (!isMobile.value && desktopSearchPanel.value) {
        desktopSearchPanel.value.show(event)
      }
    }
  }, 300)
}

function navigateToArticle(slug: string) {
  router.push(`/help/article/${slug}`)

  // Close overlay panels and mobile sidebar
  if (searchResultsPanel.value) {
    searchResultsPanel.value.hide()
  }
  if (desktopSearchPanel.value) {
    desktopSearchPanel.value.hide()
  }
  sidebarVisible.value = false
}

function showKeyboardShortcuts() {
  // TODO: Implement keyboard shortcuts overlay (Story 11.8b)
  console.log('Keyboard shortcuts not yet implemented')
}

function handleResize() {
  isMobile.value = window.innerWidth < 768
}

// ============================================================================
// Lifecycle
// ============================================================================

onMounted(async () => {
  // Fetch initial articles
  await helpStore.fetchArticles('ALL', 10, 0)

  // Add resize listener
  window.addEventListener('resize', handleResize)
})

// Watch for route changes to auto-close mobile sidebar
watch(
  () => route.path,
  () => {
    if (isMobile.value) {
      sidebarVisible.value = false
    }
  }
)
</script>

<style scoped>
.help-center {
  display: grid;
  grid-template-columns: 25% 75%;
  grid-template-rows: auto 1fr;
  min-height: 100vh;
  background-color: var(--surface-ground);
}

/* Mobile Header */
.help-center-header {
  display: none;
  align-items: center;
  gap: 1rem;
  padding: 1rem;
  background-color: var(--surface-card);
  border-bottom: 1px solid var(--surface-border);
}

.mobile-menu-btn {
  font-size: 1.5rem;
}

.help-center-title {
  margin: 0;
  font-size: 1.25rem;
}

/* Desktop Sidebar */
.desktop-sidebar-container {
  grid-column: 1;
  grid-row: 1 / 3;
  padding: 1.5rem;
  background-color: var(--surface-card);
  border-right: 1px solid var(--surface-border);
  overflow-y: auto;
}

/* Search Container */
.search-container {
  margin-bottom: 1.5rem;
}

.search-results {
  max-height: 400px;
  overflow-y: auto;
  min-width: 400px;
}

.search-result-item {
  padding: 0.75rem;
  border-bottom: 1px solid var(--surface-border);
  cursor: pointer;
  transition: background-color 0.2s;
}

.search-result-item:hover {
  background-color: var(--surface-hover);
}

.result-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 0.5rem;
}

.result-title {
  font-weight: 600;
  color: var(--text-color);
}

.result-category {
  font-size: 0.75rem;
}

.result-snippet {
  font-size: 0.875rem;
  color: var(--text-color-secondary);
  line-height: 1.4;
}

.result-snippet :deep(mark) {
  background-color: var(--highlight-bg);
  font-weight: 600;
  padding: 0.125rem;
}

.search-loading,
.search-no-results {
  padding: 1rem;
  text-align: center;
  color: var(--text-color-secondary);
}

/* Navigation Menu */
.help-nav-menu {
  border: none;
}

/* Main Content Area */
.help-content-area {
  grid-column: 2;
  grid-row: 1 / 3;
  padding: 2rem;
  overflow-y: auto;
}

.help-breadcrumb {
  margin-bottom: 1.5rem;
}

.help-content {
  background-color: var(--surface-card);
  border-radius: 6px;
  padding: 2rem;
  min-height: calc(100vh - 8rem);
}

/* Home View */
.help-home h2 {
  margin-top: 0;
  color: var(--primary-color);
}

.popular-topics {
  margin-top: 2rem;
}

.popular-topics h3 {
  margin-bottom: 1rem;
}

.topic-cards {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
  gap: 1rem;
}

.topic-card {
  cursor: pointer;
  transition:
    transform 0.2s,
    box-shadow 0.2s;
}

.topic-card:hover {
  transform: translateY(-4px);
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
}

.topic-icon {
  font-size: 2.5rem;
  color: var(--primary-color);
  padding: 1rem;
}

.recent-articles {
  margin-top: 2rem;
}

.recent-articles h3 {
  margin-bottom: 1rem;
}

.article-list {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}

.article-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 1rem;
  background-color: var(--surface-ground);
  border-radius: 4px;
  cursor: pointer;
  transition: background-color 0.2s;
}

.article-item:hover {
  background-color: var(--surface-hover);
}

.article-title {
  font-weight: 500;
}

/* Transitions */
.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.3s;
}

.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}

/* Mobile Responsive */
@media (max-width: 768px) {
  .help-center {
    grid-template-columns: 1fr;
    grid-template-rows: auto 1fr;
  }

  .help-center-header {
    display: flex;
    grid-column: 1;
    grid-row: 1;
  }

  .desktop-sidebar-container {
    display: none;
  }

  .help-content-area {
    grid-column: 1;
    grid-row: 2;
    padding: 1rem;
  }

  .help-content {
    padding: 1rem;
  }

  .topic-cards {
    grid-template-columns: 1fr;
  }

  .search-results {
    min-width: auto;
    max-width: 100vw;
  }
}
</style>
