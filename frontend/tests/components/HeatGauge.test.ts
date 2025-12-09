/**
 * Unit Tests for HeatGauge Component (Story 10.6)
 *
 * Purpose:
 * --------
 * Tests for HeatGauge.vue component including:
 * - Gauge rendering with different heat levels
 * - Color-coded risk levels (green/yellow/red)
 * - Capacity display
 * - Responsive sizing
 * - Smooth transitions
 *
 * Test Coverage:
 * --------------
 * - Renders with null values (loading state)
 * - Displays correct percentage
 * - Shows correct colors based on thresholds (60%/80%)
 * - Formats capacity text correctly
 * - Handles props changes reactively
 *
 * Author: Story 10.6
 */

import { describe, it, expect, afterEach } from 'vitest'
import { mount, VueWrapper } from '@vue/test-utils'
import Big from 'big.js'
import HeatGauge from '@/components/HeatGauge.vue'
import Knob from 'primevue/knob'

describe('HeatGauge.vue', () => {
  let wrapper: VueWrapper

  afterEach(() => {
    if (wrapper) {
      wrapper.unmount()
    }
  })

  describe('Component Rendering', () => {
    it('should render with null values (loading state)', () => {
      wrapper = mount(HeatGauge, {
        props: {
          totalHeat: null,
          totalHeatLimit: null,
        },
        global: {
          components: { Knob },
        },
      })

      expect(wrapper.exists()).toBe(true)
      expect(wrapper.find('.heat-gauge-container').exists()).toBe(true)
    })

    it('should render gauge with valid heat values', () => {
      wrapper = mount(HeatGauge, {
        props: {
          totalHeat: new Big('7.2'),
          totalHeatLimit: new Big('10.0'),
        },
        global: {
          components: { Knob },
        },
      })

      expect(wrapper.exists()).toBe(true)
      // Knob component should be rendered
      expect(wrapper.findComponent(Knob).exists()).toBe(true)
    })

    it('should display correct label', () => {
      const customLabel = 'Test Heat Gauge'
      wrapper = mount(HeatGauge, {
        props: {
          totalHeat: new Big('5.0'),
          totalHeatLimit: new Big('10.0'),
          label: customLabel,
        },
        global: {
          components: { Knob },
        },
      })

      expect(wrapper.text()).toContain(customLabel)
    })

    it('should show capacity when showCapacity is true', () => {
      wrapper = mount(HeatGauge, {
        props: {
          totalHeat: new Big('7.2'),
          totalHeatLimit: new Big('10.0'),
          showCapacity: true,
        },
        global: {
          components: { Knob },
        },
      })

      // Should show available capacity
      expect(wrapper.text()).toContain('available')
    })

    it('should hide capacity when showCapacity is false', () => {
      wrapper = mount(HeatGauge, {
        props: {
          totalHeat: new Big('7.2'),
          totalHeatLimit: new Big('10.0'),
          showCapacity: false,
        },
        global: {
          components: { Knob },
        },
      })

      // Should not show available capacity
      expect(wrapper.text()).not.toContain('available')
    })
  })

  describe('Heat Percentage Calculation', () => {
    it('should calculate correct percentage (72%)', async () => {
      wrapper = mount(HeatGauge, {
        props: {
          totalHeat: new Big('7.2'),
          totalHeatLimit: new Big('10.0'),
        },
        global: {
          components: { Knob },
        },
      })

      await wrapper.vm.$nextTick()

      const knob = wrapper.findComponent(Knob)
      // displayValue should be 72
      expect(knob.vm.modelValue).toBe(72)
    })

    it('should handle 0% heat', async () => {
      wrapper = mount(HeatGauge, {
        props: {
          totalHeat: new Big('0'),
          totalHeatLimit: new Big('10.0'),
        },
        global: {
          components: { Knob },
        },
      })

      await wrapper.vm.$nextTick()

      const knob = wrapper.findComponent(Knob)
      expect(knob.vm.modelValue).toBe(0)
    })

    it('should handle 100% heat', async () => {
      wrapper = mount(HeatGauge, {
        props: {
          totalHeat: new Big('10.0'),
          totalHeatLimit: new Big('10.0'),
        },
        global: {
          components: { Knob },
        },
      })

      await wrapper.vm.$nextTick()

      const knob = wrapper.findComponent(Knob)
      expect(knob.vm.modelValue).toBe(100)
    })

    it('should return 0% when data is null', async () => {
      wrapper = mount(HeatGauge, {
        props: {
          totalHeat: null,
          totalHeatLimit: null,
        },
        global: {
          components: { Knob },
        },
      })

      await wrapper.vm.$nextTick()

      const knob = wrapper.findComponent(Knob)
      expect(knob.vm.modelValue).toBe(0)
    })
  })

  describe('Color-Coded Risk Levels', () => {
    it('should use green color for safe zone (<60%)', async () => {
      wrapper = mount(HeatGauge, {
        props: {
          totalHeat: new Big('5.0'), // 50%
          totalHeatLimit: new Big('10.0'),
        },
        global: {
          components: { Knob },
        },
      })

      await wrapper.vm.$nextTick()

      const knob = wrapper.findComponent(Knob)
      expect(knob.vm.valueColor).toBe('#22c55e') // green-500
    })

    it('should use yellow color for caution zone (60-80%)', async () => {
      wrapper = mount(HeatGauge, {
        props: {
          totalHeat: new Big('7.0'), // 70%
          totalHeatLimit: new Big('10.0'),
        },
        global: {
          components: { Knob },
        },
      })

      await wrapper.vm.$nextTick()

      const knob = wrapper.findComponent(Knob)
      expect(knob.vm.valueColor).toBe('#eab308') // yellow-500
    })

    it('should use red color for warning zone (>=80%)', async () => {
      wrapper = mount(HeatGauge, {
        props: {
          totalHeat: new Big('8.5'), // 85%
          totalHeatLimit: new Big('10.0'),
        },
        global: {
          components: { Knob },
        },
      })

      await wrapper.vm.$nextTick()

      const knob = wrapper.findComponent(Knob)
      expect(knob.vm.valueColor).toBe('#ef4444') // red-500
    })

    it('should use red color exactly at 80% threshold', async () => {
      wrapper = mount(HeatGauge, {
        props: {
          totalHeat: new Big('8.0'), // exactly 80%
          totalHeatLimit: new Big('10.0'),
        },
        global: {
          components: { Knob },
        },
      })

      await wrapper.vm.$nextTick()

      const knob = wrapper.findComponent(Knob)
      expect(knob.vm.valueColor).toBe('#ef4444') // red-500
    })
  })

  describe('Capacity Formatting', () => {
    it('should format available capacity correctly', () => {
      wrapper = mount(HeatGauge, {
        props: {
          totalHeat: new Big('7.2'),
          totalHeatLimit: new Big('10.0'),
          showCapacity: true,
        },
        global: {
          components: { Knob },
        },
      })

      // Should show "2.8% available"
      expect(wrapper.text()).toContain('2.8% available')
    })

    it('should show "Loading..." when data is null', () => {
      wrapper = mount(HeatGauge, {
        props: {
          totalHeat: null,
          totalHeatLimit: null,
          showCapacity: true,
        },
        global: {
          components: { Knob },
        },
      })

      expect(wrapper.text()).toContain('Loading...')
    })
  })

  describe('Responsive Sizing', () => {
    it('should use default size (150px)', () => {
      wrapper = mount(HeatGauge, {
        props: {
          totalHeat: new Big('5.0'),
          totalHeatLimit: new Big('10.0'),
        },
        global: {
          components: { Knob },
        },
      })

      const knob = wrapper.findComponent(Knob)
      expect(knob.vm.size).toBe(150)
    })

    it('should use custom size', () => {
      wrapper = mount(HeatGauge, {
        props: {
          totalHeat: new Big('5.0'),
          totalHeatLimit: new Big('10.0'),
          size: 200,
        },
        global: {
          components: { Knob },
        },
      })

      const knob = wrapper.findComponent(Knob)
      expect(knob.vm.size).toBe(200)
    })

    it('should use custom stroke width', () => {
      wrapper = mount(HeatGauge, {
        props: {
          totalHeat: new Big('5.0'),
          totalHeatLimit: new Big('10.0'),
          strokeWidth: 20,
        },
        global: {
          components: { Knob },
        },
      })

      const knob = wrapper.findComponent(Knob)
      expect(knob.vm.strokeWidth).toBe(20)
    })
  })

  describe('Accessibility', () => {
    it('should have proper ARIA label', () => {
      wrapper = mount(HeatGauge, {
        props: {
          totalHeat: new Big('7.2'),
          totalHeatLimit: new Big('10.0'),
        },
        global: {
          components: { Knob },
        },
      })

      const container = wrapper.find('.heat-gauge-container')
      expect(container.attributes('role')).toBe('img')
      expect(container.attributes('aria-label')).toContain(
        'Portfolio heat gauge'
      )
      expect(container.attributes('aria-label')).toContain('72%')
    })
  })
})
