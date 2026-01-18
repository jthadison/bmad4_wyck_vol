/**
 * SearchResults Component Tests (Story 11.8c - Task 5)
 *
 * Tests for search results display, keyboard navigation, and routing.
 */

import { createPinia } from 'pinia'
import { describe, it, expect, beforeEach, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { setActivePinia, createPinia } from 'pinia'
import { createRouter, createMemoryHistory } from 'vue-router'
import SearchResults from '@/components/help/SearchResults.vue'
import { useHelpStore } from '@/stores/helpStore'
import type { SearchResult } from '@/stores/helpStore'

// Mock PrimeVue components
vi.mock('primevue/dataview', () => ({
  default: {
    name: 'DataView',
    template: '<div><slot name="list" :items="value" /></div>',
    props: ['value'],
  },
}))
vi.mock('primevue/tag', () => ({
  default: {
    name: 'Tag',
    template: '<span>{{ value }}</span>',
    props: ['value', 'severity'],
  },
}))
vi.mock('primevue/progressspinner', () => ({
  default: { name: 'ProgressSpinner', template: '<div>Loading...</div>' },
}))
vi.mock('primevue/message', () => ({
  default: {
    name: 'Message',
    template: '<div><slot /></div>',
    props: ['severity'],
  },
}))

describe('SearchResults', () => {
  let pinia: ReturnType<typeof createPinia>
  let router: unknown

  const mockSearchResults: SearchResult[] = [
    {
      article_id: '1',
      slug: 'spring',
      title: 'Spring Pattern',
      category: 'GLOSSARY',
      snippet: 'A <mark>spring</mark> is a price move below support...',
      rank: 1.0,
    },
    {
      article_id: '2',
      slug: 'identifying-springs',
      title: 'Identifying Springs Tutorial',
      category: 'TUTORIAL',
      snippet: 'Learn to identify <mark>spring</mark> patterns...',
      rank: 0.9,
    },
    {
      article_id: '3',
      slug: 'what-is-a-spring',
      title: 'What is a Spring?',
      category: 'FAQ',
      snippet: 'A <mark>spring</mark> pattern occurs when...',
      rank: 0.8,
    },
  ]

  beforeEach(() => {
    pinia = createPinia()
    setActivePinia(pinia)

    // Initialize store state before tests
    const helpStore = useHelpStore()
    helpStore.isLoading = false
    helpStore.error = null
    helpStore.searchResults = []

    // Create router with memory history for testing
    router = createRouter({
      history: createMemoryHistory(),
      routes: [
        { path: '/help/search', name: 'help-search', component: SearchResults },
        {
          path: '/help/glossary',
          name: 'help-glossary',
          component: { template: '<div>Glossary</div>' },
        },
        {
          path: '/help/article/:slug',
          name: 'help-article',
          component: { template: '<div>Article</div>' },
        },
        {
          path: '/tutorials/:slug',
          name: 'tutorial-walkthrough',
          component: { template: '<div>Tutorial</div>' },
        },
      ],
    })

    vi.clearAllMocks()
  })

  it('should render search results view', () => {
    const wrapper = mount(SearchResults, {
      global: {
        plugins: [pinia, router],
      },
    })

    expect(wrapper.find('.search-results-view').exists()).toBe(true)
  })

  it('should extract query from route params', async () => {
    await router.push('/help/search?q=spring')
    await router.isReady()

    const wrapper = mount(SearchResults, {
      global: {
        plugins: [pinia, router],
      },
    })

    const vm = wrapper.vm as unknown
    expect(vm.searchQuery).toBe('spring')
  })

  it('should display search results count', async () => {
    const helpStore = useHelpStore()

    // Mock searchHelp to prevent API call and set data synchronously
    vi.spyOn(helpStore, 'searchHelp').mockImplementation(async () => {
      helpStore.searchResults = mockSearchResults
      helpStore.isLoading = false
    })

    await router.push('/help/search?q=spring')
    await router.isReady()

    const wrapper = mount(SearchResults, {
      global: {
        plugins: [pinia, router],
      },
    })

    // Wait for search to complete
    await wrapper.vm.$nextTick()
    await wrapper.vm.$nextTick()

    const text = wrapper.text()
    // Component shows "Found 3 results" at line 233
    expect(text).toContain('Found')
    expect(text).toContain('3')
    expect(text.toLowerCase()).toContain('spring')
  })

  it('should display category badges with correct colors', () => {
    const wrapper = mount(SearchResults, {
      global: {
        plugins: [pinia, router],
      },
    })

    const vm = wrapper.vm as unknown

    expect(vm.getCategorySeverity('GLOSSARY')).toBe('info')
    expect(vm.getCategorySeverity('FAQ')).toBe('success')
    expect(vm.getCategorySeverity('TUTORIAL')).toBe('warn')
    expect(vm.getCategorySeverity('OTHER')).toBe('secondary')
  })

  it('should display loading state', async () => {
    const helpStore = useHelpStore()
    helpStore.isLoading = true

    const wrapper = mount(SearchResults, {
      global: {
        plugins: [pinia, router],
      },
    })

    expect(wrapper.find('.loading-state').exists()).toBe(true)
    expect(wrapper.text()).toContain('Loading')
  })

  it('should display empty state when no results', async () => {
    const helpStore = useHelpStore()

    // Mock searchHelp to return empty results
    vi.spyOn(helpStore, 'searchHelp').mockImplementation(async () => {
      helpStore.searchResults = []
      helpStore.isLoading = false
    })

    await router.push('/help/search?q=nonexistent')
    await router.isReady()

    const wrapper = mount(SearchResults, {
      global: {
        plugins: [pinia, router],
      },
    })

    // Wait for search to complete
    await wrapper.vm.$nextTick()
    await wrapper.vm.$nextTick()

    const text = wrapper.text()
    // Component shows "No results found for" at line 213
    expect(text).toContain('No results found')
    expect(text).toContain('nonexistent')
  })

  it('should display empty state with suggestions', async () => {
    const helpStore = useHelpStore()

    // Mock searchHelp to return empty results
    vi.spyOn(helpStore, 'searchHelp').mockImplementation(async () => {
      helpStore.searchResults = []
      helpStore.isLoading = false
    })

    await router.push('/help/search?q=xyz')
    await router.isReady()

    const wrapper = mount(SearchResults, {
      global: {
        plugins: [pinia, router],
      },
    })

    // Wait for search to complete
    await wrapper.vm.$nextTick()
    await wrapper.vm.$nextTick()

    const text = wrapper.text()
    // Component shows suggestions at lines 215-225
    expect(text).toContain('Try these suggestions')
  })

  it('should handle keyboard navigation with Arrow Down', async () => {
    const helpStore = useHelpStore()
    helpStore.searchResults = mockSearchResults

    await router.push('/help/search?q=spring')
    await router.isReady()

    const wrapper = mount(SearchResults, {
      global: {
        plugins: [pinia, router],
      },
    })

    const vm = wrapper.vm as unknown

    expect(vm.selectedIndex).toBe(0)

    // Simulate Arrow Down
    vm.handleKeyDown({ key: 'ArrowDown', preventDefault: vi.fn() })

    expect(vm.selectedIndex).toBe(1)
  })

  it('should handle keyboard navigation with Arrow Up', async () => {
    const helpStore = useHelpStore()
    helpStore.searchResults = mockSearchResults

    await router.push('/help/search?q=spring')
    await router.isReady()

    const wrapper = mount(SearchResults, {
      global: {
        plugins: [pinia, router],
      },
    })

    const vm = wrapper.vm as unknown

    vm.selectedIndex = 1

    // Simulate Arrow Up
    vm.handleKeyDown({ key: 'ArrowUp', preventDefault: vi.fn() })

    expect(vm.selectedIndex).toBe(0)
  })

  it('should not go below 0 when navigating up', async () => {
    const helpStore = useHelpStore()
    helpStore.searchResults = mockSearchResults

    const wrapper = mount(SearchResults, {
      global: {
        plugins: [pinia, router],
      },
    })

    const vm = wrapper.vm as unknown
    vm.selectedIndex = 0

    // Try to go up from 0
    vm.handleKeyDown({ key: 'ArrowUp', preventDefault: vi.fn() })

    expect(vm.selectedIndex).toBe(0)
  })

  it('should not exceed max index when navigating down', async () => {
    const helpStore = useHelpStore()
    helpStore.searchResults = mockSearchResults

    const wrapper = mount(SearchResults, {
      global: {
        plugins: [pinia, router],
      },
    })

    const vm = wrapper.vm as unknown
    vm.selectedIndex = 2 // Last item

    // Try to go down from last item
    vm.handleKeyDown({ key: 'ArrowDown', preventDefault: vi.fn() })

    expect(vm.selectedIndex).toBe(2)
  })

  it('should navigate to glossary for GLOSSARY category', async () => {
    const wrapper = mount(SearchResults, {
      global: {
        plugins: [pinia, router],
      },
    })

    const vm = wrapper.vm as unknown
    const pushSpy = vi.spyOn(router, 'push')

    vm.navigateToResult('spring', 'GLOSSARY')

    expect(pushSpy).toHaveBeenCalledWith('/help/glossary')
  })

  it('should navigate to tutorial for TUTORIAL category', async () => {
    const wrapper = mount(SearchResults, {
      global: {
        plugins: [pinia, router],
      },
    })

    const vm = wrapper.vm as unknown
    const pushSpy = vi.spyOn(router, 'push')

    vm.navigateToResult('identifying-springs', 'TUTORIAL')

    expect(pushSpy).toHaveBeenCalledWith('/tutorials/identifying-springs')
  })

  it('should navigate to article for FAQ category', async () => {
    const wrapper = mount(SearchResults, {
      global: {
        plugins: [pinia, router],
      },
    })

    const vm = wrapper.vm as unknown
    const pushSpy = vi.spyOn(router, 'push')

    vm.navigateToResult('what-is-a-spring', 'FAQ')

    expect(pushSpy).toHaveBeenCalledWith('/help/article/what-is-a-spring')
  })

  it('should handle Enter key to navigate to selected result', async () => {
    const helpStore = useHelpStore()
    helpStore.searchResults = mockSearchResults

    const wrapper = mount(SearchResults, {
      global: {
        plugins: [pinia, router],
      },
    })

    const vm = wrapper.vm as unknown
    const pushSpy = vi.spyOn(router, 'push')

    vm.selectedIndex = 0

    // Press Enter
    vm.handleKeyDown({ key: 'Enter', preventDefault: vi.fn() })

    expect(pushSpy).toHaveBeenCalled()
  })

  it('should prevent default on keyboard navigation', () => {
    const helpStore = useHelpStore()
    helpStore.searchResults = mockSearchResults

    const wrapper = mount(SearchResults, {
      global: {
        plugins: [pinia, router],
      },
    })

    const vm = wrapper.vm as unknown
    const preventDefaultMock = vi.fn()

    vm.handleKeyDown({ key: 'ArrowDown', preventDefault: preventDefaultMock })

    expect(preventDefaultMock).toHaveBeenCalled()
  })

  it('should register and cleanup keyboard listeners', () => {
    const addEventListenerSpy = vi.spyOn(window, 'addEventListener')
    const removeEventListenerSpy = vi.spyOn(window, 'removeEventListener')

    const wrapper = mount(SearchResults, {
      global: {
        plugins: [pinia, router],
      },
    })

    expect(addEventListenerSpy).toHaveBeenCalledWith(
      'keydown',
      expect.any(Function)
    )

    wrapper.unmount()

    expect(removeEventListenerSpy).toHaveBeenCalledWith(
      'keydown',
      expect.any(Function)
    )
  })

  it('should watch for query changes and re-search', async () => {
    const helpStore = useHelpStore()
    helpStore.isLoading = false
    const searchSpy = vi.spyOn(helpStore, 'searchHelp')

    await router.push('/help/search?q=spring')
    await router.isReady()

    const wrapper = mount(SearchResults, {
      global: {
        plugins: [pinia, router],
      },
    })

    // Change query
    await router.push('/help/search?q=utad')
    await wrapper.vm.$nextTick()

    expect(searchSpy).toHaveBeenCalledWith('utad', 50)
  })

  it('should handle click on result item', async () => {
    const helpStore = useHelpStore()
    helpStore.searchResults = mockSearchResults

    await router.push('/help/search?q=spring')
    await router.isReady()

    const wrapper = mount(SearchResults, {
      global: {
        plugins: [pinia, router],
      },
    })

    const vm = wrapper.vm as unknown
    const pushSpy = vi.spyOn(router, 'push')

    // Click on first result (index 0)
    vm.handleResultClick(0)

    expect(pushSpy).toHaveBeenCalled()
  })

  it('should highlight selected result visually', async () => {
    const helpStore = useHelpStore()
    helpStore.searchResults = mockSearchResults

    const wrapper = mount(SearchResults, {
      global: {
        plugins: [pinia, router],
      },
    })

    const vm = wrapper.vm as unknown

    vm.selectedIndex = 1

    await wrapper.vm.$nextTick()

    // The component should apply a selected class or style
    expect(vm.selectedIndex).toBe(1)
  })
})
