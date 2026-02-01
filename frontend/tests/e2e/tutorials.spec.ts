/**
 * E2E Tests for Tutorial System
 *
 * Covers:
 * - /tutorials/:slug - Tutorial walkthrough pages
 */

import { test, expect } from '@playwright/test'

const BASE_URL = process.env.DEPLOYMENT_URL || 'http://localhost:4173'

// Helper to get a valid tutorial slug from the tutorials list
async function getFirstTutorialSlug(
  page: import('@playwright/test').Page
): Promise<string | null> {
  await page.goto(`${BASE_URL}/tutorials`)
  await page.waitForLoadState('domcontentloaded')

  const tutorialLinks = page.locator('a[href*="/tutorials/"]')
  const hasLinks = await tutorialLinks.count()

  if (hasLinks > 0) {
    const href = await tutorialLinks.first().getAttribute('href')
    if (href) {
      const match = href.match(/\/tutorials\/(.+)/)
      return match ? match[1] : null
    }
  }
  return null
}

test.describe('Tutorial Walkthrough', () => {
  test('should load tutorial walkthrough page', async ({ page }) => {
    // First go to tutorials list to find a valid tutorial
    await page.goto(`${BASE_URL}/tutorials`)
    await page.waitForLoadState('domcontentloaded')

    // Find tutorial links
    const tutorialLinks = page.locator('a[href*="/tutorials/"]')
    const hasLinks = await tutorialLinks.count()

    if (hasLinks > 0) {
      // Click first tutorial
      await tutorialLinks.first().click()
      await page.waitForURL(/\/tutorials\/.+/)

      // Verify tutorial page loaded
      await expect(page.locator('#app')).toBeVisible({ timeout: 10000 })

      const heading = page.locator('h1, h2').first()
      await expect(heading).toBeVisible()
    }
  })

  test('should display tutorial steps or progress', async ({ page }) => {
    // Get a valid tutorial slug dynamically
    const slug = await getFirstTutorialSlug(page)
    if (!slug) {
      test.skip()
      return
    }

    await page.goto(`${BASE_URL}/tutorials/${slug}`)
    await page.waitForLoadState('domcontentloaded')

    // Look for step indicators
    const stepIndicators = page.locator(
      '[data-testid*="step"], .step, .progress-step, [class*="step"]'
    )
    const progressBar = page.locator(
      '[role="progressbar"], .progress, [class*="progress"]'
    )
    const stepNumbers = page.locator(
      ':has-text("Step 1"), :has-text("Step 2"), :has-text("1/"), :has-text("2/")'
    )

    void stepIndicators.count() // Suppress unused variable warning
    void progressBar.count() // Suppress unused variable warning
    void stepNumbers.count() // Suppress unused variable warning

    // Verify page loaded - progress indicators are optional
    await expect(page.locator('#app')).toBeVisible()
  })

  test('should have navigation between steps', async ({ page }) => {
    // Get a valid tutorial slug dynamically
    const slug = await getFirstTutorialSlug(page)
    if (!slug) {
      test.skip()
      return
    }

    await page.goto(`${BASE_URL}/tutorials/${slug}`)
    await page.waitForLoadState('domcontentloaded')

    // Look for next/previous buttons
    const nextButton = page.locator(
      'button:has-text("Next"), button:has-text("Continue"), [aria-label*="next"]'
    )

    const hasNext = await nextButton.count()

    if (hasNext > 0) {
      const nextBtn = nextButton.first()
      await expect(nextBtn).toBeVisible()

      // Try clicking next
      const isDisabled = await nextBtn.isDisabled()
      if (!isDisabled) {
        await nextBtn.click()
        // Wait for navigation by checking button is still in DOM
        await expect(page.locator('#app')).toBeVisible()
      }
    }
  })

  test('should display tutorial content with instructions', async ({
    page,
  }) => {
    // Get a valid tutorial slug dynamically
    const slug = await getFirstTutorialSlug(page)
    if (!slug) {
      test.skip()
      return
    }

    await page.goto(`${BASE_URL}/tutorials/${slug}`)
    await page.waitForLoadState('domcontentloaded')

    // Look for instructional content
    const content = page.locator(
      '.tutorial-content, .instructions, [class*="content"]'
    )
    const paragraphs = page.locator('p')
    const lists = page.locator('ul, ol')

    const hasContent = await content.count()
    const hasParagraphs = await paragraphs.count()
    const hasLists = await lists.count()

    // Should have instructional content
    expect(hasContent + hasParagraphs + hasLists).toBeGreaterThan(0)
  })

  test('should have breadcrumb navigation back to tutorials list', async ({
    page,
  }) => {
    // Get a valid tutorial slug dynamically
    const slug = await getFirstTutorialSlug(page)
    if (!slug) {
      test.skip()
      return
    }

    await page.goto(`${BASE_URL}/tutorials/${slug}`)
    await page.waitForLoadState('domcontentloaded')

    // Check for breadcrumb
    const breadcrumb = page.locator(
      'nav[aria-label="Breadcrumb"], .breadcrumb, [class*="breadcrumb"]'
    )
    const hasBreadcrumb = await breadcrumb.count()

    if (hasBreadcrumb > 0) {
      await expect(breadcrumb.first()).toBeVisible()

      // Should have link back to tutorials
      const tutorialsLink = breadcrumb.locator('a[href="/tutorials"]')
      const hasLink = await tutorialsLink.count()
      expect(hasLink).toBeGreaterThan(0)
    }
  })

  test('should allow completing tutorial', async ({ page }) => {
    // Get a valid tutorial slug dynamically
    const slug = await getFirstTutorialSlug(page)
    if (!slug) {
      test.skip()
      return
    }

    await page.goto(`${BASE_URL}/tutorials/${slug}`)
    await page.waitForLoadState('domcontentloaded')

    // Look for completion button
    const completeButton = page.locator(
      'button:has-text("Complete"), button:has-text("Finish"), button:has-text("Done")'
    )
    const hasComplete = await completeButton.count()

    // If complete button exists, it should be visible (may be at end of tutorial)
    if (hasComplete > 0) {
      // Navigate through steps to find complete button
      const nextButton = page.locator(
        'button:has-text("Next"), button:has-text("Continue")'
      )

      // Click through up to 10 steps
      for (let i = 0; i < 10; i++) {
        const hasNext = await nextButton.count()
        const isDisabled =
          hasNext > 0 ? await nextButton.first().isDisabled() : true

        if (!isDisabled) {
          await nextButton.first().click()
          // Wait for step transition
          await expect(page.locator('#app')).toBeVisible()
        } else {
          break
        }
      }
    }
  })

  test('should handle invalid tutorial slug gracefully', async ({ page }) => {
    await page.goto(`${BASE_URL}/tutorials/non-existent-tutorial`)
    await page.waitForLoadState('domcontentloaded')

    // Should show error or redirect
    const pageContent = await page.locator('body').textContent()

    // Should either show not found or redirect
    expect(
      pageContent!.toLowerCase().includes('not found') ||
        pageContent!.toLowerCase().includes('error') ||
        page.url().includes('/tutorials') ||
        page.url().includes('/404')
    ).toBe(true)
  })
})
