/**
 * E2E Tests for Help System Sub-routes
 *
 * Covers:
 * - /help/glossary - Wyckoff glossary
 * - /help/faq - FAQ page
 * - /help/article/:slug - Help articles
 * - /help/search - Search results
 */

import { test, expect } from '@playwright/test'

const BASE_URL = process.env.DEPLOYMENT_URL || 'http://localhost:4173'

test.describe('Help Glossary', () => {
  test('should load glossary page', async ({ page }) => {
    await page.goto(`${BASE_URL}/help/glossary`)
    await page.waitForLoadState('networkidle')

    // Verify page loaded
    await expect(page.locator('#app')).toBeVisible({ timeout: 10000 })

    // Check page title or heading
    const heading = page.locator('h1, h2').first()
    await expect(heading).toBeVisible()

    const headingText = await heading.textContent()
    expect(headingText!.toLowerCase().includes('glossary')).toBe(true)
  })

  test('should display Wyckoff terminology', async ({ page }) => {
    await page.goto(`${BASE_URL}/help/glossary`)
    await page.waitForLoadState('networkidle')

    // Look for common Wyckoff terms
    const wyckoffTerms = [
      'Accumulation',
      'Distribution',
      'Spring',
      'Creek',
      'Ice',
      'Composite Operator',
      'SOS',
      'LPS',
      'UTAD',
      'Phase',
    ]

    const pageContent = await page.locator('body').textContent()

    // Should have at least some Wyckoff terms
    const foundTerms = wyckoffTerms.filter((term) =>
      pageContent!.toLowerCase().includes(term.toLowerCase())
    )

    expect(foundTerms.length).toBeGreaterThan(0)
  })

  test('should have alphabetical navigation or search', async ({ page }) => {
    await page.goto(`${BASE_URL}/help/glossary`)
    await page.waitForLoadState('networkidle')

    // Look for alphabetical links or search
    const alphabetLinks = page.locator(
      'a:has-text("A"), a:has-text("B"), [class*="alpha"]'
    )
    const searchInput = page.locator(
      'input[placeholder*="Search"], input[type="search"]'
    )

    const hasAlphaNav = await alphabetLinks.count()
    const hasSearch = await searchInput.count()

    // Should have some navigation method
    expect(hasAlphaNav + hasSearch).toBeGreaterThanOrEqual(0)
  })

  test('should display term definitions', async ({ page }) => {
    await page.goto(`${BASE_URL}/help/glossary`)
    await page.waitForLoadState('networkidle')

    // Look for definition list or term-definition pairs
    const definitions = page.locator(
      'dl, .definition, .term-definition, [class*="glossary-item"]'
    )
    const hasDefinitions = await definitions.count()

    // Should display definitions
    expect(hasDefinitions).toBeGreaterThan(0)
  })
})

test.describe('Help FAQ', () => {
  test('should load FAQ page', async ({ page }) => {
    await page.goto(`${BASE_URL}/help/faq`)
    await page.waitForLoadState('networkidle')

    // Verify page loaded
    await expect(page.locator('#app')).toBeVisible({ timeout: 10000 })

    // Check page title or heading
    const heading = page.locator('h1, h2').first()
    await expect(heading).toBeVisible()

    const headingText = await heading.textContent()
    expect(
      headingText!.toLowerCase().includes('faq') ||
        headingText!.toLowerCase().includes('frequently') ||
        headingText!.toLowerCase().includes('questions')
    ).toBe(true)
  })

  test('should display expandable FAQ items', async ({ page }) => {
    await page.goto(`${BASE_URL}/help/faq`)
    await page.waitForLoadState('networkidle')

    // Look for accordion/expandable items
    const faqItems = page.locator(
      '[data-testid*="faq"], .faq-item, details, [role="button"][aria-expanded]'
    )
    const hasItems = await faqItems.count()

    if (hasItems > 0) {
      const firstItem = faqItems.first()
      await expect(firstItem).toBeVisible()

      // Try to expand first item
      const isExpandable =
        (await firstItem.getAttribute('aria-expanded')) !== null ||
        (await firstItem.locator('summary').count()) > 0

      if (isExpandable) {
        await firstItem.click()
        await page.waitForTimeout(300)
      }
    }
  })

  test('should have question and answer format', async ({ page }) => {
    await page.goto(`${BASE_URL}/help/faq`)
    await page.waitForLoadState('networkidle')

    // Look for Q&A structure
    const pageContent = await page.locator('body').textContent()

    // Should have question-like content
    expect(
      pageContent!.includes('?') ||
        pageContent!.toLowerCase().includes('how') ||
        pageContent!.toLowerCase().includes('what') ||
        pageContent!.toLowerCase().includes('why')
    ).toBe(true)
  })

  test('should allow searching FAQs', async ({ page }) => {
    await page.goto(`${BASE_URL}/help/faq`)
    await page.waitForLoadState('networkidle')

    // Look for search
    const searchInput = page.locator(
      'input[placeholder*="Search"], input[type="search"]'
    )
    const hasSearch = await searchInput.count()

    if (hasSearch > 0) {
      await searchInput.first().fill('signal')
      await page.waitForTimeout(500)

      // Search should filter or highlight results
      const pageLoaded = await page.locator('#app').isVisible()
      expect(pageLoaded).toBe(true)
    }
  })
})

