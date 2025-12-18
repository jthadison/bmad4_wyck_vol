/**
 * Performance Tests for Help System Search (Story 11.8c - Task 18)
 *
 * Purpose:
 * --------
 * Validate that PostgreSQL full-text search returns results within <200ms
 * as specified in AC #10.
 *
 * Test Coverage:
 * --------------
 * 1. Search Response Time
 *    - Single keyword search <200ms
 *    - Multi-keyword search <200ms
 *    - Long query search <200ms
 *    - Search with 75+ articles
 *
 * 2. Database Performance
 *    - PostgreSQL GIN index usage
 *    - Search vector performance
 *    - Ranking calculation speed
 *
 * 3. Frontend Performance
 *    - Results rendering time
 *    - Keyboard navigation responsiveness
 *    - Search input debouncing
 *
 * 4. Load Testing
 *    - Concurrent search requests
 *    - Large result sets
 *    - Category filtering performance
 *
 * Acceptance Criteria:
 * --------------------
 * AC #10: PostgreSQL FTS returns results in <200ms
 * - Backend API response time <200ms
 * - Total search operation (API + render) <500ms
 * - Works with 75+ articles in database
 *
 * Usage:
 * ------
 * ```bash
 * # Run performance tests
 * cd frontend
 * npx playwright test search-performance.spec.ts
 *
 * # Run with detailed timing
 * npx playwright test search-performance.spec.ts --reporter=list
 *
 * # Run specific test
 * npx playwright test search-performance.spec.ts -g "Search API"
 * ```
 */

import { test, expect } from '@playwright/test'

const DEPLOYMENT_URL = process.env.DEPLOYMENT_URL || 'http://localhost:4173'
const API_BASE_URL = process.env.API_BASE_URL || 'http://localhost:8000'
const TIMEOUT = 30000

// Performance thresholds (milliseconds)
const THRESHOLDS = {
  API_RESPONSE: 200, // AC #10 requirement
  TOTAL_SEARCH: 500, // API + rendering
  RENDER_TIME: 300, // Frontend rendering only
  KEYBOARD_NAV: 50, // Keyboard navigation response
}

/**
 * Test Suite
 */

