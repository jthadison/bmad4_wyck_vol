/**
 * Help Store (Story 11.8a - Task 10: Frontend Help Store)
 *
 * Manages help content including articles, glossary terms, and search results.
 * Features:
 * - Article and glossary term caching (24-hour for articles, indefinite for glossary)
 * - Full-text search across help content
 * - Article feedback submission
 */

import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { apiClient } from '@/services/api'

// ============================================================================
// Types (will be replaced by auto-generated types from pydantic-to-typescript)
// ============================================================================

export interface HelpArticle {
  id: string
  slug: string
  title: string
  content_markdown: string
  content_html: string
  category: 'GLOSSARY' | 'FAQ' | 'TUTORIAL' | 'REFERENCE'
  tags: string[]
  keywords: string
  last_updated: string
  view_count: number
  helpful_count: number
  not_helpful_count: number
}

export interface GlossaryTerm {
  id: string
  term: string
  slug: string
  short_definition: string
  full_description: string
  full_description_html: string
  wyckoff_phase: 'A' | 'B' | 'C' | 'D' | 'E' | null
  related_terms: string[]
  tags: string[]
  last_updated: string
}

export interface HelpSearchResult {
  article_id: string
  slug: string
  title: string
  category: string
  snippet: string
  rank: number
}

export interface HelpArticleListResponse {
  articles: HelpArticle[]
  total_count: number
}

export interface GlossaryResponse {
  terms: GlossaryTerm[]
  total_count: number
}

export interface SearchResponse {
  results: HelpSearchResult[]
  query: string
  total_count: number
}

export interface HelpFeedbackRequest {
  article_id: string
  helpful: boolean
  user_comment?: string
}

interface CacheEntry<T> {
  data: T
  timestamp: number
}

// ============================================================================
// Store Definition
// ============================================================================

