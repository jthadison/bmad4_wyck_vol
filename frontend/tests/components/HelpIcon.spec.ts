/**
 * HelpIcon Component Tests (Story 11.8a - Task 13)
 *
 * Tests for HelpIcon dialog, feedback, and article display.
 */

import { describe, it, expect, beforeEach, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { setActivePinia, createPinia } from 'pinia'
import { createRouter, createMemoryHistory } from 'vue-router'
import HelpIcon from '@/components/help/HelpIcon.vue'
import { useHelpStore } from '@/stores/helpStore'
import type { HelpArticle } from '@/stores/helpStore'

// Mock PrimeVue components
vi.mock('primevue/button', () => ({
  default: { name: 'Button', template: '<button><slot /></button>' },
}))
vi.mock('primevue/dialog', () => ({
  default: { name: 'Dialog', template: '<div v-if="visible"><slot /><slot name="footer" /></div>', props: ['visible'] },
}))
vi.mock('primevue/message', () => ({
  default: { name: 'Message', template: '<div><slot /></div>' },
}))
vi.mock('primevue/textarea', () => ({
  default: { name: 'Textarea', template: '<textarea></textarea>' },
}))

describe('HelpIcon', () => {
  let pinia: any
  let router: any

  const mockArticle: HelpArticle = {
    id: 'article-123',
    slug: 'test-article',
    title: 'Test Article',
    content_markdown: '# Test',
    content_html: '<h1>Test</h1><p>This is a test article.</p>',
    category: 'FAQ',
    tags: ['test'],
    keywords: 'test',
    last_updated: '2024-03-13T10:00:00Z',
    view_count: 10,
    helpful_count: 5,
    not_helpful_count: 1,
  }

  beforeEach(() => {
    pinia = createPinia()
    setActivePinia(pinia)

    router = createRouter({
      history: createMemoryHistory(),
      routes: [
        { path: '/help/article/:slug', component: { template: '<div>Article</div>' } },
      ],
    })

    vi.clearAllMocks()
  })

  it('should render help icon button', () => {
    const wrapper = mount(HelpIcon, {
      props: {
        articleSlug: 'test-article',
      },
      global: {
        plugins: [pinia, router],
      },
    })

    expect(wrapper.find('.help-icon-btn').exists()).toBe(true)
  })

  it('should open dialog on button click', async () => {
    const helpStore = useHelpStore()
    vi.spyOn(helpStore, 'fetchArticle').mockResolvedValue()

    const wrapper = mount(HelpIcon, {
      props: {
        articleSlug: 'test-article',
      },
      global: {
        plugins: [pinia, router],
      },
    })

    const button = wrapper.find('.help-icon-btn')
    await button.trigger('click')

    expect(helpStore.fetchArticle).toHaveBeenCalledWith('test-article')
  })

  it('should display article content in dialog', async () => {
    const helpStore = useHelpStore()
    helpStore.currentArticle = mockArticle

    const wrapper = mount(HelpIcon, {
      props: {
        articleSlug: 'test-article',
      },
      global: {
        plugins: [pinia, router],
      },
    })

    // Open dialog
    wrapper.vm.$data.dialogVisible = true
    await wrapper.vm.$nextTick()

    expect(wrapper.find('.article-html').exists()).toBe(true)
  })

  it('should display loading state', async () => {
    const helpStore = useHelpStore()
    helpStore.isLoading = true

    const wrapper = mount(HelpIcon, {
      props: {
        articleSlug: 'test-article',
      },
      global: {
        plugins: [pinia, router],
      },
    })

    await wrapper.vm.$data.dialogVisible = true
    await wrapper.vm.$nextTick()

    expect(wrapper.find('.dialog-loading').exists()).toBe(true)
  })

  it('should display error state', async () => {
    const helpStore = useHelpStore()
    helpStore.error = 'Failed to load article'

    const wrapper = mount(HelpIcon, {
      props: {
        articleSlug: 'test-article',
      },
      global: {
        plugins: [pinia, router],
      },
    })

    await wrapper.vm.$data.dialogVisible = true
    await wrapper.vm.$nextTick()

    expect(wrapper.text()).toContain('Failed to load article')
  })

  it('should submit positive feedback', async () => {
    const helpStore = useHelpStore()
    helpStore.currentArticle = mockArticle
    vi.spyOn(helpStore, 'submitFeedback').mockResolvedValue(true)

    const wrapper = mount(HelpIcon, {
      props: {
        articleSlug: 'test-article',
      },
      global: {
        plugins: [pinia, router],
      },
    })

    await wrapper.vm.$data.dialogVisible = true
    await wrapper.vm.$nextTick()

    const vm = wrapper.vm as any
    await vm.submitFeedback(true)

    expect(helpStore.submitFeedback).toHaveBeenCalledWith('article-123', true, undefined)
  })

  it('should show comment input on negative feedback', async () => {
    const helpStore = useHelpStore()
    helpStore.currentArticle = mockArticle

    const wrapper = mount(HelpIcon, {
      props: {
        articleSlug: 'test-article',
      },
      global: {
        plugins: [pinia, router],
      },
    })

    await wrapper.vm.$data.dialogVisible = true
    await wrapper.vm.$nextTick()

    await wrapper.vm.$data.showCommentInput = true
    await wrapper.vm.$nextTick()

    expect(wrapper.find('.comment-input').exists()).toBe(true)
  })

  it('should submit negative feedback with comment', async () => {
    const helpStore = useHelpStore()
    helpStore.currentArticle = mockArticle
    vi.spyOn(helpStore, 'submitFeedback').mockResolvedValue(true)

    const wrapper = mount(HelpIcon, {
      props: {
        articleSlug: 'test-article',
      },
      global: {
        plugins: [pinia, router],
      },
    })

    await wrapper.vm.$data.dialogVisible = true
    await wrapper.vm.$data.feedbackComment = 'Needs improvement'
    await wrapper.vm.$nextTick()

    const vm = wrapper.vm as any
    await vm.submitFeedback(false)

    expect(helpStore.submitFeedback).toHaveBeenCalledWith(
      'article-123',
      false,
      'Needs improvement'
    )
  })

  it('should show thank you message after feedback', async () => {
    const helpStore = useHelpStore()
    helpStore.currentArticle = mockArticle
    vi.spyOn(helpStore, 'submitFeedback').mockResolvedValue(true)

    const wrapper = mount(HelpIcon, {
      props: {
        articleSlug: 'test-article',
      },
      global: {
        plugins: [pinia, router],
      },
    })

    await wrapper.vm.$data.dialogVisible = true
    await wrapper.vm.$nextTick()

    const vm = wrapper.vm as any
    await vm.submitFeedback(true)
    await wrapper.vm.$nextTick()

    expect(wrapper.text()).toContain('Thanks for your feedback!')
  })

  it('should reset feedback state on dialog hide', async () => {
    const wrapper = mount(HelpIcon, {
      props: {
        articleSlug: 'test-article',
      },
      global: {
        plugins: [pinia, router],
      },
    })

    await wrapper.vm.$data.feedbackSubmitted = true
    await wrapper.vm.$data.showCommentInput = true
    await wrapper.vm.$data.feedbackComment = 'Test comment'

    const vm = wrapper.vm as any
    vm.onDialogHide()

    expect(wrapper.vm.$data.feedbackSubmitted).toBe(false)
    expect(wrapper.vm.$data.showCommentInput).toBe(false)
    expect(wrapper.vm.$data.feedbackComment).toBe('')
  })
})
