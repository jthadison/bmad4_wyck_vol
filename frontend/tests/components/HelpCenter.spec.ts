/**
 * HelpCenter Component Tests (Story 11.8a - Task 11)
 *
 * Tests for HelpCenter component navigation, search, and responsiveness.
 */

import { describe, it, expect, beforeEach, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { createRouter, createMemoryHistory } from 'vue-router'
import { setActivePinia, createPinia } from 'pinia'
import HelpCenter from '@/components/help/HelpCenter.vue'
import { useHelpStore } from '@/stores/helpStore'

// Mock PrimeVue components
vi.mock('primevue/button', () => ({
  default: { name: 'Button', template: '<button><slot /></button>' },
}))
vi.mock('primevue/sidebar', () => ({
  default: {
    name: 'Sidebar',
    template: '<div><slot name="header" /><slot /></div>',
  },
}))
vi.mock('primevue/menu', () => ({
  default: { name: 'Menu', template: '<div></div>' },
}))
vi.mock('primevue/inputtext', () => ({
  default: { name: 'InputText', template: '<input />' },
}))
vi.mock('primevue/iconfield', () => ({
  default: { name: 'IconField', template: '<div><slot /></div>' },
}))
vi.mock('primevue/inputicon', () => ({
  default: { name: 'InputIcon', template: '<i></i>' },
}))
vi.mock('primevue/overlaypanel', () => ({
  default: { name: 'OverlayPanel', template: '<div><slot /></div>' },
}))
vi.mock('primevue/breadcrumb', () => ({
  default: { name: 'Breadcrumb', template: '<div></div>' },
}))
vi.mock('primevue/card', () => ({
  default: {
    name: 'Card',
    template:
      '<div><slot name="header" /><slot name="title" /><slot name="content" /></div>',
  },
}))
vi.mock('primevue/tag', () => ({
  default: { name: 'Tag', template: '<span></span>' },
}))

describe('HelpCenter', () => {
  let router: any
  let pinia: any

  beforeEach(() => {
    pinia = createPinia()
    setActivePinia(pinia)

    router = createRouter({
      history: createMemoryHistory(),
      routes: [
        { path: '/help', component: { template: '<div>Help Home</div>' } },
        {
          path: '/help/glossary',
          component: { template: '<div>Glossary</div>' },
        },
        {
          path: '/help/article/:slug',
          component: { template: '<div>Article</div>' },
        },
      ],
    })

    vi.clearAllMocks()
  })

  it('should render the help center', () => {
    const wrapper = mount(HelpCenter, {
      global: {
        plugins: [router, pinia],
        stubs: {
          RouterView: { template: '<div>Router View</div>' },
        },
      },
    })

    expect(wrapper.find('.help-center').exists()).toBe(true)
  })

  it('should display search bar', () => {
    const wrapper = mount(HelpCenter, {
      global: {
        plugins: [router, pinia],
        stubs: {
          RouterView: true,
        },
      },
    })

    expect(wrapper.find('.search-container').exists()).toBe(true)
  })

  it('should display navigation menu items', () => {
    const wrapper = mount(HelpCenter, {
      global: {
        plugins: [router, pinia],
        stubs: {
          RouterView: true,
        },
      },
    })

    expect(wrapper.find('.help-nav-menu').exists()).toBe(true)
  })

  it('should display popular topics on home view', async () => {
    await router.push('/help')
    await router.isReady()

    const wrapper = mount(HelpCenter, {
      global: {
        plugins: [router, pinia],
        stubs: {
          RouterView: true,
        },
      },
    })

    expect(wrapper.find('.help-home').exists()).toBe(true)
    expect(wrapper.find('.popular-topics').exists()).toBe(true)
    expect(wrapper.find('.topic-cards').exists()).toBe(true)
  })

  it('should handle search input with debounce', async () => {
    const wrapper = mount(HelpCenter, {
      global: {
        plugins: [router, pinia],
        stubs: {
          RouterView: true,
        },
      },
    })

    const helpStore = useHelpStore()
    vi.spyOn(helpStore, 'searchHelp')

    const input = wrapper.find('input')
    await input.setValue('spring')

    // Wait for debounce
    await new Promise((resolve) => setTimeout(resolve, 350))

    expect(helpStore.searchHelp).toHaveBeenCalledWith('spring')
  })

  it('should navigate to article when search result clicked', async () => {
    const wrapper = mount(HelpCenter, {
      global: {
        plugins: [router, pinia],
        stubs: {
          RouterView: true,
        },
      },
    })

    const helpStore = useHelpStore()
    helpStore.searchResults = [
      {
        article_id: '1',
        slug: 'spring-pattern',
        title: 'Spring Pattern',
        category: 'GLOSSARY',
        snippet: 'Test snippet',
        rank: 0.9,
      },
    ]

    await wrapper.vm.$nextTick()

    const vm = wrapper.vm as any
    await vm.navigateToArticle('spring-pattern')

    expect(router.currentRoute.value.path).toBe('/help/article/spring-pattern')
  })

  it('should display breadcrumb from route meta', async () => {
    router = createRouter({
      history: createMemoryHistory(),
      routes: [
        {
          path: '/help/glossary',
          component: { template: '<div>Glossary</div>' },
          meta: {
            breadcrumb: [{ label: 'Help', to: '/help' }, { label: 'Glossary' }],
          },
        },
      ],
    })

    await router.push('/help/glossary')
    await router.isReady()

    const wrapper = mount(HelpCenter, {
      global: {
        plugins: [router, pinia],
        stubs: {
          RouterView: true,
        },
      },
    })

    expect(wrapper.find('.help-breadcrumb').exists()).toBe(true)
  })
})
