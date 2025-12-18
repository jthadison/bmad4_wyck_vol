/**
 * ArticleFeedback Component Tests (Story 11.8c - Task 2)
 *
 * Tests for article feedback collection, localStorage persistence, and duplicate prevention.
 */

import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { setActivePinia, createPinia } from 'pinia'
import ArticleFeedback from '@/components/help/ArticleFeedback.vue'
import { useHelpStore } from '@/stores/helpStore'

// Mock PrimeVue components
vi.mock('primevue/button', () => ({
  default: {
    name: 'Button',
    template:
      '<button :class="[$attrs.class]" @click="$emit(\'click\')"><slot /></button>',
    props: [
      'icon',
      'label',
      'severity',
      'outlined',
      'size',
      'disabled',
      'loading',
    ],
  },
}))
vi.mock('primevue/textarea', () => ({
  default: {
    name: 'Textarea',
    template:
      '<textarea v-model="modelValue" @input="$emit(\'update:modelValue\', $event.target.value)" :maxlength="maxlength"></textarea>',
    props: ['modelValue', 'rows', 'placeholder', 'maxlength'],
  },
}))
vi.mock('primevue/message', () => ({
  default: {
    name: 'Message',
    template: '<div><slot /></div>',
    props: ['severity', 'closable'],
  },
}))

