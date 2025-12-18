# Story 11.8d: Implementation Guide

## Status: BLOCKED - Test Infrastructure Issue

**Blocker**: npm rollup dependency issue on Windows preventing test execution
**Workaround**: Manual implementation documented below
**DevOps Issue**: See [.ai/devops-issue-rollup.md](.ai/devops-issue-rollup.md)

---

## Completed Work

### ✅ Task 8: DOMPurify Integration

**Files Created:**
1. `frontend/src/utils/sanitize.ts` - Sanitization utility with DOMPurify
2. `frontend/src/utils/sanitize.spec.ts` - 30+ XSS prevention tests

**Package Installed:**
- `dompurify` and `@types/dompurify` added to `frontend/package.json`

---

## Remaining Implementation Tasks

### Task 9: Update FAQView.vue with DOMPurify

**File**: `frontend/src/components/help/FAQView.vue`

**Changes Required:**

1. **Add imports** (line 28-39):
```typescript
import { ref, computed, onMounted } from 'vue'
import { useHelpStore } from '@/stores/helpStore'
import { sanitizeHtml } from '@/utils/sanitize'  // ADD THIS
import type { HelpArticle } from '@/stores/helpStore'  // ADD THIS
import Accordion from 'primevue/accordion'
// ... rest of imports
```

2. **Update highlightSearchTerm function** (lines 66-75):
```typescript
/**
 * Highlights search terms in text with <mark> tags and sanitizes output
 * Story 11.8d: Added DOMPurify sanitization for defense-in-depth XSS protection
 */
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
```

3. **Add sanitizedContent function** (after highlightSearchTerm, before onMounted):
```typescript
/**
 * Returns sanitized HTML content for an article
 * Story 11.8d: Client-side sanitization as defense-in-depth (backend also sanitizes)
 */
const sanitizedContent = (article: HelpArticle): string => {
  return sanitizeHtml(article.content_html)
}
```

4. **Update template v-html** (line 182):
```vue
<!-- Before -->
<div class="article-content" v-html="article.content_html"></div>

<!-- After -->
<div class="article-content" v-html="sanitizedContent(article)"></div>
```

5. **Update header comment** (lines 1-26):
Add to Integration section:
```
Security (Story 11.8d):
----------------------
- Defense-in-depth XSS protection using DOMPurify client-side sanitization
- All v-html content is sanitized via sanitizeHtml() utility
- Backend sanitization (Python Bleach) + Frontend sanitization (DOMPurify)
```

6. **Update ESLint comment** (line 84 and 165):
```vue
<!-- eslint-disable vue/no-v-html -- Content sanitized by DOMPurify (Story 11.8d) -->
```

---

### Task 10: Update ArticleView.vue with DOMPurify

**File**: `frontend/src/components/help/ArticleView.vue`

**Changes Required:**

1. **Add import**:
```typescript
import { sanitizeHtml } from '@/utils/sanitize'
```

2. **Add computed property**:
```typescript
/**
 * Sanitized article HTML content
 * Story 11.8d: Client-side sanitization for defense-in-depth XSS protection
 */
const sanitizedArticleContent = computed(() => {
  if (!article.value) return ''
  return sanitizeHtml(article.value.content_html)
})
```

3. **Update template v-html**:
Find the line with `v-html="article.content_html"` and change to:
```vue
<div class="article-body" v-html="sanitizedArticleContent"></div>
```

4. **Update ESLint comments** with note about DOMPurify sanitization

---

### Task 11: Update SearchResults.vue with DOMPurify

**File**: `frontend/src/components/help/SearchResults.vue`

**Changes Required:**

1. **Add import**:
```typescript
import { sanitizeHtml } from '@/utils/sanitize'
```

2. **Add computed or method for sanitized excerpts** (if using v-html for excerpts):
```typescript
const getSanitizedExcerpt = (article: HelpArticle): string => {
  // If content already plain text, no sanitization needed
  // If using HTML excerpts, sanitize them
  return sanitizeHtml(article.excerpt_or_content_html)
}
```

