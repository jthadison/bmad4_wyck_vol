/**
 * Help Store Unit Tests (Story 11.8a - Task 10)
 *
 * Tests for help store actions, getters, and caching behavior.
 */

import { describe, it, expect, beforeEach, vi } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { useHelpStore } from '@/stores/helpStore'
import type {
  HelpArticle,
  GlossaryTerm,
  HelpArticleListResponse,
  GlossaryResponse,
  SearchResponse,
} from '@/stores/helpStore'
import * as api from '@/services/api'

// Mock the API client
vi.mock('@/services/api', () => ({
  apiClient: {
    get: vi.fn(),
    post: vi.fn(),
  },
}))

describe('useHelpStore', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
  })

  describe('fetchArticles', () => {
    it('should fetch articles successfully', async () => {
      const mockArticles: HelpArticle[] = [
        {
          id: '1',
          slug: 'test-article',
          title: 'Test Article',
          content_markdown: '# Test',
          content_html: '<h1>Test</h1>',
          category: 'FAQ',
          tags: ['test'],
          keywords: 'test keywords',
          last_updated: '2024-03-13T10:00:00Z',
          view_count: 10,
          helpful_count: 5,
          not_helpful_count: 1,
        },
      ]

      const mockResponse: HelpArticleListResponse = {
        articles: mockArticles,
        total_count: 1,
      }

      vi.spyOn(api.apiClient, 'get').mockResolvedValue(mockResponse)

      const store = useHelpStore()
      await store.fetchArticles('ALL', 50, 0)

      expect(store.articles).toEqual(mockArticles)
      expect(store.isLoading).toBe(false)
      expect(store.error).toBeNull()
      expect(api.apiClient.get).toHaveBeenCalledWith('/help/articles', {
        category: 'ALL',
        limit: 50,
        offset: 0,
      })
    })

    it('should use cache for subsequent requests', async () => {
      const mockArticles: HelpArticle[] = [
        {
          id: '1',
          slug: 'test-article',
          title: 'Test Article',
          content_markdown: '# Test',
          content_html: '<h1>Test</h1>',
          category: 'FAQ',
          tags: ['test'],
          keywords: 'test keywords',
          last_updated: '2024-03-13T10:00:00Z',
          view_count: 10,
          helpful_count: 5,
          not_helpful_count: 1,
        },
      ]

      const mockResponse: HelpArticleListResponse = {
        articles: mockArticles,
        total_count: 1,
      }

      vi.spyOn(api.apiClient, 'get').mockResolvedValue(mockResponse)

      const store = useHelpStore()

      // First call - should hit API
      await store.fetchArticles('ALL')
      expect(api.apiClient.get).toHaveBeenCalledTimes(1)

      // Second call - should use cache
      await store.fetchArticles('ALL')
      expect(api.apiClient.get).toHaveBeenCalledTimes(1)
      expect(store.articles).toEqual(mockArticles)
    })

    it('should handle errors gracefully', async () => {
      vi.spyOn(api.apiClient, 'get').mockRejectedValue(
        new Error('Network error')
      )

      const store = useHelpStore()
      await store.fetchArticles()

      expect(store.articles).toEqual([])
      expect(store.error).toBe('Network error')
      expect(store.isLoading).toBe(false)
    })
  })

  describe('fetchArticle', () => {
    it('should fetch a single article by slug', async () => {
      const mockArticle: HelpArticle = {
        id: '1',
        slug: 'spring-pattern',
        title: 'Spring Pattern',
        content_markdown: '# Spring Pattern',
        content_html: '<h1>Spring Pattern</h1>',
        category: 'GLOSSARY',
        tags: ['pattern'],
        keywords: 'spring wyckoff',
        last_updated: '2024-03-13T10:00:00Z',
        view_count: 50,
        helpful_count: 20,
        not_helpful_count: 2,
      }

      vi.spyOn(api.apiClient, 'get').mockResolvedValue(mockArticle)

      const store = useHelpStore()
      await store.fetchArticle('spring-pattern')

      expect(store.currentArticle).toEqual(mockArticle)
      expect(api.apiClient.get).toHaveBeenCalledWith(
        '/help/articles/spring-pattern'
      )
    })

    it('should handle article not found', async () => {
      vi.spyOn(api.apiClient, 'get').mockRejectedValue(
        new Error('Article not found')
      )

      const store = useHelpStore()
      await store.fetchArticle('nonexistent')

      expect(store.currentArticle).toBeNull()
      expect(store.error).toBe('Article not found')
    })
  })

  describe('searchHelp', () => {
    it('should search help content successfully', async () => {
      const mockResults: SearchResponse = {
        results: [
          {
            article_id: '1',
            slug: 'spring-pattern',
            title: 'Spring Pattern',
            category: 'GLOSSARY',
            snippet: 'A <mark>Spring</mark> is a price move...',
            rank: 0.85,
          },
        ],
        query: 'spring',
        total_count: 1,
      }

      vi.spyOn(api.apiClient, 'get').mockResolvedValue(mockResults)

      const store = useHelpStore()
      await store.searchHelp('spring')

      expect(store.searchResults).toEqual(mockResults.results)
      expect(api.apiClient.get).toHaveBeenCalledWith('/help/search', {
        q: 'spring',
        limit: 20,
      })
    })

    it('should clear results for empty query', async () => {
      const store = useHelpStore()
      await store.searchHelp('')

      expect(store.searchResults).toEqual([])
      expect(api.apiClient.get).not.toHaveBeenCalled()
    })

    it('should handle search errors', async () => {
      vi.spyOn(api.apiClient, 'get').mockRejectedValue(
        new Error('Search failed')
      )

      const store = useHelpStore()
      await store.searchHelp('test query')

      expect(store.searchResults).toEqual([])
      expect(store.error).toBe('Search failed')
    })
  })

  describe('fetchGlossary', () => {
    it('should fetch all glossary terms', async () => {
      const mockTerms: GlossaryTerm[] = [
        {
          id: '1',
          term: 'Spring',
          slug: 'spring',
          short_definition: 'A price move below support',
          full_description: 'Full description here',
          full_description_html: '<p>Full description here</p>',
          wyckoff_phase: 'C',
          related_terms: ['utad', 'creek'],
          tags: ['pattern'],
          last_updated: '2024-03-13T10:00:00Z',
        },
      ]

      const mockResponse: GlossaryResponse = {
        terms: mockTerms,
        total_count: 1,
      }

      vi.spyOn(api.apiClient, 'get').mockResolvedValue(mockResponse)

      const store = useHelpStore()
      await store.fetchGlossary()

      expect(store.glossaryTerms).toEqual(mockTerms)
      expect(api.apiClient.get).toHaveBeenCalledWith('/help/glossary', {})
    })

    it('should filter by Wyckoff phase', async () => {
      const mockTerms: GlossaryTerm[] = [
        {
          id: '1',
          term: 'Spring',
          slug: 'spring',
          short_definition: 'A price move below support',
          full_description: 'Full description here',
          full_description_html: '<p>Full description here</p>',
          wyckoff_phase: 'C',
          related_terms: [],
          tags: ['pattern'],
          last_updated: '2024-03-13T10:00:00Z',
        },
      ]

      const mockResponse: GlossaryResponse = {
        terms: mockTerms,
        total_count: 1,
      }

      vi.spyOn(api.apiClient, 'get').mockResolvedValue(mockResponse)

      const store = useHelpStore()
      await store.fetchGlossary('C')

      expect(api.apiClient.get).toHaveBeenCalledWith('/help/glossary', {
        wyckoff_phase: 'C',
      })
    })

    it('should use indefinite cache for full glossary', async () => {
      const mockTerms: GlossaryTerm[] = [
        {
          id: '1',
          term: 'Spring',
          slug: 'spring',
          short_definition: 'A price move below support',
          full_description: 'Full description here',
          full_description_html: '<p>Full description here</p>',
          wyckoff_phase: 'C',
          related_terms: [],
          tags: ['pattern'],
          last_updated: '2024-03-13T10:00:00Z',
        },
      ]

      const mockResponse: GlossaryResponse = {
        terms: mockTerms,
        total_count: 1,
      }

      vi.spyOn(api.apiClient, 'get').mockResolvedValue(mockResponse)

      const store = useHelpStore()

      // First call
      await store.fetchGlossary()
      expect(api.apiClient.get).toHaveBeenCalledTimes(1)

      // Second call - should use cache
      await store.fetchGlossary()
      expect(api.apiClient.get).toHaveBeenCalledTimes(1)
    })
  })

  describe('submitFeedback', () => {
    it('should submit feedback successfully', async () => {
      vi.spyOn(api.apiClient, 'post').mockResolvedValue({ success: true })

      const store = useHelpStore()
      const result = await store.submitFeedback(
        'article-123',
        true,
        'Great article!'
      )

      expect(result).toBe(true)
      expect(api.apiClient.post).toHaveBeenCalledWith('/help/feedback', {
        article_id: 'article-123',
        helpful: true,
        user_comment: 'Great article!',
      })
    })

    it('should handle feedback submission errors', async () => {
      vi.spyOn(api.apiClient, 'post').mockRejectedValue(
        new Error('Submission failed')
      )

      const store = useHelpStore()
      const result = await store.submitFeedback('article-123', false)

      expect(result).toBe(false)
      expect(store.error).toBe('Submission failed')
    })
  })

  describe('getters', () => {
    it('getArticleBySlug should find article by slug', async () => {
      const mockArticles: HelpArticle[] = [
        {
          id: '1',
          slug: 'test-article',
          title: 'Test Article',
          content_markdown: '# Test',
          content_html: '<h1>Test</h1>',
          category: 'FAQ',
          tags: ['test'],
          keywords: 'test',
          last_updated: '2024-03-13T10:00:00Z',
          view_count: 10,
          helpful_count: 5,
          not_helpful_count: 1,
        },
      ]

      vi.spyOn(api.apiClient, 'get').mockResolvedValue({
        articles: mockArticles,
        total_count: 1,
      })

      const store = useHelpStore()
      await store.fetchArticles()

      const article = store.getArticleBySlug('test-article')
      expect(article).toEqual(mockArticles[0])
    })

    it('getTermByName should find glossary term by name', async () => {
      const mockTerms: GlossaryTerm[] = [
        {
          id: '1',
          term: 'Spring',
          slug: 'spring',
          short_definition: 'Test definition',
          full_description: 'Full description',
          full_description_html: '<p>Full description</p>',
          wyckoff_phase: 'C',
          related_terms: [],
          tags: [],
          last_updated: '2024-03-13T10:00:00Z',
        },
      ]

      vi.spyOn(api.apiClient, 'get').mockResolvedValue({
        terms: mockTerms,
        total_count: 1,
      })

      const store = useHelpStore()
      await store.fetchGlossary()

      const term = store.getTermByName('Spring')
      expect(term).toEqual(mockTerms[0])
    })

    it('articlesGroupedByCategory should group articles correctly', async () => {
      const mockArticles: HelpArticle[] = [
        {
          id: '1',
          slug: 'faq-1',
          title: 'FAQ 1',
          content_markdown: '# FAQ',
          content_html: '<h1>FAQ</h1>',
          category: 'FAQ',
          tags: [],
          keywords: '',
          last_updated: '2024-03-13T10:00:00Z',
          view_count: 0,
          helpful_count: 0,
          not_helpful_count: 0,
        },
        {
          id: '2',
          slug: 'glossary-1',
          title: 'Glossary 1',
          content_markdown: '# Glossary',
          content_html: '<h1>Glossary</h1>',
          category: 'GLOSSARY',
          tags: [],
          keywords: '',
          last_updated: '2024-03-13T10:00:00Z',
          view_count: 0,
          helpful_count: 0,
          not_helpful_count: 0,
        },
      ]

      vi.spyOn(api.apiClient, 'get').mockResolvedValue({
        articles: mockArticles,
        total_count: 2,
      })

      const store = useHelpStore()
      await store.fetchArticles()

      const grouped = store.articlesGroupedByCategory
      expect(grouped.FAQ).toHaveLength(1)
      expect(grouped.GLOSSARY).toHaveLength(1)
      expect(grouped.TUTORIAL).toHaveLength(0)
    })
  })
})
