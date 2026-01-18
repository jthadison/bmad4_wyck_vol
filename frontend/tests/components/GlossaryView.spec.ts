/**
 * GlossaryView Component Tests (Story 11.8a - Task 12)
 *
 * Tests for GlossaryView filtering, expansion, and navigation.
 */

import { createPinia } from 'pinia'
import { describe, it, expect, beforeEach, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { setActivePinia, createPinia } from 'pinia'
import GlossaryView from '@/components/help/GlossaryView.vue'
import { useHelpStore } from '@/stores/helpStore'
import type { GlossaryTerm } from '@/stores/helpStore'

// Mock PrimeVue components
vi.mock('primevue/dropdown', () => ({
  default: { name: 'Dropdown', template: '<select><slot /></select>' },
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
vi.mock('primevue/dataview', () => ({
  default: {
    name: 'DataView',
    template: '<div><slot name="list" :items="value" /></div>',
    props: ['value'],
  },
}))
vi.mock('primevue/button', () => ({
  default: { name: 'Button', template: '<button><slot /></button>' },
}))
vi.mock('primevue/tag', () => ({
  default: { name: 'Tag', template: '<span></span>' },
}))
vi.mock('primevue/chip', () => ({
  default: { name: 'Chip', template: '<span></span>' },
}))
vi.mock('primevue/message', () => ({
  default: { name: 'Message', template: '<div><slot /></div>' },
}))

describe('GlossaryView', () => {
  let pinia: ReturnType<typeof createPinia>

  const mockTerms: GlossaryTerm[] = [
    {
      id: '1',
      term: 'Spring',
      slug: 'spring',
      short_definition: 'A price move below support',
      full_description: 'Full description of Spring',
      full_description_html: '<p>Full description of Spring</p>',
      wyckoff_phase: 'C',
      related_terms: ['utad', 'creek'],
      tags: ['pattern', 'accumulation'],
      last_updated: '2024-03-13T10:00:00Z',
    },
    {
      id: '2',
      term: 'UTAD',
      slug: 'utad',
      short_definition: 'Upthrust After Distribution',
      full_description: 'Full description of UTAD',
      full_description_html: '<p>Full description of UTAD</p>',
      wyckoff_phase: 'C',
      related_terms: ['spring'],
      tags: ['pattern', 'distribution'],
      last_updated: '2024-03-13T10:00:00Z',
    },
    {
      id: '3',
      term: 'Creek',
      slug: 'creek',
      short_definition: 'Support level penetration',
      full_description: 'Full description of Creek',
      full_description_html: '<p>Full description of Creek</p>',
      wyckoff_phase: null,
      related_terms: ['spring'],
      tags: ['level'],
      last_updated: '2024-03-13T10:00:00Z',
    },
  ]

  beforeEach(() => {
    pinia = createPinia()
    setActivePinia(pinia)
    vi.clearAllMocks()
  })

  it('should render glossary view', () => {
    const wrapper = mount(GlossaryView, {
      global: {
        plugins: [pinia],
      },
    })

    expect(wrapper.find('.glossary-view').exists()).toBe(true)
    expect(wrapper.find('.glossary-title').text()).toBe('Wyckoff Glossary')
  })

  it('should display filters', () => {
    const wrapper = mount(GlossaryView, {
      global: {
        plugins: [pinia],
      },
    })

    expect(wrapper.find('.glossary-filters').exists()).toBe(true)
    expect(wrapper.find('#phase-filter').exists()).toBe(true)
    expect(wrapper.find('#search-filter').exists()).toBe(true)
  })

  it('should display alphabetical index', () => {
    const wrapper = mount(GlossaryView, {
      global: {
        plugins: [pinia],
      },
    })

    expect(wrapper.find('.alpha-index').exists()).toBe(true)
  })

  it('should filter terms by phase', async () => {
    const helpStore = useHelpStore()
    helpStore.glossaryTerms = mockTerms

    const wrapper = mount(GlossaryView, {
      global: {
        plugins: [pinia],
      },
    })

    // Set phase filter to C
    wrapper.vm.$data.selectedPhase = 'C'
    await wrapper.vm.$nextTick()

    const vm = wrapper.vm as unknown
    expect(vm.filteredTerms).toHaveLength(2)
    expect(
      vm.filteredTerms.every((t: GlossaryTerm) => t.wyckoff_phase === 'C')
    ).toBe(true)
  })

  it('should filter terms by search query', async () => {
    const helpStore = useHelpStore()
    helpStore.glossaryTerms = mockTerms

    const wrapper = mount(GlossaryView, {
      global: {
        plugins: [pinia],
      },
    })

    wrapper.vm.$data.searchFilter = 'spring'
    await wrapper.vm.$nextTick()

    const vm = wrapper.vm as unknown
    expect(vm.filteredTerms).toHaveLength(1)
    expect(vm.filteredTerms[0].term).toBe('Spring')
  })

  it('should sort terms alphabetically', async () => {
    const helpStore = useHelpStore()
    helpStore.glossaryTerms = [...mockTerms].reverse() // Reverse order

    const wrapper = mount(GlossaryView, {
      global: {
        plugins: [pinia],
      },
    })

    const vm = wrapper.vm as unknown
    const sortedTerms = vm.filteredTerms

    expect(sortedTerms[0].term).toBe('Creek')
    expect(sortedTerms[1].term).toBe('Spring')
    expect(sortedTerms[2].term).toBe('UTAD')
  })

  it('should toggle term expansion', async () => {
    const helpStore = useHelpStore()
    helpStore.glossaryTerms = mockTerms

    const wrapper = mount(GlossaryView, {
      global: {
        plugins: [pinia],
      },
    })

    const vm = wrapper.vm as unknown

    // Initially not expanded
    expect(vm.expandedTermId).toBeNull()

    // Expand term
    vm.toggleTerm('1')
    await wrapper.vm.$nextTick()
    expect(vm.expandedTermId).toBe('1')

    // Collapse term
    vm.toggleTerm('1')
    await wrapper.vm.$nextTick()
    expect(vm.expandedTermId).toBeNull()
  })

  it('should get correct phase severity', () => {
    const wrapper = mount(GlossaryView, {
      global: {
        plugins: [pinia],
      },
    })

    const vm = wrapper.vm as unknown

    expect(vm.getPhaseSeverity('A')).toBe('danger')
    expect(vm.getPhaseSeverity('B')).toBe('warning')
    expect(vm.getPhaseSeverity('C')).toBe('info')
    expect(vm.getPhaseSeverity('D')).toBe('success')
    expect(vm.getPhaseSeverity('E')).toBe('secondary')
  })

  it('should check if terms start with a letter', async () => {
    const helpStore = useHelpStore()
    helpStore.glossaryTerms = mockTerms

    const wrapper = mount(GlossaryView, {
      global: {
        plugins: [pinia],
      },
    })

    const vm = wrapper.vm as unknown

    expect(vm.hasTermsStartingWith('S')).toBe(true)
    expect(vm.hasTermsStartingWith('U')).toBe(true)
    expect(vm.hasTermsStartingWith('C')).toBe(true)
    expect(vm.hasTermsStartingWith('Z')).toBe(false)
  })

  it('should display empty state when no terms', async () => {
    const helpStore = useHelpStore()
    helpStore.glossaryTerms = []

    const wrapper = mount(GlossaryView, {
      global: {
        plugins: [pinia],
      },
    })

    await wrapper.vm.$nextTick()

    expect(wrapper.text()).toContain('No terms found')
  })

  it('should display loading state', async () => {
    const helpStore = useHelpStore()
    helpStore.isLoading = true

    const wrapper = mount(GlossaryView, {
      global: {
        plugins: [pinia],
      },
    })

    expect(wrapper.find('.loading-state').exists()).toBe(true)
    expect(wrapper.text()).toContain('Loading glossary terms')
  })

  it('should display error state', async () => {
    const helpStore = useHelpStore()
    helpStore.error = 'Failed to load glossary'

    const wrapper = mount(GlossaryView, {
      global: {
        plugins: [pinia],
      },
    })

    expect(wrapper.text()).toContain('Failed to load glossary')
  })
})