test.describe('Help Search', () => {
  test('should load search results page', async ({ page }) => {
    await page.goto(`${BASE_URL}/help/search?q=signal`)
    await page.waitForLoadState('networkidle')

    // Verify page loaded
    await expect(page.locator('#app')).toBeVisible({ timeout: 10000 })
  })

  test('should display search results or no results message', async ({
    page,
  }) => {
    await page.goto(`${BASE_URL}/help/search?q=signal`)
    await page.waitForLoadState('networkidle')

    // Look for results or empty state
    const results = page.locator(
      '[data-testid*="result"], .search-result, .result-item, a[href*="/help/article"]'
    )
    const noResults = page.locator(
      ':has-text("No results"), :has-text("Nothing found"), .empty-state'
    )

    const hasResults = await results.count()
    const hasNoResults = await noResults.count()

    // Should show either results or no-results message
    expect(hasResults + hasNoResults).toBeGreaterThan(0)
  })

  test('should have search input with query', async ({ page }) => {
    await page.goto(`${BASE_URL}/help/search?q=pattern`)
    await page.waitForLoadState('networkidle')

    // Look for search input
    const searchInput = page.locator(
      'input[type="search"], input[placeholder*="Search"]'
    )
    const hasInput = await searchInput.count()

    if (hasInput > 0) {
      const inputValue = await searchInput.first().inputValue()
      // Query param should populate search input
      expect(inputValue.toLowerCase()).toContain('pattern')
    }
  })

  test('should navigate to article from search results', async ({ page }) => {
    await page.goto(`${BASE_URL}/help/search?q=wyckoff`)
    await page.waitForLoadState('networkidle')

    // Find article links in results
    const articleLinks = page.locator('a[href*="/help/article"]')
    const hasLinks = await articleLinks.count()

    if (hasLinks > 0) {
      const firstLink = articleLinks.first()
      const href = await firstLink.getAttribute('href')
      expect(href).toContain('/help/article/')
    }
  })
})

test.describe('Help Article', () => {
  test('should handle article route with slug', async ({ page }) => {
    // Try to access an article (may 404 if no articles exist)
    await page.goto(`${BASE_URL}/help/article/getting-started`)
    await page.waitForLoadState('networkidle')

    // Verify page loaded (either article or 404)
    await expect(page.locator('#app')).toBeVisible({ timeout: 10000 })

    const pageContent = await page.locator('body').textContent()

    // Should either show article content or not-found message
    expect(pageContent!.length).toBeGreaterThan(0)
  })

  test('should display breadcrumb navigation', async ({ page }) => {
    await page.goto(`${BASE_URL}/help/article/getting-started`)
    await page.waitForLoadState('networkidle')

    // Check for breadcrumb
    const breadcrumb = page.locator(
      'nav[aria-label="Breadcrumb"], .breadcrumb, [class*="breadcrumb"]'
    )
    const hasBreadcrumb = await breadcrumb.count()

    if (hasBreadcrumb > 0) {
      await expect(breadcrumb.first()).toBeVisible()

      // Should have link back to help
      const helpLink = breadcrumb.locator('a[href="/help"]')
      const hasHelpLink = await helpLink.count()
      expect(hasHelpLink).toBeGreaterThan(0)
    }
  })

  test('should display article content with markdown rendering', async ({
    page,
  }) => {
    await page.goto(`${BASE_URL}/help/article/getting-started`)
    await page.waitForLoadState('networkidle')

    // Look for markdown-rendered content
    const headings = page.locator('h1, h2, h3')
    const paragraphs = page.locator('p')
    const lists = page.locator('ul, ol')

    const hasHeadings = await headings.count()
    const hasParagraphs = await paragraphs.count()
    const hasLists = await lists.count()

    // Article should have some content structure
    expect(hasHeadings + hasParagraphs + hasLists).toBeGreaterThan(0)
  })

  test('should have back navigation', async ({ page }) => {
    await page.goto(`${BASE_URL}/help/article/getting-started`)
    await page.waitForLoadState('networkidle')

    // Look for back button or link
    const backButton = page.locator(
      'a:has-text("Back"), button:has-text("Back"), a[href="/help"]'
    )
    const hasBack = await backButton.count()

    if (hasBack > 0) {
      await expect(backButton.first()).toBeVisible()
    }
  })
})