3. **Update any v-html usage** in template with sanitized version

---

### Task 12: Add XSS Test Coverage to Component Tests

#### Task 12.1: FAQView.spec.ts

**File**: `frontend/tests/components/FAQView.spec.ts`

**Add test** (after existing tests, before closing describe block):
```typescript
it('should sanitize malicious HTML in FAQ content', async () => {
  const helpStore = useHelpStore()

  const maliciousArticle: HelpArticle = {
    id: '999',
    slug: 'xss-test',
    title: 'XSS Test',
    category: 'FAQ',
    content_html: '<p>Safe content</p><script>alert("XSS")</script>',
    content_markdown: 'Safe content',
    tags: [],
    keywords: '',
    last_updated: new Date().toISOString(),
    view_count: 0,
    helpful_count: 0,
    not_helpful_count: 0,
  }

  vi.spyOn(helpStore, 'fetchArticles').mockImplementation(async () => {
    helpStore.articles = [maliciousArticle]
    helpStore.isLoading = false
  })

  const wrapper = mount(FAQView, {
    global: {
      plugins: [pinia],
    },
  })

  await wrapper.vm.$nextTick()
  await wrapper.vm.$nextTick()

  const html = wrapper.html()
  expect(html).not.toContain('<script>')
  expect(html).not.toContain('alert')
  expect(html).toContain('Safe content')
})
```

#### Task 12.2: ArticleView.spec.ts

**File**: `frontend/tests/components/ArticleView.spec.ts`

**Add test**:
```typescript
it('should sanitize malicious HTML in article content', async () => {
  const maliciousArticle: HelpArticle = {
    id: '999',
    slug: 'xss-test-article',
    title: 'XSS Test Article',
    category: 'GUIDE',
    content_html: '<h1>Title</h1><script>fetch("/steal-data")</script><p>Content</p>',
    content_markdown: '# Title\n\nContent',
    tags: ['test'],
    keywords: 'test',
    last_updated: new Date().toISOString(),
    view_count: 0,
    helpful_count: 0,
    not_helpful_count: 0,
  }

  vi.spyOn(helpStore, 'fetchArticle').mockImplementation(async () => {
    return maliciousArticle
  })

  const wrapper = mount(ArticleView, {
    global: {
      plugins: [pinia, router],
    },
    props: {
      slug: 'xss-test-article',
    },
  })

  await wrapper.vm.$nextTick()
  await wrapper.vm.$nextTick()

  const html = wrapper.html()
  expect(html).not.toContain('<script>')
  expect(html).not.toContain('fetch')
  expect(html).toContain('Title')
  expect(html).toContain('Content')
})
```

---

### Task 13: Create Test Documentation

#### File 1: `docs/testing/async-testing-patterns.md`

```markdown
# Async Testing Patterns for Vue Components

## Overview
This guide documents best practices for testing asynchronous behavior in Vue 3 components using Vitest.

## Common Async Patterns

### 1. Using flushPromises()
```typescript
import { flushPromises } from '@vue/test-utils'

