/**
 * Tooltip Composable (Story 11.8a - Task 16)
 *
 * Provides helpers for registering and managing tooltips throughout the application.
 * Integrates with PrimeVue Tooltip directive.
 */

import { onMounted, onUnmounted, type Directive } from 'vue'
import Tooltip from 'primevue/tooltip'
import { getTooltipConfig, getTooltipText } from '@/config/tooltips'

/**
 * Register a tooltip on an element by ID
 *
 * @param elementId - DOM element ID to attach tooltip to
 * @param content - Tooltip content key from tooltips.ts or custom content
 * @param options - Additional PrimeVue tooltip options
 *
 * @example
 * ```ts
 * // In component setup
 * onMounted(() => {
 *   registerTooltip('win-rate-metric', 'winRate')
 *   registerTooltip('custom-element', { value: 'Custom tooltip text', escape: true })
 * })
 * ```
 */
export function registerTooltip(
  elementId: string,
  content: string | { value: string; escape: boolean; class?: string },
  options?: Record<string, unknown>
) {
  const element = document.getElementById(elementId)

  if (!element) {
    console.warn(`Element not found for tooltip registration: ${elementId}`)
    return
  }

  // Get tooltip configuration
  const tooltipConfig =
    typeof content === 'string' ? getTooltipConfig(content) : content

  // Apply tooltip directive
  const tooltipDirective = Tooltip as Directive
  const binding = {
    value: tooltipConfig,
    modifiers: {
      ...options,
    },
  }

  if (tooltipDirective.mounted) {
    tooltipDirective.mounted(element, binding, {} as never, {} as never)
  }
}

/**
 * Unregister a tooltip from an element
 *
 * @param elementId - DOM element ID to remove tooltip from
 */
export function unregisterTooltip(elementId: string) {
  const element = document.getElementById(elementId)

  if (!element) {
    return
  }

  const tooltipDirective = Tooltip as Directive

  if (tooltipDirective.unmounted) {
    tooltipDirective.unmounted(element, {} as never, {} as never, {} as never)
  }
}

/**
 * Composable for managing tooltips with lifecycle hooks
 *
 * @param tooltips - Map of element IDs to tooltip content keys
 *
 * @example
 * ```ts
 * <script setup>
 * import { useTooltips } from '@/composables/useTooltip'
 *
 * useTooltips({
 *   'win-rate': 'winRate',
 *   'r-multiple': 'rMultiple',
 *   'portfolio-heat': 'portfolioHeat',
 * })
 * </script>
 *
 * <template>
 *   <div id="win-rate">95%</div>
 *   <div id="r-multiple">2.5R</div>
 *   <div id="portfolio-heat">4.2%</div>
 * </template>
 * ```
 */
export function useTooltips(tooltips: Record<string, string>) {
  onMounted(() => {
    // Small delay to ensure DOM is ready
    setTimeout(() => {
      Object.entries(tooltips).forEach(([elementId, contentKey]) => {
        registerTooltip(elementId, contentKey)
      })
    }, 100)
  })

  onUnmounted(() => {
    Object.keys(tooltips).forEach((elementId) => {
      unregisterTooltip(elementId)
    })
  })
}

/**
 * Get accessible tooltip text (plain text, no HTML)
 *
 * Useful for aria-label attributes
 *
 * @param key - Tooltip content key from tooltips.ts
 * @returns Plain text description
 */
export function useTooltipText(key: string): string {
  return getTooltipText(key)
}

/**
 * Configure PrimeVue Tooltip globally
 *
 * Call this in main.ts or App.vue setup
 *
 * @example
 * ```ts
 * import { configureTooltips } from '@/composables/useTooltip'
 * import { createApp } from 'vue'
 *
 * const app = createApp(App)
 * configureTooltips(app)
 * ```
 */
export function configureTooltips(app: {
  directive: (name: string, directive: unknown) => void
}) {
  // Register PrimeVue Tooltip directive globally
  app.directive('tooltip', Tooltip)

  // Configure default options (if PrimeVue supports global config)
  // Note: PrimeVue Tooltip options are typically set per-directive usage
  // This is a placeholder for any global configuration if needed
}

export default {
  registerTooltip,
  unregisterTooltip,
  useTooltips,
  useTooltipText,
  configureTooltips,
}
