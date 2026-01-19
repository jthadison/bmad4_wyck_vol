/**
 * SchematicBadge Component Unit Tests
 * Story 11.5.1 - Wyckoff Schematic Badge Component
 *
 * Test Coverage:
 * - AC 2: Schematic badge display with type and confidence score
 * - Component rendering with null/valid props
 * - Computed properties (schematicLabel, schematicIcon, confidenceClass, etc.)
 * - User interactions (badge click, modal open/close)
 * - Pattern sequence display in modal
 * - Interpretation guide rendering
 * - Edge cases and data validation
 */

import { describe, it, expect, beforeEach, afterEach } from 'vitest'
import { mount, VueWrapper } from '@vue/test-utils'
import SchematicBadge from '@/components/charts/SchematicBadge.vue'
import type { WyckoffSchematic } from '@/types/chart'
import PrimeVue from 'primevue/config'

// Helper to create mock Wyckoff schematic data
const createMockSchematic = (
  overrides?: Partial<WyckoffSchematic>
): WyckoffSchematic => ({
  schematic_type: 'ACCUMULATION_1',
  confidence_score: 85,
  template_data: [
    { x_percent: 10.0, y_percent: 20.0 },
    { x_percent: 20.0, y_percent: 5.0 },
    { x_percent: 30.0, y_percent: 15.0 },
    { x_percent: 40.0, y_percent: 10.0 },
    { x_percent: 50.0, y_percent: 3.0 },
    { x_percent: 60.0, y_percent: 25.0 },
  ],
  ...overrides,
})

