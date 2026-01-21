/**
 * HelpIcon Component Tests (Story 11.8a - Task 13)
 *
 * Tests for HelpIcon dialog, feedback, and article display.
 */

import { describe, it, expect, beforeEach, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { createRouter, createMemoryHistory } from 'vue-router'
import HelpIcon from '@/components/help/HelpIcon.vue'
import { useHelpStore } from '@/stores/helpStore'
import type { HelpArticle } from '@/stores/helpStore'

// Mock PrimeVue components
vi.mock('primevue/button', () => ({
  default: {
    name: 'Button',
    template:
      '<button :class="$attrs.class" :disabled="disabled" @click="$emit(\'click\')">{{ label }}<slot /></button>',
    props: ['label', 'icon', 'disabled'],
    emits: ['click'],
  },
}))
vi.mock('primevue/dialog', () => ({
  default: {
    name: 'Dialog',
    template:
      '<div v-if="visible" class="dialog-wrapper"><slot /><slot name="footer" /></div>',
    props: [
      'visible',
      'header',
      'modal',
      'closable',
      'dismissableMask',
      'draggable',
      'style',
    ],
    emits: ['update:visible', 'hide'],
  },
}))
vi.mock('primevue/message', () => ({
  default: {
    name: 'Message',
    template: '<div class="message"><slot /></div>',
    props: ['severity', 'closable'],
  },
}))
vi.mock('primevue/textarea', () => ({
  default: {
    name: 'Textarea',
    template:
      '<textarea class="comment-input" :value="modelValue" @input="$emit(\'update:modelValue\', $event.target.value)"></textarea>',
    props: ['modelValue', 'placeholder', 'autoResize', 'rows'],
    emits: ['update:modelValue'],
  },
}))

describe('HelpIcon', () => {
  let pinia: ReturnType<typeof createPinia>
  let router: unknown

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
        {
          path: '/help/article/:slug',
          component: { template: '<div>Article</div>' },
        },
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
    vi.spyOn(helpStore, 'fetchArticle').mockResolvedValue()

    const wrapper = mount(HelpIcon, {
      props: {
        articleSlug: 'test-article',
      },
      global: {
        plugins: [pinia, router],
      },
    })

    // Open dialog by clicking the button
    const button = wrapper.find('.help-icon-btn')
    await button.trigger('click')
    await wrapper.vm.$nextTick()

    expect(wrapper.find('.article-html').exists()).toBe(true)
  })

  it('should display loading state', async () => {
    const helpStore = useHelpStore()
    // Mock fetchArticle to not resolve immediately so isLoading stays true
    vi.spyOn(helpStore, 'fetchArticle').mockImplementation(() => {
      helpStore.isLoading = true
      return new Promise(() => {}) // Never resolves
    })

    const wrapper = mount(HelpIcon, {
      props: {
        articleSlug: 'test-article',
      },
      global: {
        plugins: [pinia, router],
      },
    })

    // Open dialog by clicking the button
    const button = wrapper.find('.help-icon-btn')
    await button.trigger('click')
    await wrapper.vm.$nextTick()

    expect(wrapper.find('.dialog-loading').exists()).toBe(true)
  })

  it('should display error state', async () => {
    const helpStore = useHelpStore()
    vi.spyOn(helpStore, 'fetchArticle').mockImplementation(async () => {
      helpStore.error = 'Failed to load article'
    })

    const wrapper = mount(HelpIcon, {
      props: {
        articleSlug: 'test-article',
      },
      global: {
        plugins: [pinia, router],
      },
    })

    // Open dialog by clicking the button
    const button = wrapper.find('.help-icon-btn')
    await button.trigger('click')
    await wrapper.vm.$nextTick()

    expect(wrapper.text()).toContain('Failed to load article')
  })

  it('should submit positive feedback', async () => {
    const helpStore = useHelpStore()
    helpStore.currentArticle = mockArticle
    vi.spyOn(helpStore, 'fetchArticle').mockResolvedValue()
    vi.spyOn(helpStore, 'submitFeedback').mockResolvedValue(true)

    const wrapper = mount(HelpIcon, {
      props: {
        articleSlug: 'test-article',
      },
      global: {
        plugins: [pinia, router],
      },
    })

    // Open dialog by clicking the button
    const button = wrapper.find('.help-icon-btn')
    await button.trigger('click')
    await wrapper.vm.$nextTick()

    // Find and click the Yes (thumbs up) button
    const yesButton = wrapper
      .findAll('button')
      .find((b) => b.text().includes('Yes'))
    expect(yesButton).toBeDefined()
    await yesButton!.trigger('click')

    expect(helpStore.submitFeedback).toHaveBeenCalledWith(
      'article-123',
      true,
      undefined
    )
  })

  it('should show comment input on negative feedback', async () => {
    const helpStore = useHelpStore()
    helpStore.currentArticle = mockArticle
    vi.spyOn(helpStore, 'fetchArticle').mockResolvedValue()

    const wrapper = mount(HelpIcon, {
      props: {
        articleSlug: 'test-article',
      },
      global: {
        plugins: [pinia, router],
      },
    })

    // Open dialog by clicking the button
    const button = wrapper.find('.help-icon-btn')
    await button.trigger('click')
    await wrapper.vm.$nextTick()

    // Find and click the No (thumbs down) button to show comment input
    const noButton = wrapper
      .findAll('button')
      .find((b) => b.text().includes('No'))
    expect(noButton).toBeDefined()
    await noButton!.trigger('click')
    await wrapper.vm.$nextTick()

    expect(wrapper.find('.comment-input').exists()).toBe(true)
  })

  it('should submit negative feedback with comment', async () => {
    const helpStore = useHelpStore()
    helpStore.currentArticle = mockArticle
    vi.spyOn(helpStore, 'fetchArticle').mockResolvedValue()
    vi.spyOn(helpStore, 'submitFeedback').mockResolvedValue(true)

    const wrapper = mount(HelpIcon, {
      props: {
        articleSlug: 'test-article',
      },
      global: {
        plugins: [pinia, router],
      },
    })

    // Open dialog by clicking the button
    const button = wrapper.find('.help-icon-btn')
    await button.trigger('click')
    await wrapper.vm.$nextTick()

    // Click No button to show comment input
    const noButton = wrapper
      .findAll('button')
      .find((b) => b.text().includes('No'))
    await noButton!.trigger('click')
    await wrapper.vm.$nextTick()

    // Fill in comment (mock textarea since it's stubbed)
    const textarea = wrapper.find('textarea')
    await textarea.setValue('Needs improvement')

    // Click Submit button
    const submitButton = wrapper
      .findAll('button')
      .find((b) => b.text().includes('Submit'))
    await submitButton!.trigger('click')

    expect(helpStore.submitFeedback).toHaveBeenCalledWith(
      'article-123',
      false,
      'Needs improvement'
    )
  })

  it('should show thank you message after feedback', async () => {
    const helpStore = useHelpStore()
    helpStore.currentArticle = mockArticle
    vi.spyOn(helpStore, 'fetchArticle').mockResolvedValue()
    vi.spyOn(helpStore, 'submitFeedback').mockResolvedValue(true)

    const wrapper = mount(HelpIcon, {
      props: {
        articleSlug: 'test-article',
      },
      global: {
        plugins: [pinia, router],
      },
    })

    // Open dialog by clicking the button
    const button = wrapper.find('.help-icon-btn')
    await button.trigger('click')
    await wrapper.vm.$nextTick()

    // Find and click the Yes (thumbs up) button
    const yesButton = wrapper
      .findAll('button')
      .find((b) => b.text().includes('Yes'))
    await yesButton!.trigger('click')
    await wrapper.vm.$nextTick()

    expect(wrapper.text()).toContain('Thanks for your feedback!')
  })

  it('should reset feedback state on dialog hide', async () => {
    const helpStore = useHelpStore()
    helpStore.currentArticle = mockArticle
    vi.spyOn(helpStore, 'fetchArticle').mockResolvedValue()
    vi.spyOn(helpStore, 'submitFeedback').mockResolvedValue(true)

    const wrapper = mount(HelpIcon, {
      props: {
        articleSlug: 'test-article',
      },
      global: {
        plugins: [pinia, router],
      },
    })

    // Open dialog
    const button = wrapper.find('.help-icon-btn')
    await button.trigger('click')
    await wrapper.vm.$nextTick()

    // Submit feedback to set feedbackSubmitted = true
    const yesButton = wrapper
      .findAll('button')
      .find((b) => b.text().includes('Yes'))
    await yesButton!.trigger('click')
    await wrapper.vm.$nextTick()

    // Verify thank you message is shown
    expect(wrapper.text()).toContain('Thanks for your feedback!')

    // Open dialog again (which should reset state)
    await button.trigger('click')
    await wrapper.vm.$nextTick()

    // Feedback buttons should be visible again (state was reset)
    const yesButtonAfterReopen = wrapper
      .findAll('button')
      .find((b) => b.text().includes('Yes'))
    expect(yesButtonAfterReopen).toBeDefined()
  })
})