it('should wait for async data', async () => {
  const wrapper = mount(Component)

  // Trigger async action
  await wrapper.find('button').trigger('click')

  // Wait for all promises to resolve
  await flushPromises()

  // Now assertions will work
  expect(wrapper.text()).toContain('Expected text')
})
```

### 2. Using $nextTick()
```typescript
it('should wait for DOM updates', async () => {
  const wrapper = mount(Component)

  // Update reactive data
  wrapper.vm.someData = 'new value'

  // Wait for Vue to update DOM
  await wrapper.vm.$nextTick()

  expect(wrapper.text()).toContain('new value')
})
```

### 3. Multiple nextTick for Deep Updates
```typescript
it('should wait for nested component updates', async () => {
  const wrapper = mount(ParentComponent)

  // First tick: parent updates
  await wrapper.vm.$nextTick()

  // Second tick: child components update
  await wrapper.vm.$nextTick()

  expect(wrapper.findComponent(ChildComponent).exists()).toBe(true)
})
```

### 4. Testing PrimeVue Components
```typescript
it('should wait for PrimeVue Dialog to mount', async () => {
  const wrapper = mount(ComponentWithDialog)

  // PrimeVue components have async initialization
  await flushPromises()
  await wrapper.vm.$nextTick()

  const dialog = wrapper.findComponent(Dialog)
  expect(dialog.exists()).toBe(true)
})
```

### 5. Testing Store Actions
```typescript
it('should wait for store action to complete', async () => {
  const store = useMyStore()

  // Mock the API call
  vi.spyOn(api, 'fetchData').mockResolvedValue(mockData)

  // Call store action
  await store.fetchData()

  // Wait for reactive updates
  await flushPromises()

  expect(store.data).toEqual(mockData)
})
```

### 6. Custom waitFor Helper
```typescript
async function waitFor(condition: () => boolean, timeout = 1000) {
  const startTime = Date.now()

  while (!condition()) {
    if (Date.now() - startTime > timeout) {
      throw new Error('Timeout waiting for condition')
    }
    await new Promise(resolve => setTimeout(resolve, 50))
  }
}

it('should wait for conditional rendering', async () => {
  const wrapper = mount(Component)

  await waitFor(() => wrapper.find('.dynamic-element').exists())

  expect(wrapper.find('.dynamic-element').text()).toBe('Expected')
})
```

## Story 11.8d Test Fixes

### Issue: Tests failing due to async timing
**Root Cause**: Assertions running before component fully rendered

**Solution**:
1. Add `await flushPromises()` after API mocks
2. Use multiple `await wrapper.vm.$nextTick()` for nested updates
3. Mock store methods to return immediately
4. Wait for PrimeVue component initialization

### Example Fix
```typescript
// Before (FAILING)
it('should display FAQs', () => {
  helpStore.articles = mockFAQs
  const wrapper = mount(FAQView)

  expect(wrapper.findAll('.faq-item')).toHaveLength(3)
})

// After (PASSING)
it('should display FAQs', async () => {
  helpStore.articles = mockFAQs

  const wrapper = mount(FAQView)

  // Wait for component to mount
  await wrapper.vm.$nextTick()

  // Wait for PrimeVue Accordion to render
  await flushPromises()

  expect(wrapper.findAll('.faq-item')).toHaveLength(3)
})
```

## Best Practices

1. **Always await** async operations
2. **Use flushPromises()** after mocking API calls
3. **Use nextTick()** after updating reactive data
4. **Test one async operation at a time** for clarity
5. **Add descriptive comments** explaining why waits are needed
6. **Mock timers** when testing debounce/throttle
7. **Clean up** async operations in afterEach hooks

## References
- [Vue Test Utils Async Guide](https://test-utils.vuejs.org/guide/advanced/async-testing.html)
- [Vitest Async Matchers](https://vitest.dev/api/expect.html#async-matchers)
```

#### File 2: `docs/testing/component-testing-best-practices.md`

```markdown
# Component Testing Best Practices

## Setup and Teardown

### Proper beforeEach/afterEach
```typescript
import { setActivePinia, createPinia } from 'pinia'

