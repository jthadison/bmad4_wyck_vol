/**
 * Keyboard Shortcuts Composable (Story 11.8c - Task 4)
 *
 * Purpose:
 * --------
 * Provides global keyboard shortcut handling for the application.
 * Registers event listeners for common shortcuts and manages overlay visibility.
 *
 * Features:
 * ---------
 * - "?" key → Show keyboard shortcuts overlay
 * - "/" key → Focus search input (querySelector('[data-search-input]'))
 * - "Esc" key → Close overlays/dialogs
 * - "Ctrl+K" / "Cmd+K" → Command palette (placeholder for future)
 * - Ignore shortcuts when typing in input/textarea/contenteditable
 * - Event listener cleanup on unmount
 * - preventDefault for registered shortcuts
 *
 * Integration:
 * -----------
 * - Returns { showShortcutsOverlay: Ref<boolean> }
 * - Use in App.vue or HelpCenter.vue
 * - Render KeyboardShortcutsOverlay with v-model="showShortcutsOverlay"
 *
 * Author: Story 11.8c (Task 4)
 */

import { ref, onMounted, onUnmounted } from 'vue'

export function useKeyboardShortcuts() {
  const showShortcutsOverlay = ref(false)

  /**
   * Check if the current target is an input-like element
   * where we should ignore keyboard shortcuts
   */
  const isInputElement = (target: EventTarget | null): boolean => {
    if (!target || !(target instanceof HTMLElement)) {
      return false
    }

    const tagName = target.tagName.toUpperCase()
    const isContentEditable = target.isContentEditable

    return (
      tagName === 'INPUT' ||
      tagName === 'TEXTAREA' ||
      tagName === 'SELECT' ||
      isContentEditable
    )
  }

  /**
   * Focus the search input element
   * Looks for element with data-search-input attribute
   */
  const focusSearchInput = () => {
    const searchInput = document.querySelector<HTMLInputElement>(
      '[data-search-input]'
    )

    if (searchInput) {
      searchInput.focus()
      // Optionally select all text
      if (searchInput.value) {
        searchInput.select()
      }
    }
  }

  /**
   * Close overlays and dialogs
   * Triggers Esc key event that PrimeVue dialogs listen to
   */
  const closeOverlays = () => {
    // Set overlay state to false
    showShortcutsOverlay.value = false

    // Optionally blur any focused element
    if (document.activeElement instanceof HTMLElement) {
      document.activeElement.blur()
    }
  }

  /**
   * Handle command palette (placeholder for future feature)
   */
  const openCommandPalette = () => {
    console.log('Command palette: Not yet implemented (Story 11.8c)')
    // TODO: Implement command palette in future story
  }

  /**
   * Global keydown event handler
   */
  const handleKeyDown = (event: KeyboardEvent) => {
    // Ignore shortcuts when typing in input elements
    if (isInputElement(event.target)) {
      return
    }

    const key = event.key
    const ctrlOrCmd = event.ctrlKey || event.metaKey

    // "?" key → Show keyboard shortcuts overlay
    if (key === '?' && !event.shiftKey && !ctrlOrCmd) {
      event.preventDefault()
      showShortcutsOverlay.value = true
      return
    }

    // "/" key → Focus search input
    if (key === '/' && !event.shiftKey && !ctrlOrCmd) {
      event.preventDefault()
      focusSearchInput()
      return
    }

    // "Esc" key → Close overlays
    if (key === 'Escape') {
      event.preventDefault()
      closeOverlays()
      return
    }

    // "Ctrl+K" or "Cmd+K" → Command palette (future)
    if (key === 'k' && ctrlOrCmd && !event.shiftKey) {
      event.preventDefault()
      openCommandPalette()
      return
    }
  }

  // Lifecycle hooks
  onMounted(() => {
    window.addEventListener('keydown', handleKeyDown)
  })

  onUnmounted(() => {
    window.removeEventListener('keydown', handleKeyDown)
  })

  return {
    showShortcutsOverlay,
  }
}