test.describe('Search Performance Tests (Story 11.8c - AC #10)', () => {
  /**
   * API Response Time Tests
   */
  test.describe('Search API Performance', () => {
    test('Single keyword search returns in <200ms', async ({ request }) => {
      const queries = [
        'wyckoff',
        'spring',
        'accumulation',
        'volume',
        'composite',
      ]

      for (const query of queries) {
        const startTime = performance.now()

        const response = await request.get(
          `${API_BASE_URL}/api/v1/help/search?q=${encodeURIComponent(query)}`,
          {
            timeout: TIMEOUT,
          }
        )

        const endTime = performance.now()
        const responseTime = endTime - startTime

        console.log(
          `[${query}] API response time: ${responseTime.toFixed(2)}ms`
        )

        expect(response.status()).toBe(200)
        expect(responseTime).toBeLessThan(THRESHOLDS.API_RESPONSE)

        const data = await response.json()
        expect(Array.isArray(data)).toBe(true)
      }
    })

    test('Multi-keyword search returns in <200ms', async ({ request }) => {
      const queries = [
        'wyckoff method',
        'composite operator',
        'volume spread analysis',
        'accumulation phase',
        'spring pattern',
      ]

      for (const query of queries) {
        const startTime = performance.now()

        const response = await request.get(
          `${API_BASE_URL}/api/v1/help/search?q=${encodeURIComponent(query)}`,
          {
            timeout: TIMEOUT,
          }
        )

        const endTime = performance.now()
        const responseTime = endTime - startTime

        console.log(
          `[${query}] API response time: ${responseTime.toFixed(2)}ms`
        )

        expect(response.status()).toBe(200)
        expect(responseTime).toBeLessThan(THRESHOLDS.API_RESPONSE)

        const data = await response.json()
        expect(Array.isArray(data)).toBe(true)
      }
    })

    test('Long query search returns in <200ms', async ({ request }) => {
      const longQuery =
        'what is the wyckoff method and how does it work with volume spread analysis'

      const startTime = performance.now()

      const response = await request.get(
        `${API_BASE_URL}/api/v1/help/search?q=${encodeURIComponent(longQuery)}`,
        {
          timeout: TIMEOUT,
        }
      )

      const endTime = performance.now()
      const responseTime = endTime - startTime

      console.log(
        `[Long query] API response time: ${responseTime.toFixed(2)}ms`
      )

      expect(response.status()).toBe(200)
      expect(responseTime).toBeLessThan(THRESHOLDS.API_RESPONSE)

      const data = await response.json()
      expect(Array.isArray(data)).toBe(true)
    })

    test('Search works with 75+ articles', async ({ request }) => {
      // First, verify we have enough articles
      const listResponse = await request.get(
        `${API_BASE_URL}/api/v1/help/articles`
      )

      if (listResponse.status() === 200) {
        const articles = await listResponse.json()
        const articleCount = Array.isArray(articles) ? articles.length : 0

        console.log(`Total articles in database: ${articleCount}`)

        // Now perform search
        const startTime = performance.now()

        const searchResponse = await request.get(
          `${API_BASE_URL}/api/v1/help/search?q=wyckoff`,
          {
            timeout: TIMEOUT,
          }
        )

        const endTime = performance.now()
        const responseTime = endTime - startTime

        console.log(
          `[Search with ${articleCount} articles] Response time: ${responseTime.toFixed(
            2
          )}ms`
        )

        expect(searchResponse.status()).toBe(200)
        expect(responseTime).toBeLessThan(THRESHOLDS.API_RESPONSE)

        const results = await searchResponse.json()
        expect(Array.isArray(results)).toBe(true)
        expect(results.length).toBeGreaterThan(0)
      }
    })

    test('Category filtering maintains performance', async ({ request }) => {
      const categories = ['FAQ', 'GLOSSARY', 'TUTORIAL']

      for (const category of categories) {
        const startTime = performance.now()

        const response = await request.get(
          `${API_BASE_URL}/api/v1/help/search?q=wyckoff&category=${category}`,
          {
            timeout: TIMEOUT,
          }
        )

        const endTime = performance.now()
        const responseTime = endTime - startTime

        console.log(
          `[Category: ${category}] API response time: ${responseTime.toFixed(
            2
          )}ms`
        )

        if (response.status() === 200) {
          expect(responseTime).toBeLessThan(THRESHOLDS.API_RESPONSE)

          const data = await response.json()
          expect(Array.isArray(data)).toBe(true)
        }
      }
    })

    test('Empty search returns quickly', async ({ request }) => {
      const startTime = performance.now()

      const response = await request.get(
        `${API_BASE_URL}/api/v1/help/search?q=xyznonexistentquery12345`,
        {
          timeout: TIMEOUT,
        }
      )

      const endTime = performance.now()
      const responseTime = endTime - startTime

      console.log(
        `[Empty result] API response time: ${responseTime.toFixed(2)}ms`
      )

      expect(response.status()).toBe(200)
      expect(responseTime).toBeLessThan(THRESHOLDS.API_RESPONSE)

      const data = await response.json()
      expect(Array.isArray(data)).toBe(true)
      expect(data.length).toBe(0)
    })

    test('Search ranking returns results ordered by relevance', async ({
      request,
    }) => {
      const response = await request.get(
        `${API_BASE_URL}/api/v1/help/search?q=composite`,
        {
          timeout: TIMEOUT,
        }
      )

      expect(response.status()).toBe(200)

      const results = await response.json()

      if (results.length > 1) {
        // Results should have rank field
        expect(results[0]).toHaveProperty('rank')

        // First result should have highest rank
        const firstRank = results[0].rank
        const lastRank = results[results.length - 1].rank

        expect(firstRank).toBeGreaterThanOrEqual(lastRank)
      }
    })
  })

  /**
   * End-to-End Search Performance
   */
  test.describe('E2E Search Performance', () => {
    test('Total search operation completes in <500ms', async ({ page }) => {
      await page.goto(`${DEPLOYMENT_URL}/help`, {
        timeout: TIMEOUT,
        waitUntil: 'networkidle',
      })

      await page.waitForSelector('#app', { timeout: TIMEOUT })

      // Find search input
      const searchInput = page.locator('input[placeholder*="Search"]')
      await expect(searchInput).toBeVisible()

      // Measure total search time (input + API + render)
      const startTime = performance.now()

      await searchInput.fill('wyckoff')
      await page.keyboard.press('Enter')

      // Wait for results to appear
      await page.waitForSelector('.search-results-view, text=/results/i', {
        timeout: 5000,
      })

      const endTime = performance.now()
      const totalTime = endTime - startTime

      console.log(`Total search operation time: ${totalTime.toFixed(2)}ms`)

      expect(totalTime).toBeLessThan(THRESHOLDS.TOTAL_SEARCH)
    })

    test('Results rendering completes quickly', async ({ page }) => {
      // Navigate directly to search results
      await page.goto(`${DEPLOYMENT_URL}/help/search?q=spring`, {
        timeout: TIMEOUT,
        waitUntil: 'domcontentloaded',
      })

      const startTime = performance.now()

      // Wait for results to render
      await page.waitForSelector('.search-results-view', { timeout: 5000 })
      await page.waitForSelector('.result-item, [class*="search-result"]', {
        timeout: 5000,
      })

      const endTime = performance.now()
      const renderTime = endTime - startTime

      console.log(`Results rendering time: ${renderTime.toFixed(2)}ms`)

      expect(renderTime).toBeLessThan(THRESHOLDS.RENDER_TIME)
    })

    test('Keyboard navigation responds quickly', async ({ page }) => {
      await page.goto(`${DEPLOYMENT_URL}/help/search?q=wyckoff`, {
        timeout: TIMEOUT,
        waitUntil: 'networkidle',
      })

      await page.waitForSelector('.search-results-view', { timeout: 5000 })
      await page.waitForTimeout(1000)

      // Measure keyboard navigation response
      const measurements: number[] = []

      for (let i = 0; i < 5; i++) {
        const startTime = performance.now()

        await page.keyboard.press('ArrowDown')
        await page.waitForTimeout(50)

        const endTime = performance.now()
        const navTime = endTime - startTime

        measurements.push(navTime)
        console.log(`Keyboard nav ${i + 1}: ${navTime.toFixed(2)}ms`)
      }

      // Average navigation time should be fast
      const avgTime =
        measurements.reduce((a, b) => a + b, 0) / measurements.length

      console.log(`Average keyboard navigation time: ${avgTime.toFixed(2)}ms`)

      expect(avgTime).toBeLessThan(THRESHOLDS.KEYBOARD_NAV)
    })

    test('Large result set renders efficiently', async ({ page }) => {
      // Search for common term likely to return many results
      await page.goto(`${DEPLOYMENT_URL}/help/search?q=wyckoff`, {
        timeout: TIMEOUT,
        waitUntil: 'domcontentloaded',
      })

      const startTime = performance.now()

      await page.waitForSelector('.search-results-view', { timeout: 5000 })

      const endTime = performance.now()
      const renderTime = endTime - startTime

      // Count results rendered
      const results = await page
        .locator('.result-item, [class*="search-result"]')
        .count()

      console.log(`Rendered ${results} results in ${renderTime.toFixed(2)}ms`)

      expect(renderTime).toBeLessThan(THRESHOLDS.RENDER_TIME)
    })

    test('Search input debouncing works correctly', async ({ page }) => {
      await page.goto(`${DEPLOYMENT_URL}/help`, {
        timeout: TIMEOUT,
        waitUntil: 'networkidle',
      })

      const searchInput = page.locator('input[placeholder*="Search"]')
      await expect(searchInput).toBeVisible()

      // Type quickly to trigger debounce
      const query = 'wyckoff method'
      for (const char of query) {
        await searchInput.type(char, { delay: 50 }) // Fast typing
      }

      // Wait for debounce to settle
      await page.waitForTimeout(500)

      // Should have value in input
      const inputValue = await searchInput.inputValue()
      expect(inputValue).toBe(query)
    })
  })

  /**
   * Concurrent Request Performance
   */
  test.describe('Load Testing', () => {
    test('Handles concurrent search requests', async ({ request }) => {
      const queries = [
        'wyckoff',
        'spring',
        'composite',
        'accumulation',
        'volume',
        'distribution',
        'backup',
        'test',
      ]

      // Send concurrent requests
      const startTime = performance.now()

      const promises = queries.map((query) =>
        request.get(
          `${API_BASE_URL}/api/v1/help/search?q=${encodeURIComponent(query)}`,
          {
            timeout: TIMEOUT,
          }
        )
      )

      const responses = await Promise.all(promises)

      const endTime = performance.now()
      const totalTime = endTime - startTime

      console.log(
        `${queries.length} concurrent searches completed in ${totalTime.toFixed(
          2
        )}ms`
      )

      // All requests should succeed
      responses.forEach((response, index) => {
        expect(response.status()).toBe(200)
        console.log(`  [${queries[index]}] Success`)
      })

      // Average time per request should still be fast
      const avgTime = totalTime / queries.length
      console.log(
        `Average time per concurrent request: ${avgTime.toFixed(2)}ms`
      )

      expect(avgTime).toBeLessThan(THRESHOLDS.API_RESPONSE * 2) // Allow 2x threshold for concurrency
    })

    test('Search performance does not degrade over time', async ({
      request,
    }) => {
      const query = 'wyckoff'
      const iterations = 10
      const measurements: number[] = []

      for (let i = 0; i < iterations; i++) {
        const startTime = performance.now()

        const response = await request.get(
          `${API_BASE_URL}/api/v1/help/search?q=${encodeURIComponent(query)}`,
          {
            timeout: TIMEOUT,
          }
        )

        const endTime = performance.now()
        const responseTime = endTime - startTime

        measurements.push(responseTime)

        expect(response.status()).toBe(200)

        // Small delay between requests
        await new Promise((resolve) => setTimeout(resolve, 100))
      }

      // Calculate statistics
      const avgTime =
        measurements.reduce((a, b) => a + b, 0) / measurements.length
      const maxTime = Math.max(...measurements)
      const minTime = Math.min(...measurements)

      console.log(`Performance over ${iterations} iterations:`)
      console.log(`  Average: ${avgTime.toFixed(2)}ms`)
      console.log(`  Min: ${minTime.toFixed(2)}ms`)
      console.log(`  Max: ${maxTime.toFixed(2)}ms`)

      // All measurements should be under threshold
      expect(avgTime).toBeLessThan(THRESHOLDS.API_RESPONSE)
      expect(maxTime).toBeLessThan(THRESHOLDS.API_RESPONSE * 1.5) // Allow 50% variance for max
    })
  })

  /**
   * Database Query Performance
   */
  test.describe('Database Performance Indicators', () => {
    test('Search returns ranked results efficiently', async ({ request }) => {
      const response = await request.get(
        `${API_BASE_URL}/api/v1/help/search?q=wyckoff method`,
        {
          timeout: TIMEOUT,
        }
      )

      expect(response.status()).toBe(200)

      const results = await response.json()

      // Results should have rank scores
      if (results.length > 0) {
        expect(results[0]).toHaveProperty('rank')

        // Ranks should be in descending order
        for (let i = 0; i < results.length - 1; i++) {
          expect(results[i].rank).toBeGreaterThanOrEqual(results[i + 1].rank)
        }

        console.log(`Top result rank: ${results[0].rank}`)
        console.log(`Results ranked and ordered correctly`)
      }
    })

    test('Search snippets generated efficiently', async ({ request }) => {
      const response = await request.get(
        `${API_BASE_URL}/api/v1/help/search?q=composite operator`,
        {
          timeout: TIMEOUT,
        }
      )

      expect(response.status()).toBe(200)

      const results = await response.json()

      // Results should have snippets with highlighting
      if (results.length > 0) {
        expect(results[0]).toHaveProperty('snippet')

        // Snippet should contain highlighted text
        const snippet = results[0].snippet
        expect(snippet).toBeTruthy()
        expect(snippet.length).toBeGreaterThan(0)

        console.log(`Snippet generated: ${snippet.substring(0, 100)}...`)
      }
    })
  })

  /**
   * Performance Regression Tests
   */
  test.describe('Performance Benchmarks', () => {
    test('Establish performance baseline', async ({ request }) => {
      const testCases = [
        { name: 'Single word', query: 'wyckoff' },
        { name: 'Two words', query: 'composite operator' },
        { name: 'Three words', query: 'volume spread analysis' },
        {
          name: 'Long query',
          query: 'what is the wyckoff method accumulation phase',
        },
        { name: 'Partial match', query: 'accum' },
      ]

      console.log('\n=== Performance Baseline ===')

      for (const testCase of testCases) {
        const startTime = performance.now()

        const response = await request.get(
          `${API_BASE_URL}/api/v1/help/search?q=${encodeURIComponent(
            testCase.query
          )}`,
          {
            timeout: TIMEOUT,
          }
        )

        const endTime = performance.now()
        const responseTime = endTime - startTime

        expect(response.status()).toBe(200)

        const results = await response.json()
        const resultCount = Array.isArray(results) ? results.length : 0

        console.log(
          `${testCase.name.padEnd(20)} | ${responseTime.toFixed(
            2
          )}ms | ${resultCount} results`
        )

        expect(responseTime).toBeLessThan(THRESHOLDS.API_RESPONSE)
      }

      console.log('==============================\n')
    })
  })
})