describe('MyComponent', () => {
  let pinia: any

  beforeEach(() => {
    // Create fresh Pinia instance for each test
    pinia = createPinia()
    setActivePinia(pinia)

    // Reset mocks
    vi.clearAllMocks()
  })

  afterEach(() => {
    // Clean up any pending timers
    vi.clearAllTimers()
  })
})
```

## Mocking Stores

### Pattern 1: Direct State Manipulation
```typescript
const helpStore = useHelpStore()
helpStore.articles = mockArticles
helpStore.isLoading = false
```

### Pattern 2: Mock Actions
```typescript
const helpStore = useHelpStore()
vi.spyOn(helpStore, 'fetchArticles').mockImplementation(async () => {
  helpStore.articles = mockArticles
  helpStore.isLoading = false
})
```

## Testing v-html Content

```typescript
it('should render HTML content', () => {
  const wrapper = mount(Component)

  // Check raw HTML
  expect(wrapper.html()).toContain('<strong>Bold</strong>')

  // Check text content
  expect(wrapper.text()).toContain('Bold')
})
```

## Testing Keyboard Events

```typescript
it('should handle keyboard shortcuts', async () => {
  const wrapper = mount(Component)

  // Dispatch keyboard event
  await wrapper.find('input').trigger('keydown', { key: 'Enter' })

  await wrapper.vm.$nextTick()

  expect(wrapper.emitted('submit')).toBeTruthy()
})
```

## Testing PrimeVue Components

### Mocking PrimeVue
```typescript
vi.mock('primevue/dialog', () => ({
  default: {
    name: 'Dialog',
    template: '<div class="p-dialog"><slot /></div>',
    props: ['visible'],
  },
}))
```

### Testing PrimeVue Events
```typescript
it('should handle Dialog close', async () => {
  const wrapper = mount(ComponentWithDialog)

  // Find PrimeVue component
  const dialog = wrapper.findComponent({ name: 'Dialog' })

  // Emit event
  dialog.vm.$emit('update:visible', false)

  await wrapper.vm.$nextTick()

  expect(wrapper.vm.dialogVisible).toBe(false)
})
```

## Common Pitfalls

### ❌ Not Waiting for Async
```typescript
// BAD
it('renders data', () => {
  helpStore.fetchArticles()
  expect(wrapper.text()).toContain('Article')
})
```

### ✅ Properly Waiting
```typescript
// GOOD
it('renders data', async () => {
  await helpStore.fetchArticles()
  await flushPromises()
  expect(wrapper.text()).toContain('Article')
})
```

### ❌ Not Resetting Stores
```typescript
// BAD - tests can affect each other
describe('Tests', () => {
  const store = useMyStore()

  it('test 1', () => {
    store.data = 'test1'
  })

  it('test 2', () => {
    // Fails because store.data is still 'test1'
    expect(store.data).toBeUndefined()
  })
})
```

### ✅ Proper Store Reset
```typescript
// GOOD
describe('Tests', () => {
  beforeEach(() => {
    const pinia = createPinia()
    setActivePinia(pinia)
  })

  it('test 1', () => {
    const store = useMyStore()
    store.data = 'test1'
  })

  it('test 2', () => {
    const store = useMyStore()
    expect(store.data).toBeUndefined()
  })
})
```

## Test Organization

```typescript
describe('ComponentName', () => {
  describe('Rendering', () => {
    it('should render basic structure', () => {})
    it('should render with props', () => {})
  })

  describe('User Interactions', () => {
    it('should handle click events', () => {})
    it('should handle form submission', () => {})
  })

  describe('Data Loading', () => {
    it('should show loading state', () => {})
    it('should display data when loaded', () => {})
    it('should handle errors', () => {})
  })

  describe('Edge Cases', () => {
    it('should handle empty data', () => {})
    it('should handle malformed input', () => {})
  })
})
```
```

---

### Task 14: Create Security Documentation

#### File: `docs/security/xss-prevention.md`

```markdown
# XSS Prevention Strategy

## Overview
This document describes the defense-in-depth Cross-Site Scripting (XSS) prevention strategy implemented in the help documentation system.

## Architecture: Two-Layer Protection

### Layer 1: Backend Sanitization (Python Bleach)
**Location**: `backend/src/help/markdown_renderer.py`

**Configuration**:
```python
import bleach

ALLOWED_TAGS = [
    'h1', 'h2', 'h3', 'h4', 'h5', 'h6',
    'p', 'br', 'hr', 'strong', 'em', 'u', 's',
    'ul', 'ol', 'li', 'a', 'code', 'pre',
    'blockquote', 'table', 'thead', 'tbody', 'tr', 'th', 'td'
]

ALLOWED_ATTRIBUTES = {
    'a': ['href', 'title'],
    '*': ['id', 'class']
}

def sanitize_html(html: str) -> str:
    return bleach.clean(
        html,
        tags=ALLOWED_TAGS,
        attributes=ALLOWED_ATTRIBUTES,
        strip=True
    )