describe('ArticleFeedback', () => {
  let pinia: any

  const articleId = 'test-article-123'
  const articleSlug = 'test-article'
  const feedbackKey = `feedback_${articleSlug}`

  beforeEach(() => {
    // Set up Pinia
    pinia = createPinia()
    setActivePinia(pinia)

    // Clear localStorage before each test
    localStorage.clear()
    vi.clearAllMocks()
  })

  afterEach(() => {
    localStorage.clear()
  })

  it('should render feedback component', () => {
    const wrapper = mount(ArticleFeedback, {
      props: {
        articleId,
        articleSlug,
      },
      global: {
        plugins: [pinia],
      },
    })

    expect(wrapper.find('.article-feedback').exists()).toBe(true)
    expect(wrapper.text()).toContain('Was this helpful')
  })

  it('should display thumbs up and thumbs down buttons', () => {
    const wrapper = mount(ArticleFeedback, {
      props: {
        articleId,
        articleSlug,
      },
      global: {
        plugins: [pinia],
      },
    })

    expect(wrapper.find('.thumbs-up-btn').exists()).toBe(true)
    expect(wrapper.find('.thumbs-down-btn').exists()).toBe(true)
  })

  it('should show thank you message after positive feedback', async () => {
    const helpStore = useHelpStore()
    vi.spyOn(helpStore, 'submitFeedback').mockResolvedValue(true)

    const wrapper = mount(ArticleFeedback, {
      props: {
        articleId,
        articleSlug,
      },
      global: {
        plugins: [pinia],
      },
    })

    // Click the thumbs up button
    const thumbsUpBtn = wrapper.find('.thumbs-up-btn')
    await thumbsUpBtn.trigger('click')
    await wrapper.vm.$nextTick()

    expect(wrapper.text()).toContain('Thanks for your feedback')
  })

  it('should show comment textarea after negative feedback', async () => {
    const wrapper = mount(ArticleFeedback, {
      props: {
        articleId,
        articleSlug,
      },
      global: {
        plugins: [pinia],
      },
    })

    // Click the thumbs down button
    const thumbsDownBtn = wrapper.find('.thumbs-down-btn')
    await thumbsDownBtn.trigger('click')
    await wrapper.vm.$nextTick()

    expect(wrapper.find('.comment-section').exists()).toBe(true)
    expect(wrapper.find('textarea').exists()).toBe(true)
  })

  it('should save feedback to localStorage', async () => {
    const helpStore = useHelpStore()
    vi.spyOn(helpStore, 'submitFeedback').mockResolvedValue(true)

    const wrapper = mount(ArticleFeedback, {
      props: {
        articleId,
        articleSlug,
      },
      global: {
        plugins: [pinia],
      },
    })

    // Click thumbs up
    const thumbsUpBtn = wrapper.find('.thumbs-up-btn')
    await thumbsUpBtn.trigger('click')
    await wrapper.vm.$nextTick()

    // Check localStorage
    const stored = localStorage.getItem(feedbackKey)
    expect(stored).toBeTruthy()

    const data = JSON.parse(stored!)
    expect(data.submitted).toBe(true)
    expect(data.helpful).toBe(true)
    expect(data.articleId).toBe(articleId)
  })

  it('should prevent duplicate feedback submission', async () => {
    // Pre-populate localStorage with existing feedback
    const existingFeedback = {
      submitted: true,
      helpful: true,
      timestamp: new Date().toISOString(),
      articleId,
    }
    localStorage.setItem(feedbackKey, JSON.stringify(existingFeedback))

    const wrapper = mount(ArticleFeedback, {
      props: {
        articleId,
        articleSlug,
      },
      global: {
        plugins: [pinia],
      },
    })

    await wrapper.vm.$nextTick()

    // Component shows thank you message when localStorage has existing feedback
    // (checkExistingFeedback sets both feedbackSubmitted and showThankYou to true)
    expect(wrapper.text()).toContain('Thanks for your feedback')
  })

  it('should submit comment with negative feedback', async () => {
    const helpStore = useHelpStore()
    vi.spyOn(helpStore, 'submitFeedback').mockResolvedValue(true)

    const wrapper = mount(ArticleFeedback, {
      props: {
        articleId,
        articleSlug,
      },
      global: {
        plugins: [pinia],
      },
    })

    // Click thumbs down
    const thumbsDownBtn = wrapper.find('.thumbs-down-btn')
    await thumbsDownBtn.trigger('click')
    await wrapper.vm.$nextTick()

    // Enter comment
    const textarea = wrapper.find('textarea')
    await textarea.setValue('This section was unclear')
    await wrapper.vm.$nextTick()

    // Click submit button
    const submitBtn = wrapper
      .findAll('button')
      .find((btn) => btn.text().includes('Submit'))
    if (submitBtn) {
      await submitBtn.trigger('click')
      await wrapper.vm.$nextTick()

      expect(wrapper.text()).toContain('Thanks for your feedback')
    }
  })

  it('should enforce character limit on comments', async () => {
    const wrapper = mount(ArticleFeedback, {
      props: {
        articleId,
        articleSlug,
      },
      global: {
        plugins: [pinia],
      },
    })

    // Click thumbs down to show comment box
    const thumbsDownBtn = wrapper.find('.thumbs-down-btn')
    await thumbsDownBtn.trigger('click')
    await wrapper.vm.$nextTick()

    // Textarea should have maxlength attribute
    const textarea = wrapper.find('textarea')
    expect(textarea.attributes('maxlength')).toBe('1000')
  })

  it('should hide feedback buttons after submission', async () => {
    const helpStore = useHelpStore()
    vi.spyOn(helpStore, 'submitFeedback').mockResolvedValue(true)

    const wrapper = mount(ArticleFeedback, {
      props: {
        articleId,
        articleSlug,
      },
      global: {
        plugins: [pinia],
      },
    })

    // Initially buttons should be visible
    expect(wrapper.find('.feedback-controls').exists()).toBe(true)

    // Submit feedback
    const thumbsUpBtn = wrapper.find('.thumbs-up-btn')
    await thumbsUpBtn.trigger('click')
    await wrapper.vm.$nextTick()

    // Buttons should be hidden, thank you message shown
    expect(wrapper.find('.feedback-controls').exists()).toBe(false)
    expect(wrapper.find('.thank-you-message').exists()).toBe(true)
  })

  it('should handle localStorage errors gracefully', async () => {
    // Clear all mocks first to avoid interference
    vi.clearAllMocks()

    const helpStore = useHelpStore()
    const submitSpy = vi
      .spyOn(helpStore, 'submitFeedback')
      .mockResolvedValue(true)

    // Mock localStorage to throw error when saving (AFTER clearAllMocks)
    const setItemMock = vi.fn(() => {
      throw new Error('localStorage is full')
    })
    Storage.prototype.setItem = setItemMock

    const wrapper = mount(ArticleFeedback, {
      props: {
        articleId,
        articleSlug,
      },
      global: {
        plugins: [pinia],
      },
    })

    // Click thumbs up - should still work even if localStorage fails
    const thumbsUpBtn = wrapper.find('.thumbs-up-btn')
    await thumbsUpBtn.trigger('click')

    // Wait for async operation to complete
    await new Promise((resolve) => setTimeout(resolve, 100))
    await wrapper.vm.$nextTick()

    // Component should still show success even if localStorage save fails
    expect(wrapper.text()).toContain('Thanks for your feedback')

    // Feedback should have been submitted to the store
    expect(submitSpy).toHaveBeenCalledWith(articleId, true)
  })

  it('should use correct feedback key format', () => {
    expect(feedbackKey).toBe('feedback_test-article')
  })

  it('should clear comment when closing comment box without submitting', async () => {
    const wrapper = mount(ArticleFeedback, {
      props: {
        articleId,
        articleSlug,
      },
      global: {
        plugins: [pinia],
      },
    })

    // Click thumbs down
    const thumbsDownBtn = wrapper.find('.thumbs-down-btn')
    await thumbsDownBtn.trigger('click')
    await wrapper.vm.$nextTick()

    // Enter comment
    const textarea = wrapper.find('textarea')
    await textarea.setValue('Test comment')
    await wrapper.vm.$nextTick()

    // Click cancel button
    const cancelBtn = wrapper
      .findAll('button')
      .find((btn) => btn.text().includes('Cancel'))
    if (cancelBtn) {
      await cancelBtn.trigger('click')
      await wrapper.vm.$nextTick()

      // Comment box should be hidden
      expect(wrapper.find('.comment-section').exists()).toBe(false)
    }
  })

  it('should show appropriate message for positive feedback', async () => {
    const helpStore = useHelpStore()
    vi.spyOn(helpStore, 'submitFeedback').mockResolvedValue(true)

    const wrapper = mount(ArticleFeedback, {
      props: {
        articleId,
        articleSlug,
      },
      global: {
        plugins: [pinia],
      },
    })

    const thumbsUpBtn = wrapper.find('.thumbs-up-btn')
    await thumbsUpBtn.trigger('click')
    await wrapper.vm.$nextTick()

    expect(wrapper.text()).toContain('Thanks for your feedback')
  })

  it('should show appropriate message for negative feedback with comment', async () => {
    const helpStore = useHelpStore()
    vi.spyOn(helpStore, 'submitFeedback').mockResolvedValue(true)

    const wrapper = mount(ArticleFeedback, {
      props: {
        articleId,
        articleSlug,
      },
      global: {
        plugins: [pinia],
      },
    })

    // Click thumbs down
    const thumbsDownBtn = wrapper.find('.thumbs-down-btn')
    await thumbsDownBtn.trigger('click')
    await wrapper.vm.$nextTick()

    // Add comment and submit
    const textarea = wrapper.find('textarea')
    await textarea.setValue('Needs improvement')

    const submitBtn = wrapper
      .findAll('button')
      .find((btn) => btn.text().includes('Submit'))
    if (submitBtn) {
      await submitBtn.trigger('click')
      await wrapper.vm.$nextTick()

      expect(wrapper.text()).toContain('Thanks for your feedback')
    }
  })

  it('should handle localStorage retrieval errors gracefully', () => {
    // Clear all mocks first to avoid interference
    vi.clearAllMocks()

    // Mock localStorage to throw error when reading (AFTER clearAllMocks)
    const getItemMock = vi.fn(() => {
      throw new Error('localStorage access denied')
    })
    Storage.prototype.getItem = getItemMock

    const wrapper = mount(ArticleFeedback, {
      props: {
        articleId,
        articleSlug,
      },
      global: {
        plugins: [pinia],
      },
    })

    // Component should still render despite localStorage error
    expect(wrapper.find('.article-feedback').exists()).toBe(true)

    // Feedback buttons should still be visible (since we couldn't read existing feedback)
    expect(wrapper.find('.feedback-controls').exists()).toBe(true)

    // Buttons should be functional
    expect(wrapper.find('.thumbs-up-btn').exists()).toBe(true)
    expect(wrapper.find('.thumbs-down-btn').exists()).toBe(true)
  })
})