export const useHelpStore = defineStore('help', () => {
  // State
  const articles = ref<HelpArticle[]>([])
  const glossaryTerms = ref<GlossaryTerm[]>([])
  const searchResults = ref<HelpSearchResult[]>([])
  const currentArticle = ref<HelpArticle | null>(null)
  const isLoading = ref(false)
  const error = ref<string | null>(null)

  // Cache management
  const cache = ref<{
    articles: CacheEntry<HelpArticle[]> | null
    glossary: CacheEntry<GlossaryTerm[]> | null
    articlesBySlug: Map<string, CacheEntry<HelpArticle>>
  }>({
    articles: null,
    glossary: null,
    articlesBySlug: new Map(),
  })

  // Cache duration constants
  const CACHE_DURATION_24H = 24 * 60 * 60 * 1000 // 24 hours
  const CACHE_DURATION_INDEFINITE = Infinity // Never expires

  // ============================================================================
  // Helper Functions
  // ============================================================================

  function isCacheValid<T>(
    cacheEntry: CacheEntry<T> | null,
    duration: number
  ): boolean {
    if (!cacheEntry) return false
    const age = Date.now() - cacheEntry.timestamp
    return age < duration
  }

  function setCacheEntry<T>(data: T): CacheEntry<T> {
    return {
      data,
      timestamp: Date.now(),
    }
  }

  // ============================================================================
  // Actions
  // ============================================================================

  /**
   * Fetch help articles with optional filtering
   * Cache duration: 24 hours
   */
  const fetchArticles = async (
    category: 'GLOSSARY' | 'FAQ' | 'TUTORIAL' | 'REFERENCE' | 'ALL' = 'ALL',
    limit: number = 50,
    offset: number = 0
  ) => {
    // Check cache (only for "ALL" category to keep it simple)
    if (
      category === 'ALL' &&
      isCacheValid(cache.value.articles, CACHE_DURATION_24H)
    ) {
      articles.value = cache.value.articles!.data
      return
    }

    isLoading.value = true
    error.value = null

    try {
      const response = await apiClient.get<HelpArticleListResponse>(
        '/help/articles',
        { category, limit, offset }
      )

      articles.value = response.articles

      // Cache the results (only for "ALL" category)
      if (category === 'ALL') {
        cache.value.articles = setCacheEntry(response.articles)
      }
    } catch (e) {
      error.value = e instanceof Error ? e.message : 'Failed to fetch articles'
      console.error('Error fetching help articles:', e)
    } finally {
      isLoading.value = false
    }
  }

  /**
   * Fetch a single article by slug and set as currentArticle
   */
  const fetchArticle = async (slug: string) => {
    // Check cache
    const cachedArticle = cache.value.articlesBySlug.get(slug)
    if (isCacheValid(cachedArticle || null, CACHE_DURATION_24H)) {
      currentArticle.value = cachedArticle!.data
      return
    }

    isLoading.value = true
    error.value = null

    try {
      const article = await apiClient.get<HelpArticle>(`/help/articles/${slug}`)
      currentArticle.value = article

      // Cache the article
      cache.value.articlesBySlug.set(slug, setCacheEntry(article))
    } catch (e) {
      error.value = e instanceof Error ? e.message : 'Failed to fetch article'
      console.error('Error fetching article:', e)
      currentArticle.value = null
    } finally {
      isLoading.value = false
    }
  }

  /**
   * Search help content with full-text search
   */
  const searchHelp = async (query: string, limit: number = 20) => {
    if (!query || query.trim().length === 0) {
      searchResults.value = []
      return
    }

    isLoading.value = true
    error.value = null

    try {
      const response = await apiClient.get<SearchResponse>('/help/search', {
        q: query,
        limit,
      })

      searchResults.value = response.results
    } catch (e) {
      error.value =
        e instanceof Error ? e.message : 'Failed to search help content'
      console.error('Error searching help:', e)
      searchResults.value = []
    } finally {
      isLoading.value = false
    }
  }

  /**
   * Fetch glossary terms with optional phase filtering
   * Cache duration: Indefinite (reload only on manual refresh)
   */
  const fetchGlossary = async (wyckoffPhase?: 'A' | 'B' | 'C' | 'D' | 'E') => {
    // Check cache (only for full glossary without phase filter)
    if (
      !wyckoffPhase &&
      isCacheValid(cache.value.glossary, CACHE_DURATION_INDEFINITE)
    ) {
      glossaryTerms.value = cache.value.glossary!.data
      return
    }

    isLoading.value = true
    error.value = null

    try {
      const params: { wyckoff_phase?: string } = {}
      if (wyckoffPhase) {
        params.wyckoff_phase = wyckoffPhase
      }

      const response = await apiClient.get<GlossaryResponse>(
        '/help/glossary',
        params
      )

      glossaryTerms.value = response.terms

      // Cache the results (only for full glossary)
      if (!wyckoffPhase) {
        cache.value.glossary = setCacheEntry(response.terms)
      }
    } catch (e) {
      error.value = e instanceof Error ? e.message : 'Failed to fetch glossary'
      console.error('Error fetching glossary:', e)
    } finally {
      isLoading.value = false
    }
  }

  /**
   * Submit feedback for an article
   */
  const submitFeedback = async (
    articleId: string,
    helpful: boolean,
    comment?: string
  ) => {
    isLoading.value = true
    error.value = null

    try {
      const feedback: HelpFeedbackRequest = {
        article_id: articleId,
        helpful,
      }

      if (comment) {
        feedback.user_comment = comment
      }

      await apiClient.post('/help/feedback', feedback)

      // Invalidate article cache for this article
      const articleEntry = Array.from(
        cache.value.articlesBySlug.entries()
      ).find(([, entry]) => entry.data.id === articleId)
      if (articleEntry) {
        cache.value.articlesBySlug.delete(articleEntry[0])
      }

      return true
    } catch (e) {
      error.value = e instanceof Error ? e.message : 'Failed to submit feedback'
      console.error('Error submitting feedback:', e)
      return false
    } finally {
      isLoading.value = false
    }
  }

  // ============================================================================
  // Getters
  // ============================================================================

  /**
   * Get an article by slug from the articles array
   */
  const getArticleBySlug = computed(() => {
    return (slug: string) => {
      return articles.value.find((article) => article.slug === slug)
    }
  })

  /**
   * Get a glossary term by name (case-insensitive)
   */
  const getTermByName = computed(() => {
    return (term: string) => {
      const lowerTerm = term.toLowerCase()
      return glossaryTerms.value.find(
        (t) => t.term.toLowerCase() === lowerTerm || t.slug === lowerTerm
      )
    }
  })

  /**
   * Group articles by category
   */
  const articlesGroupedByCategory = computed(() => {
    const grouped: Record<string, HelpArticle[]> = {
      GLOSSARY: [],
      FAQ: [],
      TUTORIAL: [],
      REFERENCE: [],
    }

    articles.value.forEach((article) => {
      if (grouped[article.category]) {
        grouped[article.category].push(article)
      }
    })

    return grouped
  })

  return {
    // State
    articles,
    glossaryTerms,
    searchResults,
    currentArticle,
    isLoading,
    error,

    // Actions
    fetchArticles,
    fetchArticle,
    searchHelp,
    fetchGlossary,
    submitFeedback,

    // Getters
    getArticleBySlug,
    getTermByName,
    articlesGroupedByCategory,
  }
})