```

**Purpose**:
- Primary defense against XSS
- Sanitizes markdown-generated HTML before storing in database
- Prevents malicious content from being persisted

### Layer 2: Frontend Sanitization (DOMPurify)
**Location**: `frontend/src/utils/sanitize.ts` (Story 11.8d)

**Configuration**:
```typescript
import DOMPurify from 'dompurify'

export function sanitizeHtml(html: string): string {
  return DOMPurify.sanitize(html, {
    ALLOWED_TAGS: [
      'h1', 'h2', 'h3', 'h4', 'h5', 'h6',
      'p', 'br', 'hr', 'strong', 'em', 'u', 's', 'mark', 'span', 'div',
      'ul', 'ol', 'li', 'a', 'code', 'pre', 'blockquote',
      'table', 'thead', 'tbody', 'tr', 'th', 'td'
    ],
    ALLOWED_ATTR: ['href', 'title', 'id', 'class'],
    ALLOWED_URI_REGEXP: /^(?:(?:https?|mailto):|[^a-z]|[a-z+.-]+(?:[^a-z+.\-:]|$))/i,
  })
}
```

**Purpose**:
- Defense-in-depth protection
- Protects against backend sanitization bypass
- Client-side last line of defense before DOM rendering

## Why Two Layers?

### Defense-in-Depth Principle
Never rely on a single security control. If backend sanitization fails (bug, bypass, database compromise), frontend sanitization provides backup protection.

### Threat Scenarios Protected Against

1. **Backend Bypass**: Attacker finds vulnerability in Bleach configuration
   - **Mitigation**: DOMPurify still sanitizes before rendering

2. **Database Injection**: Malicious content inserted directly into database
   - **Mitigation**: DOMPurify sanitizes on read

3. **API Response Tampering**: Man-in-the-middle modifies API response
   - **Mitigation**: DOMPurify sanitizes before rendering

4. **Zero-Day in Backend Library**: Bleach has undiscovered vulnerability
   - **Mitigation**: DOMPurify provides independent protection

## Usage in Components

### Example: FAQView.vue
```typescript
import { sanitizeHtml } from '@/utils/sanitize'

// For search highlighting
const highlightSearchTerm = (text: string): string => {
  const query = searchQuery.value.trim()
  if (!query) return text

  const regex = new RegExp(`(${query})`, 'gi')
  const highlighted = text.replace(regex, '<mark>$1</mark>')

  // Sanitize to prevent XSS in user-generated search queries
  return sanitizeHtml(highlighted)
}

// For article content
const sanitizedContent = (article: HelpArticle): string => {
  return sanitizeHtml(article.content_html)
}
```

```vue
<template>
  <!-- Safe: Double-sanitized content -->
  <div v-html="sanitizedContent(article)"></div>

  <!-- Safe: Sanitized search highlighting -->
  <span v-html="highlightSearchTerm(article.title)"></span>
</template>
```

## What Gets Blocked?

### Script Tags
```html
<!-- Input -->
<p>Safe</p><script>alert('XSS')</script>

<!-- Output -->
<p>Safe</p>
```

### Event Handlers
```html
<!-- Input -->
<a href="#" onclick="alert('XSS')">Click</a>

<!-- Output -->
<a href="#">Click</a>
```

### JavaScript Protocols
```html
<!-- Input -->
<a href="javascript:alert('XSS')">Link</a>

<!-- Output -->
<a>Link</a>
```

### Data URLs
```html
<!-- Input -->
<a href="data:text/html,<script>alert('XSS')</script>">Link</a>

<!-- Output -->
<a>Link</a>
```

## What's Allowed?

### Safe HTML
```html
<h1>Heading</h1>
<p>Paragraph with <strong>bold</strong> and <em>italic</em></p>
<ul>
  <li>List item</li>
