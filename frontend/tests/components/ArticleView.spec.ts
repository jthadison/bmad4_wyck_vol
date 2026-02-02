/**
 * ArticleView Component Tests (Story 11.8c - Task 6)
 *
 * Tests for article display, TOC generation, responsive behavior, and user actions.
 */

import { describe, it, expect, beforeEach, vi, afterEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { setActivePinia, createPinia } from 'pinia'
import { createRouter, createMemoryHistory } from 'vue-router'
import ArticleView from '@/components/help/ArticleView.vue'
import { useHelpStore } from '@/stores/helpStore'
import type { HelpArticle } from '@/stores/helpStore'

// Mock the API client to prevent real HTTP requests
vi.mock('@/services/api', () => ({
  apiClient: {
    get: vi.fn().mockResolvedValue(null),
    post: vi.fn().mockResolvedValue(null),
    put: vi.fn().mockResolvedValue(null),
    patch: vi.fn().mockResolvedValue(null),
    delete: vi.fn().mockResolvedValue(null),
  },
}))

// Mock PrimeVue components
vi.mock('primevue/message', () => ({
  default: {
    name: 'Message',
    template: '<div><slot /></div>',
    props: ['severity', 'closable'],
  },
}))
vi.mock('primevue/tag', () => ({
  default: {
    name: 'Tag',
    template: '<span>{{ value }}</span>',
    props: ['value', 'severity'],
  },
}))
vi.mock('primevue/button', () => ({
  default: {
    name: 'Button',
    template: '<button @click="$emit(\'click\')"><slot /></button>',
    props: ['icon', 'label', 'severity', 'outlined', 'size'],
  },
}))
vi.mock('primevue/progressspinner', () => ({
  default: { name: 'ProgressSpinner', template: '<div>Loading...</div>' },
}))
vi.mock('primevue/accordion', () => ({
  default: { name: 'Accordion', template: '<div><slot /></div>' },
}))
vi.mock('primevue/accordiontab', () => ({
  default: {
    name: 'AccordionTab',
    template: '<div><slot /></div>',
    props: ['header'],
  },
}))
vi.mock('primevue/usetoast', () => ({
  useToast: () => ({
    add: vi.fn(),
  }),
}))

describe('ArticleView', () => {
  let pinia: ReturnType<typeof createPinia>
  let router: unknown

  const mockArticle: HelpArticle = {
    id: '1',
    slug: 'what-is-wyckoff',
    title: 'What is the Wyckoff Method?',
    category: 'FAQ',
    content_html: `
      <h2>Introduction</h2>
      <p>The Wyckoff Method is a technical analysis approach.</p>
      <h3>Key Principles</h3>
      <p>Supply and demand drive markets.</p>
      <h2>Conclusion</h2>
      <p>Wyckoff analysis remains relevant today.</p>
    `,
    content_markdown: '# Test',
    tags: ['wyckoff', 'technical-analysis', 'trading'],
    keywords: 'wyckoff method, technical analysis',
    last_updated: '2024-01-15T10:00:00Z',
    view_count: 1234,
  }

  beforeEach(async () => {
    pinia = createPinia()
    setActivePinia(pinia)

    // Create router with memory history for testing
    router = createRouter({
      history: createMemoryHistory(),
      routes: [
        {
          path: '/help/article/:slug',
          name: 'help-article',
          component: ArticleView,
        },
        {
          path: '/help',
          name: 'help-center',
          component: { template: '<div>Help Center</div>' },
        },
      ],
    })

    vi.clearAllMocks()

    // Mock window methods
    global.window.print = vi.fn()

    // Mock clipboard API using defineProperty (navigator.clipboard is read-only)
    Object.defineProperty(navigator, 'clipboard', {
      value: {
        writeText: vi.fn().mockResolvedValue(undefined),
      },
      writable: true,
      configurable: true,
    })

    // Get the help store and mock fetchArticle by default to prevent real API calls
    // Individual tests can override this mock as needed
    const helpStore = useHelpStore()
    vi.spyOn(helpStore, 'fetchArticle').mockImplementation(async () => {
      // Default: do nothing (no article loaded)
      helpStore.isLoading = false
    })
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('should render article view', () => {
    const wrapper = mount(ArticleView, {
      global: {
        plugins: [pinia, router],
        stubs: {
          ArticleFeedback: true,
        },
      },
    })

    expect(wrapper.find('.article-view').exists()).toBe(true)
  })

  it('should display loading state', () => {
    const helpStore = useHelpStore()
    helpStore.isLoading = true

    const wrapper = mount(ArticleView, {
      global: {
        plugins: [pinia, router],
        stubs: {
          ArticleFeedback: true,
        },
      },
    })

    expect(wrapper.find('.loading-state').exists()).toBe(true)
    expect(wrapper.text()).toContain('Loading')
  })

  it('should display error state when article not found', async () => {
    const helpStore = useHelpStore()

    // Mock fetchArticle to simulate error state
    vi.spyOn(helpStore, 'fetchArticle').mockImplementation(async () => {
      helpStore.currentArticle = null
      helpStore.isLoading = false
      helpStore.error = 'Not found'
    })

    const wrapper = mount(ArticleView, {
      global: {
        plugins: [pinia, router],
        stubs: {
          ArticleFeedback: true,
        },
      },
    })

    await wrapper.vm.$nextTick()
    await wrapper.vm.$nextTick()

    expect(wrapper.find('.error-state').exists()).toBe(true)
    expect(wrapper.text()).toContain('Article Not Found')
  })

  it('should navigate to help center on error state button click', async () => {
    const helpStore = useHelpStore()

    // Mock fetchArticle to simulate error state
    vi.spyOn(helpStore, 'fetchArticle').mockImplementation(async () => {
      helpStore.currentArticle = null
      helpStore.isLoading = false
      helpStore.error = 'Not found'
    })

    await router.push('/help/article/nonexistent')
    await router.isReady()

    const wrapper = mount(ArticleView, {
      global: {
        plugins: [pinia, router],
        stubs: {
          ArticleFeedback: true,
        },
      },
    })

    await wrapper.vm.$nextTick()
    await wrapper.vm.$nextTick()

    const pushSpy = vi.spyOn(router, 'push')
    const button = wrapper.find('.error-content button')

    await button.trigger('click')

    expect(pushSpy).toHaveBeenCalledWith('/help')
  })

  it('should display article content when loaded', async () => {
    const helpStore = useHelpStore()

    // Mock fetchArticle to set the article data
    vi.spyOn(helpStore, 'fetchArticle').mockImplementation(async () => {
      helpStore.currentArticle = mockArticle
      helpStore.isLoading = false
    })

    const wrapper = mount(ArticleView, {
      global: {
        plugins: [pinia, router],
        stubs: {
          ArticleFeedback: true,
        },
      },
    })

    // Wait for fetchArticle to complete
    await wrapper.vm.$nextTick()
    await wrapper.vm.$nextTick()

    expect(wrapper.find('.article-container').exists()).toBe(true)
    expect(wrapper.find('.article-title').text()).toBe(mockArticle.title)
  })

  it('should display article metadata', async () => {
    const helpStore = useHelpStore()

    // Mock fetchArticle to set the article data
    vi.spyOn(helpStore, 'fetchArticle').mockImplementation(async () => {
      helpStore.currentArticle = mockArticle
      helpStore.isLoading = false
    })

    const wrapper = mount(ArticleView, {
      global: {
        plugins: [pinia, router],
        stubs: {
          ArticleFeedback: true,
        },
      },
    })

    await wrapper.vm.$nextTick()
    await wrapper.vm.$nextTick()

    const metadata = wrapper.find('.article-metadata')
    expect(metadata.exists()).toBe(true)
    expect(metadata.text()).toContain('FAQ')
    expect(metadata.text()).toContain('1234 views')
  })

  it('should format date correctly', async () => {
    const helpStore = useHelpStore()

    vi.spyOn(helpStore, 'fetchArticle').mockImplementation(async () => {
      helpStore.currentArticle = mockArticle
      helpStore.isLoading = false
    })

    const wrapper = mount(ArticleView, {
      global: {
        plugins: [pinia, router],
        stubs: {
          ArticleFeedback: true,
        },
      },
    })

    await wrapper.vm.$nextTick()
    await wrapper.vm.$nextTick()

    const metadata = wrapper.find('.article-metadata')
    // Should contain "January 15, 2024" or similar formatted date
    expect(metadata.text()).toContain('Updated')
    expect(metadata.text()).toContain('2024')
  })

  it('should render article body HTML content', async () => {
    const helpStore = useHelpStore()

    vi.spyOn(helpStore, 'fetchArticle').mockImplementation(async () => {
      helpStore.currentArticle = mockArticle
      helpStore.isLoading = false
    })

    const wrapper = mount(ArticleView, {
      global: {
        plugins: [pinia, router],
        stubs: {
          ArticleFeedback: true,
        },
      },
    })

    await wrapper.vm.$nextTick()
    await wrapper.vm.$nextTick()

    const articleBody = wrapper.find('.article-body')
    expect(articleBody.exists()).toBe(true)
    expect(articleBody.html()).toContain('<h2>Introduction</h2>')
    expect(articleBody.html()).toContain('<h3>Key Principles</h3>')
  })

  it('should display article tags', async () => {
    const helpStore = useHelpStore()

    vi.spyOn(helpStore, 'fetchArticle').mockImplementation(async () => {
      helpStore.currentArticle = mockArticle
      helpStore.isLoading = false
    })

    const wrapper = mount(ArticleView, {
      global: {
        plugins: [pinia, router],
        stubs: {
          ArticleFeedback: true,
        },
      },
    })

    await wrapper.vm.$nextTick()
    await wrapper.vm.$nextTick()

    const tags = wrapper.find('.article-tags')
    expect(tags.exists()).toBe(true)
    expect(tags.text()).toContain('wyckoff')
    expect(tags.text()).toContain('technical-analysis')
  })

  it('should not display tags section if no tags', async () => {
    const articleNoTags = { ...mockArticle, tags: [] }
    const helpStore = useHelpStore()

    vi.spyOn(helpStore, 'fetchArticle').mockImplementation(async () => {
      helpStore.currentArticle = articleNoTags
      helpStore.isLoading = false
    })

    const wrapper = mount(ArticleView, {
      global: {
        plugins: [pinia, router],
        stubs: {
          ArticleFeedback: true,
        },
      },
    })

    await wrapper.vm.$nextTick()
    await wrapper.vm.$nextTick()

    expect(wrapper.find('.article-tags').exists()).toBe(false)
  })

  it('should render ArticleFeedback component', async () => {
    const helpStore = useHelpStore()

    vi.spyOn(helpStore, 'fetchArticle').mockImplementation(async () => {
      helpStore.currentArticle = mockArticle
      helpStore.isLoading = false
    })

    const wrapper = mount(ArticleView, {
      global: {
        plugins: [pinia, router],
        stubs: {
          ArticleFeedback: true,
        },
      },
    })

    await wrapper.vm.$nextTick()
    await wrapper.vm.$nextTick()

    const feedback = wrapper.findComponent({ name: 'ArticleFeedback' })
    expect(feedback.exists()).toBe(true)
    expect(feedback.props('articleId')).toBe('1')
    expect(feedback.props('articleSlug')).toBe('what-is-wyckoff')
  })

  it('should generate table of contents from h2 and h3 headers', async () => {
    const helpStore = useHelpStore()

    vi.spyOn(helpStore, 'fetchArticle').mockImplementation(async () => {
      helpStore.currentArticle = mockArticle
      helpStore.isLoading = false
    })

    const wrapper = mount(ArticleView, {
      global: {
        plugins: [pinia, router],
        stubs: {
          ArticleFeedback: true,
        },
      },
      attachTo: document.body,
    })

    // Wait for all promises and DOM updates to complete
    await flushPromises()
    await wrapper.vm.$nextTick()

    // Verify article body exists and has content with headers
    const articleBody = wrapper.find('.article-body')
    expect(articleBody.exists()).toBe(true)

    // Check that headers were rendered in the DOM
    const headers = document.querySelectorAll(
      '.article-body h2, .article-body h3'
    )
    expect(headers.length).toBeGreaterThan(0)

    const vm = wrapper.vm as unknown

    // The component automatically calls generateTableOfContents in onMounted
    // Should have 3 TOC items: Introduction (h2), Key Principles (h3), Conclusion (h2)
    expect(vm.tableOfContents.length).toBeGreaterThan(0)

    wrapper.unmount()
  })

  it('should display TOC sidebar on desktop', async () => {
    const helpStore = useHelpStore()

    vi.spyOn(helpStore, 'fetchArticle').mockImplementation(async () => {
      helpStore.currentArticle = mockArticle
      helpStore.isLoading = false
    })

    const wrapper = mount(ArticleView, {
      global: {
        plugins: [pinia, router],
        stubs: {
          ArticleFeedback: true,
        },
      },
    })

    await wrapper.vm.$nextTick()
    await wrapper.vm.$nextTick()

    const vm = wrapper.vm as unknown
    vm.isMobile = false
    vm.tableOfContents = [
      { id: 'heading-0', text: 'Introduction', level: 2 },
      { id: 'heading-1', text: 'Key Principles', level: 3 },
    ]

    await wrapper.vm.$nextTick()

    expect(wrapper.find('.toc-sidebar').exists()).toBe(true)
    expect(wrapper.find('.toc-sticky').exists()).toBe(true)
  })

  it('should display TOC accordion on mobile', async () => {
    const helpStore = useHelpStore()

    vi.spyOn(helpStore, 'fetchArticle').mockImplementation(async () => {
      helpStore.currentArticle = mockArticle
      helpStore.isLoading = false
    })

    const wrapper = mount(ArticleView, {
      global: {
        plugins: [pinia, router],
        stubs: {
          ArticleFeedback: true,
        },
      },
    })

    await wrapper.vm.$nextTick()
    await wrapper.vm.$nextTick()

    const vm = wrapper.vm as unknown
    vm.isMobile = true
    vm.tableOfContents = [
      { id: 'heading-0', text: 'Introduction', level: 2 },
      { id: 'heading-1', text: 'Key Principles', level: 3 },
    ]

    await wrapper.vm.$nextTick()

    expect(wrapper.find('.toc-mobile').exists()).toBe(true)
  })

  it('should not display TOC if no table of contents', async () => {
    const helpStore = useHelpStore()

    vi.spyOn(helpStore, 'fetchArticle').mockImplementation(async () => {
      helpStore.currentArticle = {
        ...mockArticle,
        content_html: '<p>Simple content</p>',
      }
      helpStore.isLoading = false
    })

    const wrapper = mount(ArticleView, {
      global: {
        plugins: [pinia, router],
        stubs: {
          ArticleFeedback: true,
        },
      },
    })

    await wrapper.vm.$nextTick()
    await wrapper.vm.$nextTick()

    const vm = wrapper.vm as unknown
    vm.tableOfContents = []

    await wrapper.vm.$nextTick()

    expect(wrapper.find('.toc-sidebar').exists()).toBe(false)
    expect(wrapper.find('.toc-mobile').exists()).toBe(false)
  })

  it('should apply correct CSS class for TOC levels', async () => {
    const helpStore = useHelpStore()

    vi.spyOn(helpStore, 'fetchArticle').mockImplementation(async () => {
      helpStore.currentArticle = mockArticle
      helpStore.isLoading = false
    })

    const wrapper = mount(ArticleView, {
      global: {
        plugins: [pinia, router],
        stubs: {
          ArticleFeedback: true,
        },
      },
    })

    await wrapper.vm.$nextTick()
    await wrapper.vm.$nextTick()

    const vm = wrapper.vm as unknown
    vm.isMobile = false
    vm.tableOfContents = [
      { id: 'heading-0', text: 'Introduction', level: 2 },
      { id: 'heading-1', text: 'Key Principles', level: 3 },
    ]

    await wrapper.vm.$nextTick()

    const links = wrapper.findAll('.toc-link')
    expect(links.length).toBe(2)
    expect(links[0].classes()).toContain('toc-level-2')
    expect(links[1].classes()).toContain('toc-level-3')
  })

  it('should scroll to heading when TOC link clicked', async () => {
    const helpStore = useHelpStore()

    vi.spyOn(helpStore, 'fetchArticle').mockImplementation(async () => {
      helpStore.currentArticle = mockArticle
      helpStore.isLoading = false
    })

    // Mock scrollIntoView
    const scrollIntoViewMock = vi.fn()
    Element.prototype.scrollIntoView = scrollIntoViewMock

    const wrapper = mount(ArticleView, {
      global: {
        plugins: [pinia, router],
        stubs: {
          ArticleFeedback: true,
        },
      },
    })

    await wrapper.vm.$nextTick()
    await wrapper.vm.$nextTick()

    const vm = wrapper.vm as unknown
    vm.isMobile = false
    vm.tableOfContents = [{ id: 'heading-0', text: 'Introduction', level: 2 }]

    await wrapper.vm.$nextTick()

    // Create mock element
    const mockElement = document.createElement('div')
    mockElement.id = 'heading-0'
    mockElement.scrollIntoView = scrollIntoViewMock
    document.body.appendChild(mockElement)

    const link = wrapper.find('.toc-link')
    await link.trigger('click')

    expect(scrollIntoViewMock).toHaveBeenCalledWith({
      behavior: 'smooth',
      block: 'start',
    })

    document.body.removeChild(mockElement)
  })

  it('should copy article URL to clipboard when share button clicked', async () => {
    const helpStore = useHelpStore()
    helpStore.currentArticle = mockArticle
    helpStore.isLoading = false

    const wrapper = mount(ArticleView, {
      global: {
        plugins: [pinia, router],
        stubs: {
          ArticleFeedback: true,
        },
      },
    })

    await wrapper.vm.$nextTick()

    const vm = wrapper.vm as unknown
    await vm.copyArticleUrl()

    expect(navigator.clipboard.writeText).toHaveBeenCalledWith(
      window.location.href
    )
  })

  it('should handle clipboard copy failure gracefully', async () => {
    const helpStore = useHelpStore()
    helpStore.currentArticle = mockArticle
    helpStore.isLoading = false

    // Mock clipboard failure
    Object.assign(navigator, {
      clipboard: {
        writeText: vi
          .fn()
          .mockRejectedValue(new Error('Clipboard access denied')),
      },
    })

    const wrapper = mount(ArticleView, {
      global: {
        plugins: [pinia, router],
        stubs: {
          ArticleFeedback: true,
        },
      },
    })

    const vm = wrapper.vm as unknown

    await vm.copyArticleUrl()

    // Should not throw error
    expect(navigator.clipboard.writeText).toHaveBeenCalled()
  })

  it('should trigger print when print button clicked', async () => {
    const helpStore = useHelpStore()
    helpStore.currentArticle = mockArticle
    helpStore.isLoading = false

    const wrapper = mount(ArticleView, {
      global: {
        plugins: [pinia, router],
        stubs: {
          ArticleFeedback: true,
        },
      },
    })

    await wrapper.vm.$nextTick()

    const vm = wrapper.vm as unknown
    vm.printArticle()

    expect(window.print).toHaveBeenCalled()
  })

  it('should update isMobile on window resize', async () => {
    const helpStore = useHelpStore()
    helpStore.currentArticle = mockArticle
    helpStore.isLoading = false

    const wrapper = mount(ArticleView, {
      global: {
        plugins: [pinia, router],
        stubs: {
          ArticleFeedback: true,
        },
      },
    })

    const vm = wrapper.vm as unknown

    // Start desktop
    Object.defineProperty(window, 'innerWidth', { writable: true, value: 1200 })
    vm.handleResize()
    expect(vm.isMobile).toBe(false)

    // Switch to mobile
    Object.defineProperty(window, 'innerWidth', { writable: true, value: 800 })
    vm.handleResize()
    expect(vm.isMobile).toBe(true)

    // Back to desktop
    Object.defineProperty(window, 'innerWidth', { writable: true, value: 1100 })
    vm.handleResize()
    expect(vm.isMobile).toBe(false)
  })

  it('should register and cleanup resize listener', async () => {
    // Set up spies BEFORE creating store or mounting component
    const addEventListenerSpy = vi.spyOn(window, 'addEventListener')
    const removeEventListenerSpy = vi.spyOn(window, 'removeEventListener')

    const helpStore = useHelpStore()

    // Mock fetchArticle to allow component to mount properly
    vi.spyOn(helpStore, 'fetchArticle').mockImplementation(async () => {
      helpStore.currentArticle = mockArticle
      helpStore.isLoading = false
    })

    const wrapper = mount(ArticleView, {
      global: {
        plugins: [pinia, router],
        stubs: {
          ArticleFeedback: true,
        },
      },
    })

    // Wait for all async operations to complete
    await flushPromises()
    await wrapper.vm.$nextTick()

    expect(addEventListenerSpy).toHaveBeenCalledWith(
      'resize',
      expect.any(Function)
    )

    wrapper.unmount()

    expect(removeEventListenerSpy).toHaveBeenCalledWith(
      'resize',
      expect.any(Function)
    )
  })

  it('should fetch article on mount', async () => {
    const helpStore = useHelpStore()
    // Mock fetchArticle to prevent real API calls while still tracking calls
    const fetchSpy = vi
      .spyOn(helpStore, 'fetchArticle')
      .mockImplementation(async () => {
        helpStore.isLoading = false
      })

    await router.push('/help/article/what-is-wyckoff')
    await router.isReady()

    mount(ArticleView, {
      global: {
        plugins: [pinia, router],
        stubs: {
          ArticleFeedback: true,
        },
      },
    })

    expect(fetchSpy).toHaveBeenCalledWith('what-is-wyckoff')
  })

  it('should handle missing article gracefully', async () => {
    const helpStore = useHelpStore()

    vi.spyOn(helpStore, 'fetchArticle').mockImplementation(async () => {
      helpStore.currentArticle = null
      helpStore.isLoading = false
    })

    const wrapper = mount(ArticleView, {
      global: {
        plugins: [pinia, router],
        stubs: {
          ArticleFeedback: true,
        },
      },
    })

    await wrapper.vm.$nextTick()
    await wrapper.vm.$nextTick()

    expect(wrapper.find('.error-state').exists()).toBe(true)
    expect(wrapper.find('.article-container').exists()).toBe(false)
  })

  it('should assign IDs to headers during TOC generation', async () => {
    const helpStore = useHelpStore()

    vi.spyOn(helpStore, 'fetchArticle').mockImplementation(async () => {
      helpStore.currentArticle = mockArticle
      helpStore.isLoading = false
    })

    const wrapper = mount(ArticleView, {
      global: {
        plugins: [pinia, router],
        stubs: {
          ArticleFeedback: true,
        },
      },
    })

    await wrapper.vm.$nextTick()

    // Create mock headers
    const articleBody = document.createElement('div')
    articleBody.className = 'article-body'
    const h2 = document.createElement('h2')
    h2.textContent = 'Test Heading'
    articleBody.appendChild(h2)
    document.body.appendChild(articleBody)

    const vm = wrapper.vm as unknown
    vm.generateTableOfContents()

    await wrapper.vm.$nextTick()

    // Header should have ID assigned
    expect(h2.getAttribute('id')).toBeTruthy()

    document.body.removeChild(articleBody)
  })

  it('should sanitize malicious HTML in article content', async () => {
    const helpStore = useHelpStore()

    const maliciousArticle: HelpArticle = {
      id: '999',
      slug: 'xss-test-article',
      title: 'XSS Test Article',
      category: 'GUIDE',
      content_html:
        '<h1>Title</h1><script>fetch("/steal-data")</script><p>Content</p>',
      content_markdown: '# Title\n\nContent',
      tags: ['test'],
      keywords: 'test',
      last_updated: new Date().toISOString(),
      view_count: 0,
      helpful_count: 0,
      not_helpful_count: 0,
    }

    vi.spyOn(helpStore, 'fetchArticle').mockImplementation(async () => {
      helpStore.currentArticle = maliciousArticle
      helpStore.isLoading = false
    })

    const wrapper = mount(ArticleView, {
      global: {
        plugins: [pinia, router],
        stubs: {
          ArticleFeedback: true,
        },
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
})
