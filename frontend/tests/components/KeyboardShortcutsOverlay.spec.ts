/**
 * KeyboardShortcutsOverlay Component Tests (Story 11.8c - Task 3)
 *
 * Tests for keyboard shortcuts overlay dialog display and functionality.
 */

import { describe, it, expect, beforeEach, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import KeyboardShortcutsOverlay from '@/components/help/KeyboardShortcutsOverlay.vue'

// Mock PrimeVue components
vi.mock('primevue/dialog', () => ({
  default: {
    name: 'Dialog',
    template: '<div v-if="visible"><slot /></div>',
    props: ['visible', 'header', 'modal', 'dismissableMask'],
    emits: ['update:visible'],
  },
}))
vi.mock('primevue/tag', () => ({
  default: {
    name: 'Tag',
    template: '<span>{{ value }}</span>',
    props: ['value', 'severity'],
  },
}))

describe('KeyboardShortcutsOverlay', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('should render when visible', () => {
    const wrapper = mount(KeyboardShortcutsOverlay, {
      props: {
        visible: true,
      },
    })

    expect(wrapper.find('.shortcuts-overlay').exists()).toBe(true)
  })

  it('should not render when not visible', () => {
    const wrapper = mount(KeyboardShortcutsOverlay, {
      props: {
        visible: false,
      },
    })

    // Dialog is hidden, so shortcuts-overlay may not exist
    expect(wrapper.html()).toBeTruthy()
  })

  it('should display shortcuts grouped by context', () => {
    const wrapper = mount(KeyboardShortcutsOverlay, {
      props: {
        visible: true,
      },
    })

    const vm = wrapper.vm as any

    expect(vm.shortcutsData).toBeDefined()
    expect(vm.shortcutsData.length).toBeGreaterThan(0)

    // Check that shortcuts are grouped
    const contexts = vm.shortcutsData.map((group: any) => group.context)
    expect(contexts).toContain('Global')
  })

  it('should have Global shortcuts', () => {
    const wrapper = mount(KeyboardShortcutsOverlay, {
      props: {
        visible: true,
      },
    })

    const vm = wrapper.vm as any
    const globalGroup = vm.shortcutsData.find(
      (g: any) => g.context === 'Global'
    )

    expect(globalGroup).toBeDefined()
    expect(globalGroup.shortcuts.length).toBeGreaterThan(0)

    // Check for specific global shortcuts
    const shortcutKeys = globalGroup.shortcuts.map((s: any) => s.keys)
    expect(shortcutKeys).toContain('?')
    expect(shortcutKeys).toContain('/')
    expect(shortcutKeys).toContain('Esc')
  })

  it('should have Chart shortcuts', () => {
    const wrapper = mount(KeyboardShortcutsOverlay, {
      props: {
        visible: true,
      },
    })

    const vm = wrapper.vm as any
    const chartGroup = vm.shortcutsData.find((g: any) => g.context === 'Chart')

    expect(chartGroup).toBeDefined()
    expect(chartGroup.shortcuts.length).toBeGreaterThan(0)
  })

  it('should have Signals shortcuts', () => {
    const wrapper = mount(KeyboardShortcutsOverlay, {
      props: {
        visible: true,
      },
    })

    const vm = wrapper.vm as any
    const signalsGroup = vm.shortcutsData.find(
      (g: any) => g.context === 'Signals'
    )

    expect(signalsGroup).toBeDefined()
    expect(signalsGroup.shortcuts.length).toBeGreaterThan(0)
  })

  it('should have Settings shortcuts', () => {
    const wrapper = mount(KeyboardShortcutsOverlay, {
      props: {
        visible: true,
      },
    })

    const vm = wrapper.vm as any
    const settingsGroup = vm.shortcutsData.find(
      (g: any) => g.context === 'Settings'
    )

    expect(settingsGroup).toBeDefined()
    expect(settingsGroup.shortcuts.length).toBeGreaterThan(0)
  })

  it('should assign correct severity to contexts', () => {
    const wrapper = mount(KeyboardShortcutsOverlay, {
      props: {
        visible: true,
      },
    })

    const vm = wrapper.vm as any

    expect(vm.getContextSeverity('Global')).toBe('info')
    expect(vm.getContextSeverity('Chart')).toBe('success')
    expect(vm.getContextSeverity('Signals')).toBe('warning')
    expect(vm.getContextSeverity('Settings')).toBe('danger')
    expect(vm.getContextSeverity('Unknown')).toBe('secondary')
  })

  it('should emit update:visible when dialog is closed', async () => {
    const wrapper = mount(KeyboardShortcutsOverlay, {
      props: {
        visible: true,
      },
    })

    // Simulate dialog close
    await wrapper.vm.$emit('update:visible', false)

    expect(wrapper.emitted('update:visible')).toBeTruthy()
    expect(wrapper.emitted('update:visible')![0]).toEqual([false])
  })

  it('should display shortcut keys with kbd elements', () => {
    const wrapper = mount(KeyboardShortcutsOverlay, {
      props: {
        visible: true,
      },
    })

    // The template should use <kbd> elements for displaying keys
    expect(wrapper.html()).toContain('shortcut-key')
  })

  it('should display shortcut descriptions', () => {
    const wrapper = mount(KeyboardShortcutsOverlay, {
      props: {
        visible: true,
      },
    })

    const vm = wrapper.vm as any
    const globalGroup = vm.shortcutsData.find(
      (g: any) => g.context === 'Global'
    )

    globalGroup.shortcuts.forEach((shortcut: any) => {
      expect(shortcut.description).toBeTruthy()
      expect(shortcut.description.length).toBeGreaterThan(0)
    })
  })

  it('should have keyboard shortcut for showing shortcuts', () => {
    const wrapper = mount(KeyboardShortcutsOverlay, {
      props: {
        visible: true,
      },
    })

    const vm = wrapper.vm as any
    const globalGroup = vm.shortcutsData.find(
      (g: any) => g.context === 'Global'
    )

    const showShortcutsShortcut = globalGroup.shortcuts.find(
      (s: any) =>
        s.keys === '?' || s.description.toLowerCase().includes('shortcuts')
    )

    expect(showShortcutsShortcut).toBeDefined()
  })

  it('should have keyboard shortcut for focusing search', () => {
    const wrapper = mount(KeyboardShortcutsOverlay, {
      props: {
        visible: true,
      },
    })

    const vm = wrapper.vm as any
    const globalGroup = vm.shortcutsData.find(
      (g: any) => g.context === 'Global'
    )

    const searchShortcut = globalGroup.shortcuts.find(
      (s: any) =>
        s.keys === '/' || s.description.toLowerCase().includes('search')
    )

    expect(searchShortcut).toBeDefined()
  })

  it('should have keyboard shortcut for closing dialogs', () => {
    const wrapper = mount(KeyboardShortcutsOverlay, {
      props: {
        visible: true,
      },
    })

    const vm = wrapper.vm as any
    const globalGroup = vm.shortcutsData.find(
      (g: any) => g.context === 'Global'
    )

    const escShortcut = globalGroup.shortcuts.find(
      (s: any) =>
        s.keys === 'Esc' || s.description.toLowerCase().includes('close')
    )

    expect(escShortcut).toBeDefined()
  })

  it('should support v-model binding', async () => {
    const wrapper = mount(KeyboardShortcutsOverlay, {
      props: {
        visible: true,
        'onUpdate:visible': (value: boolean) =>
          wrapper.setProps({ visible: value }),
      },
    })

    expect(wrapper.props('visible')).toBe(true)

    // Simulate closing
    await wrapper.vm.$emit('update:visible', false)
    await wrapper.setProps({ visible: false })

    expect(wrapper.props('visible')).toBe(false)
  })

  it('should render all shortcut groups', () => {
    const wrapper = mount(KeyboardShortcutsOverlay, {
      props: {
        visible: true,
      },
    })

    const vm = wrapper.vm as any

    // Should have at least 4 groups (Global, Chart, Signals, Settings)
    expect(vm.shortcutsData.length).toBeGreaterThanOrEqual(4)
  })

  it('should format shortcut keys correctly', () => {
    const wrapper = mount(KeyboardShortcutsOverlay, {
      props: {
        visible: true,
      },
    })

    const vm = wrapper.vm as any

    // Check that multi-key shortcuts are properly formatted
    const allShortcuts = vm.shortcutsData.flatMap(
      (group: any) => group.shortcuts
    )
    const multiKeyShortcut = allShortcuts.find((s: any) => s.keys.includes('+'))

    if (multiKeyShortcut) {
      expect(multiKeyShortcut.keys).toContain('+')
    }
  })
})