</ul>
<a href="https://example.com" title="Safe link">Link</a>
<code>const x = 42;</code>
<pre><code>function example() {}</code></pre>
```

### Safe Attributes
- `href` (on `<a>` tags, validated URLs only)
- `title` (tooltip text)
- `id` (element identification)
- `class` (CSS styling)

### Safe Protocols
- `https://` - Secure HTTP
- `http://` - HTTP (allowed but HTTPS preferred)
- `mailto:` - Email links
- Relative URLs (`/path/to/page`)

## Testing XSS Protection

### Unit Tests
Location: `frontend/src/utils/sanitize.spec.ts`

30+ test cases covering:
- Script tag removal
- Event handler removal
- Protocol validation
- Allowed HTML passthrough
- Edge cases and encoded entities

### Component Tests
Location: `frontend/tests/components/*.spec.ts`

XSS tests added to:
- `FAQView.spec.ts` - Tests FAQ content sanitization
- `ArticleView.spec.ts` - Tests article content sanitization

Example test:
```typescript
it('should sanitize malicious HTML', async () => {
  const malicious = {
    content_html: '<p>Safe</p><script>alert("XSS")</script>'
  }

  const wrapper = mount(Component, { props: { article: malicious } })
  await flushPromises()

  expect(wrapper.html()).not.toContain('<script>')
  expect(wrapper.html()).toContain('Safe')
})
```

## Maintenance Guidelines

### When to Update Allowed Tags
1. Review security implications
2. Update both backend AND frontend configurations
3. Add test cases for new tags
4. Document the change

### When Adding New v-html Usage
1. **ALWAYS** sanitize with `sanitizeHtml()`
2. Add ESLint disable comment with explanation
3. Add XSS test for the component
4. Document in component header

### Regular Audits
- Review all v-html usage quarterly
- Update DOMPurify to latest version
- Monitor security advisories for Bleach and DOMPurify
- Run penetration tests on help system

## References
- [OWASP XSS Prevention Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Cross_Site_Scripting_Prevention_Cheat_Sheet.html)
- [DOMPurify Documentation](https://github.com/cure53/DOMPurify)
- [Bleach Documentation](https://bleach.readthedocs.io/)
- Story 11.8a: Backend sanitization implementation
- Story 11.8d: Frontend sanitization implementation

## Contact
For security concerns, contact: Security Team

Last Updated: 2025-12-18 (Story 11.8d)
```

---

## Summary of Remaining Manual Steps

1. **Fix npm/rollup issue** (see devops-issue-rollup.md)
2. **Apply component changes** (Tasks 9-11 above)
3. **Add XSS tests** (Task 12 above)
4. **Create documentation** (Tasks 13-14 above - files ready to create)
5. **Run tests** to verify ≥90% pass rate
6. **Update story file** with completion notes
7. **Create pull request**

---

## Test Execution (When npm Fixed)

```bash
cd frontend

# Test sanitize utility
npm test -- --run src/utils/sanitize.spec.ts

# Test all components
npm test -- --run tests/components/

# Full test suite
npm test -- --run

# Generate coverage
npm test -- --coverage
```

**Expected Results**:
- sanitize.spec.ts: 30+ tests passing
- Component tests: XSS tests passing
- Overall pass rate: ≥90% (97/108 minimum)

---

## Files Modified/Created

### Created:
- `frontend/src/utils/sanitize.ts`
- `frontend/src/utils/sanitize.spec.ts`
- `.ai/devops-issue-rollup.md`
- `.ai/story-11.8d-implementation-guide.md` (this file)
- `docs/testing/async-testing-patterns.md` (pending)
- `docs/testing/component-testing-best-practices.md` (pending)
- `docs/security/xss-prevention.md` (pending)

### To Modify:
- `frontend/src/components/help/FAQView.vue`
- `frontend/src/components/help/ArticleView.vue`
- `frontend/src/components/help/SearchResults.vue`
- `frontend/tests/components/FAQView.spec.ts`
- `frontend/tests/components/ArticleView.spec.ts`
- `frontend/package.json` (already updated with dompurify)
- `docs/stories/epic-11/11.8d.test-refinements-security.md` (completion notes)