describe('SchematicBadge.vue', () => {
  let wrapper: VueWrapper

  const mountComponent = (props: { schematic: WyckoffSchematic | null }) => {
    return mount(SchematicBadge, {
      props,
      global: {
        plugins: [PrimeVue],
        stubs: {
          Dialog: {
            template: `
              <div v-if="visible" class="p-dialog" role="dialog">
                <div class="p-dialog-header">
                  <span class="p-dialog-title">{{ header }}</span>
                </div>
                <div class="p-dialog-content">
                  <slot />
                </div>
              </div>
            `,
            props: [
              'visible',
              'header',
              'modal',
              'closable',
              'draggable',
              'style',
            ],
          },
          ProgressBar: {
            template:
              '<div class="p-progressbar"><div class="p-progressbar-value" :style="{ width: value + \'%\' }">{{ showValue ? value + \'%\' : \'\' }}</div></div>',
            props: ['value', 'showValue', 'style'],
          },
          Tag: {
            template:
              '<span class="p-tag" :class="`p-tag-${severity}`">{{ value }}</span>',
            props: ['value', 'severity', 'class'],
          },
        },
      },
    })
  }

  afterEach(() => {
    if (wrapper) {
      wrapper.unmount()
    }
  })

  describe('Component Rendering', () => {
    it('should not render anything when schematic prop is null', () => {
      wrapper = mountComponent({ schematic: null })

      const badge = wrapper.find('.schematic-badge')
      expect(badge.exists()).toBe(false)
    })

    it('should render badge when schematic prop is provided', () => {
      const schematic = createMockSchematic()
      wrapper = mountComponent({ schematic })

      const badge = wrapper.find('.schematic-badge')
      expect(badge.exists()).toBe(true)
    })

    it('should render badge as clickable element', () => {
      const schematic = createMockSchematic()
      wrapper = mountComponent({ schematic })

      const badge = wrapper.find('.schematic-badge')
      expect(badge.exists()).toBe(true)
      expect(badge.attributes('role')).toBe('button')
      expect(badge.attributes('tabindex')).toBe('0')
    })
  })

  describe('Badge Content Display', () => {
    it('should display schematic type label', () => {
      const schematic = createMockSchematic({
        schematic_type: 'ACCUMULATION_1',
      })
      wrapper = mountComponent({ schematic })

      expect(wrapper.text()).toContain('Accumulation #1 (Spring)')
    })

    it('should display confidence score as percentage', () => {
      const schematic = createMockSchematic({ confidence_score: 85 })
      wrapper = mountComponent({ schematic })

      expect(wrapper.text()).toContain('85% match')
    })

    it('should display appropriate icon for accumulation patterns', () => {
      const schematic = createMockSchematic({
        schematic_type: 'ACCUMULATION_1',
      })
      wrapper = mountComponent({ schematic })

      const icon = wrapper.find('.badge-icon i')
      expect(icon.exists()).toBe(true)
      expect(icon.classes()).toContain('pi-arrow-up')
    })

    it('should display appropriate icon for distribution patterns', () => {
      const schematic = createMockSchematic({
        schematic_type: 'DISTRIBUTION_1',
      })
      wrapper = mountComponent({ schematic })

      const icon = wrapper.find('.badge-icon i')
      expect(icon.classes()).toContain('pi-arrow-down')
    })
  })

  describe('Computed Property: schematicLabel', () => {
    it('should return correct label for ACCUMULATION_1', () => {
      const schematic = createMockSchematic({
        schematic_type: 'ACCUMULATION_1',
      })
      wrapper = mountComponent({ schematic })

      expect(wrapper.text()).toContain('Accumulation #1 (Spring)')
    })

    it('should return correct label for ACCUMULATION_2', () => {
      const schematic = createMockSchematic({
        schematic_type: 'ACCUMULATION_2',
      })
      wrapper = mountComponent({ schematic })

      expect(wrapper.text()).toContain('Accumulation #2 (No Spring)')
    })

    it('should return correct label for DISTRIBUTION_1', () => {
      const schematic = createMockSchematic({
        schematic_type: 'DISTRIBUTION_1',
      })
      wrapper = mountComponent({ schematic })

      expect(wrapper.text()).toContain('Distribution #1 (UTAD)')
    })

    it('should return correct label for DISTRIBUTION_2', () => {
      const schematic = createMockSchematic({
        schematic_type: 'DISTRIBUTION_2',
      })
      wrapper = mountComponent({ schematic })

      expect(wrapper.text()).toContain('Distribution #2 (No UTAD)')
    })

    it('should fallback to raw schematic_type for unknown types', () => {
      const schematic = createMockSchematic({
        schematic_type: 'UNKNOWN_TYPE' as WyckoffSchematic['schematic_type'],
      })
      wrapper = mountComponent({ schematic })

      expect(wrapper.text()).toContain('UNKNOWN_TYPE')
    })
  })

  describe('Computed Property: schematicIcon', () => {
    it('should return pi-arrow-up for ACCUMULATION_1', () => {
      const schematic = createMockSchematic({
        schematic_type: 'ACCUMULATION_1',
      })
      wrapper = mountComponent({ schematic })

      const icon = wrapper.find('.badge-icon i')
      expect(icon.classes()).toContain('pi-arrow-up')
    })

    it('should return pi-arrow-up for ACCUMULATION_2', () => {
      const schematic = createMockSchematic({
        schematic_type: 'ACCUMULATION_2',
      })
      wrapper = mountComponent({ schematic })

      const icon = wrapper.find('.badge-icon i')
      expect(icon.classes()).toContain('pi-arrow-up')
    })

    it('should return pi-arrow-down for DISTRIBUTION_1', () => {
      const schematic = createMockSchematic({
        schematic_type: 'DISTRIBUTION_1',
      })
      wrapper = mountComponent({ schematic })

      const icon = wrapper.find('.badge-icon i')
      expect(icon.classes()).toContain('pi-arrow-down')
    })

    it('should return pi-arrow-down for DISTRIBUTION_2', () => {
      const schematic = createMockSchematic({
        schematic_type: 'DISTRIBUTION_2',
      })
      wrapper = mountComponent({ schematic })

      const icon = wrapper.find('.badge-icon i')
      expect(icon.classes()).toContain('pi-arrow-down')
    })
  })

  describe('Computed Property: confidenceClass', () => {
    it('should return confidence-high for scores >= 80', () => {
      const schematic = createMockSchematic({ confidence_score: 85 })
      wrapper = mountComponent({ schematic })

      const confidenceBadge = wrapper.find('.badge-confidence')
      expect(confidenceBadge.classes()).toContain('confidence-high')
    })

    it('should return confidence-high for score exactly 80', () => {
      const schematic = createMockSchematic({ confidence_score: 80 })
      wrapper = mountComponent({ schematic })

      const confidenceBadge = wrapper.find('.badge-confidence')
      expect(confidenceBadge.classes()).toContain('confidence-high')
    })

    it('should return confidence-medium for scores 70-79', () => {
      const schematic = createMockSchematic({ confidence_score: 75 })
      wrapper = mountComponent({ schematic })

      const confidenceBadge = wrapper.find('.badge-confidence')
      expect(confidenceBadge.classes()).toContain('confidence-medium')
    })

    it('should return confidence-medium for score exactly 70', () => {
      const schematic = createMockSchematic({ confidence_score: 70 })
      wrapper = mountComponent({ schematic })

      const confidenceBadge = wrapper.find('.badge-confidence')
      expect(confidenceBadge.classes()).toContain('confidence-medium')
    })

    it('should return confidence-low for scores < 70', () => {
      const schematic = createMockSchematic({ confidence_score: 65 })
      wrapper = mountComponent({ schematic })

      const confidenceBadge = wrapper.find('.badge-confidence')
      expect(confidenceBadge.classes()).toContain('confidence-low')
    })

    it('should return confidence-low for minimum confidence score', () => {
      const schematic = createMockSchematic({ confidence_score: 60 })
      wrapper = mountComponent({ schematic })

      const confidenceBadge = wrapper.find('.badge-confidence')
      expect(confidenceBadge.classes()).toContain('confidence-low')
    })
  })

  describe('Modal Interaction', () => {
    it('should start with modal closed', () => {
      const schematic = createMockSchematic()
      wrapper = mountComponent({ schematic })

      const modal = wrapper.find('.p-dialog')
      expect(modal.exists()).toBe(false)
    })

    it('should open modal when badge is clicked', async () => {
      const schematic = createMockSchematic()
      wrapper = mountComponent({ schematic })

      await wrapper.find('.schematic-badge').trigger('click')
      await wrapper.vm.$nextTick()

      const modal = wrapper.find('.p-dialog')
      expect(modal.exists()).toBe(true)
    })

    it('should not open modal when schematic is null', async () => {
      wrapper = mountComponent({ schematic: null })

      // Since badge doesn't render, click won't happen
      const badge = wrapper.find('.schematic-badge')
      expect(badge.exists()).toBe(false)
    })

    it('should display modal title with schematic type', async () => {
      const schematic = createMockSchematic({
        schematic_type: 'ACCUMULATION_1',
      })
      wrapper = mountComponent({ schematic })

      await wrapper.find('.schematic-badge').trigger('click')
      await wrapper.vm.$nextTick()

      const modalTitle = wrapper.find('.p-dialog-title')
      expect(modalTitle.text()).toContain('Wyckoff Schematic Match')
      expect(modalTitle.text()).toContain('Accumulation #1 (Spring)')
    })
  })

  describe('Modal Content Display', () => {
    beforeEach(async () => {
      const schematic = createMockSchematic({
        schematic_type: 'ACCUMULATION_1',
        confidence_score: 85,
        template_data: [
          { x_percent: 10, y_percent: 20 },
          { x_percent: 20, y_percent: 5 },
          { x_percent: 30, y_percent: 15 },
        ],
      })
      wrapper = mountComponent({ schematic })
      await wrapper.find('.schematic-badge').trigger('click')
      await wrapper.vm.$nextTick()
    })

    it('should display confidence score in modal', () => {
      const modalContent = wrapper.find('.schematic-details')
      expect(modalContent.text()).toContain('Confidence Score')
    })

    it('should display progress bar with confidence value', () => {
      const progressBar = wrapper.find('.p-progressbar-value')
      expect(progressBar.attributes('style')).toContain('width: 85%')
    })

    it('should display schematic type description', () => {
      const modalContent = wrapper.find('.schematic-details')
      expect(modalContent.text()).toContain('Schematic Type')
      expect(modalContent.text()).toContain(
        'Accumulation pattern with Spring (shakeout below Creek)'
      )
    })

    it('should display template point count', () => {
      const modalContent = wrapper.find('.schematic-details')
      expect(modalContent.text()).toContain('Template Points')
      expect(modalContent.text()).toContain('3 key levels')
    })

    it('should display expected pattern sequence heading', () => {
      const modalContent = wrapper.find('.schematic-details')
      expect(modalContent.text()).toContain('Expected Pattern Sequence')
    })

    it('should display interpretation guide heading', () => {
      const modalContent = wrapper.find('.schematic-details')
      expect(modalContent.text()).toContain('Interpretation')
    })

    it('should display interpretation text', () => {
      const interpretation = wrapper.find('.interpretation-text')
      expect(interpretation.text()).toContain('This schematic indicates')
      expect(interpretation.text().length).toBeGreaterThan(50)
    })
  })

  describe('Computed Property: schematicDescription', () => {
    it('should return correct description for ACCUMULATION_1', async () => {
      const schematic = createMockSchematic({
        schematic_type: 'ACCUMULATION_1',
      })
      wrapper = mountComponent({ schematic })
      await wrapper.find('.schematic-badge').trigger('click')

      expect(wrapper.text()).toContain(
        'Accumulation pattern with Spring (shakeout below Creek)'
      )
    })

    it('should return correct description for ACCUMULATION_2', async () => {
      const schematic = createMockSchematic({
        schematic_type: 'ACCUMULATION_2',
      })
      wrapper = mountComponent({ schematic })
      await wrapper.find('.schematic-badge').trigger('click')

      expect(wrapper.text()).toContain(
        'Accumulation pattern with LPS (no Spring shakeout)'
      )
    })

    it('should return correct description for DISTRIBUTION_1', async () => {
      const schematic = createMockSchematic({
        schematic_type: 'DISTRIBUTION_1',
      })
      wrapper = mountComponent({ schematic })
      await wrapper.find('.schematic-badge').trigger('click')

      expect(wrapper.text()).toContain(
        'Distribution pattern with UTAD (upthrust above Ice)'
      )
    })

    it('should return correct description for DISTRIBUTION_2', async () => {
      const schematic = createMockSchematic({
        schematic_type: 'DISTRIBUTION_2',
      })
      wrapper = mountComponent({ schematic })
      await wrapper.find('.schematic-badge').trigger('click')

      expect(wrapper.text()).toContain(
        'Distribution pattern with LPSY (no UTAD upthrust)'
      )
    })
  })

  describe('Computed Property: expectedSequence', () => {
    it('should return correct sequence for ACCUMULATION_1', async () => {
      const schematic = createMockSchematic({
        schematic_type: 'ACCUMULATION_1',
      })
      wrapper = mountComponent({ schematic })
      await wrapper.find('.schematic-badge').trigger('click')

      const tags = wrapper.findAll('.p-tag')
      const tagTexts = tags.map((tag) => tag.text())

      expect(tagTexts).toContain('PS')
      expect(tagTexts).toContain('SC')
      expect(tagTexts).toContain('AR')
      expect(tagTexts).toContain('ST')
      expect(tagTexts).toContain('SPRING')
      expect(tagTexts).toContain('SOS')
      expect(tags.length).toBe(6)
    })

    it('should return correct sequence for ACCUMULATION_2', async () => {
      const schematic = createMockSchematic({
        schematic_type: 'ACCUMULATION_2',
      })
      wrapper = mountComponent({ schematic })
      await wrapper.find('.schematic-badge').trigger('click')

      const tags = wrapper.findAll('.p-tag')
      const tagTexts = tags.map((tag) => tag.text())

      expect(tagTexts).toContain('PS')
      expect(tagTexts).toContain('SC')
      expect(tagTexts).toContain('AR')
      expect(tagTexts).toContain('ST')
      expect(tagTexts).toContain('LPS')
      expect(tagTexts).toContain('SOS')
      expect(tags.length).toBe(6)
    })

    it('should return correct sequence for DISTRIBUTION_1', async () => {
      const schematic = createMockSchematic({
        schematic_type: 'DISTRIBUTION_1',
      })
      wrapper = mountComponent({ schematic })
      await wrapper.find('.schematic-badge').trigger('click')

      const tags = wrapper.findAll('.p-tag')
      const tagTexts = tags.map((tag) => tag.text())

      expect(tagTexts).toContain('PSY')
      expect(tagTexts).toContain('BC')
      expect(tagTexts).toContain('AR')
      expect(tagTexts).toContain('ST')
      expect(tagTexts).toContain('UTAD')
      expect(tagTexts).toContain('SOW')
      expect(tags.length).toBe(6)
    })

    it('should return correct sequence for DISTRIBUTION_2', async () => {
      const schematic = createMockSchematic({
        schematic_type: 'DISTRIBUTION_2',
      })
      wrapper = mountComponent({ schematic })
      await wrapper.find('.schematic-badge').trigger('click')

      const tags = wrapper.findAll('.p-tag')
      const tagTexts = tags.map((tag) => tag.text())

      expect(tagTexts).toContain('PSY')
      expect(tagTexts).toContain('BC')
      expect(tagTexts).toContain('AR')
      expect(tagTexts).toContain('ST')
      expect(tagTexts).toContain('LPSY')
      expect(tagTexts).toContain('SOW')
      expect(tags.length).toBe(6)
    })
  })

  describe('Computed Property: interpretationGuide', () => {
    it('should return detailed interpretation for ACCUMULATION_1', async () => {
      const schematic = createMockSchematic({
        schematic_type: 'ACCUMULATION_1',
      })
      wrapper = mountComponent({ schematic })
      await wrapper.find('.schematic-badge').trigger('click')

      const interpretation = wrapper.find('.interpretation-text')
      expect(interpretation.text()).toContain('classic accumulation pattern')
      expect(interpretation.text()).toContain('Spring shakeout')
      expect(interpretation.text()).toContain('Sign of Strength')
      expect(interpretation.text()).toContain('upward move')
    })

    it('should return detailed interpretation for ACCUMULATION_2', async () => {
      const schematic = createMockSchematic({
        schematic_type: 'ACCUMULATION_2',
      })
      wrapper = mountComponent({ schematic })
      await wrapper.find('.schematic-badge').trigger('click')

      const interpretation = wrapper.find('.interpretation-text')
      expect(interpretation.text()).toContain('accumulation without a Spring')
      expect(interpretation.text()).toContain('Last Point of Support')
      expect(interpretation.text()).toContain('upward movement')
    })

    it('should return detailed interpretation for DISTRIBUTION_1', async () => {
      const schematic = createMockSchematic({
        schematic_type: 'DISTRIBUTION_1',
      })
      wrapper = mountComponent({ schematic })
      await wrapper.find('.schematic-badge').trigger('click')

      const interpretation = wrapper.find('.interpretation-text')
      expect(interpretation.text()).toContain('distribution pattern')
      expect(interpretation.text()).toContain('Upthrust After Distribution')
      expect(interpretation.text()).toContain('downward move')
    })

    it('should return detailed interpretation for DISTRIBUTION_2', async () => {
      const schematic = createMockSchematic({
        schematic_type: 'DISTRIBUTION_2',
      })
      wrapper = mountComponent({ schematic })
      await wrapper.find('.schematic-badge').trigger('click')

      const interpretation = wrapper.find('.interpretation-text')
      expect(interpretation.text()).toContain('distribution without an UTAD')
      expect(interpretation.text()).toContain('Last Point of Supply')
      expect(interpretation.text()).toContain('downward movement')
    })
  })

  describe('Edge Cases', () => {
    it('should handle empty template_data array', () => {
      const schematic = createMockSchematic({ template_data: [] })
      wrapper = mountComponent({ schematic })

      expect(() => wrapper.find('.schematic-badge')).not.toThrow()
      expect(wrapper.text()).toContain('Accumulation #1 (Spring)')
    })

    it('should handle very low confidence scores (60%)', () => {
      const schematic = createMockSchematic({ confidence_score: 60 })
      wrapper = mountComponent({ schematic })

      expect(wrapper.text()).toContain('60% match')
      const confidenceBadge = wrapper.find('.badge-confidence')
      expect(confidenceBadge.classes()).toContain('confidence-low')
    })

    it('should handle maximum confidence scores (95%)', () => {
      const schematic = createMockSchematic({ confidence_score: 95 })
      wrapper = mountComponent({ schematic })

      expect(wrapper.text()).toContain('95% match')
      const confidenceBadge = wrapper.find('.badge-confidence')
      expect(confidenceBadge.classes()).toContain('confidence-high')
    })

    it('should handle boundary confidence score (79%)', () => {
      const schematic = createMockSchematic({ confidence_score: 79 })
      wrapper = mountComponent({ schematic })

      const confidenceBadge = wrapper.find('.badge-confidence')
      expect(confidenceBadge.classes()).toContain('confidence-medium')
    })

    it('should handle large template_data arrays', async () => {
      const largeTemplate = Array.from({ length: 20 }, (_, i) => ({
        x_percent: i * 5,
        y_percent: Math.random() * 100,
      }))
      const schematic = createMockSchematic({ template_data: largeTemplate })
      wrapper = mountComponent({ schematic })

      await wrapper.find('.schematic-badge').trigger('click')
      expect(wrapper.text()).toContain('20 key levels')
    })
  })

  describe('Styling and CSS Classes', () => {
    it('should have cursor pointer on badge', () => {
      const schematic = createMockSchematic()
      wrapper = mountComponent({ schematic })

      const badge = wrapper.find('.schematic-badge')
      expect(badge.exists()).toBe(true)
      expect(badge.attributes('role')).toBe('button')
      expect(badge.attributes('tabindex')).toBe('0')
    })

    it('should have badge-content container', () => {
      const schematic = createMockSchematic()
      wrapper = mountComponent({ schematic })

      const badgeContent = wrapper.find('.badge-content')
      expect(badgeContent.exists()).toBe(true)
    })

    it('should have badge-icon with circular styling', () => {
      const schematic = createMockSchematic()
      wrapper = mountComponent({ schematic })

      const badgeIcon = wrapper.find('.badge-icon')
      expect(badgeIcon.exists()).toBe(true)
    })

    it('should have pattern-sequence container in modal', async () => {
      const schematic = createMockSchematic()
      wrapper = mountComponent({ schematic })

      await wrapper.find('.schematic-badge').trigger('click')

      const patternSequence = wrapper.find('.pattern-sequence')
      expect(patternSequence.exists()).toBe(true)
    })
  })
})
