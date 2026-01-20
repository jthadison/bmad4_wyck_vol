/**
 * Tests for PortfolioRiskPanel Component (Story 16.3b)
 *
 * Test Coverage:
 * - Component rendering
 * - Loading state display
 * - Error state display
 * - Heat gauge display
 * - Risk level calculation and color coding
 * - Warning badge display (heat > 80%)
 * - Proximity warnings display
 * - Summary cards rendering
 * - Detail dialog functionality
 * - Refresh functionality
 *
 * Author: Story 16.3b
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createTestingPinia } from '@pinia/testing'
import { setActivePinia } from 'pinia'
import PortfolioRiskPanel from '@/components/campaigns/PortfolioRiskPanel.vue'
import { usePortfolioStore } from '@/stores/portfolioStore'
import Big from 'big.js'

// Mock websocketService
vi.mock('@/services/websocketService', () => ({
  websocketService: {
    connectionStatus: { value: 'connected' },
    lastMessageTime: { value: null },
    reconnectAttemptsCount: { value: 0 },
    isConnected: () => true,
    subscribe: vi.fn(),
    unsubscribe: vi.fn(),
    connect: vi.fn(),
    disconnect: vi.fn(),
    reconnectNow: vi.fn(),
    getLastSequenceNumber: () => 0,
    getConnectionId: () => 'test-conn-id',
  },
}))

// Mock PrimeVue components
vi.mock('primevue/progressbar', () => ({
  default: {
    name: 'ProgressBar',
    template:
      '<div class="progress-bar" data-testid="progress-bar" :data-value="value"><slot /></div>',
    props: ['value', 'showValue', 'style', 'pt'],
  },
}))

vi.mock('primevue/badge', () => ({
  default: {
    name: 'Badge',
    template:
      '<span class="badge" data-testid="warning-badge">{{ value }}</span>',
    props: ['value', 'severity'],
  },
}))

vi.mock('primevue/dialog', () => ({
  default: {
    name: 'Dialog',
    template:
      '<div v-if="visible" class="dialog" data-testid="detail-dialog"><slot /></div>',
    props: ['visible', 'header', 'modal', 'draggable', 'style'],
  },
}))

vi.mock('primevue/progressspinner', () => ({
  default: {
    name: 'ProgressSpinner',
    template: '<div class="progress-spinner" data-testid="spinner"></div>',
  },
}))

vi.mock('primevue/message', () => ({
  default: {
    name: 'Message',
    template: '<div class="message" data-testid="error-message"><slot /></div>',
    props: ['severity', 'closable'],
  },
}))

describe('PortfolioRiskPanel', () => {
  let pinia: ReturnType<typeof createTestingPinia>

  beforeEach(() => {
    pinia = createTestingPinia({
      createSpy: vi.fn,
      stubActions: true,
    })
    setActivePinia(pinia)
  })

  afterEach(() => {
    vi.clearAllMocks()
  })

  function mountComponent(options = {}) {
    return mount(PortfolioRiskPanel, {
      global: {
        plugins: [pinia],
        stubs: {
          Dialog: {
            name: 'Dialog',
            template:
              '<div v-if="visible" class="dialog" data-testid="detail-dialog"><slot /></div>',
            props: ['visible', 'header', 'modal', 'draggable', 'style'],
          },
        },
      },
      ...options,
    })
  }

  describe('component rendering', () => {
    it('should render component with title', () => {
      const wrapper = mountComponent()
      expect(wrapper.exists()).toBe(true)
      expect(wrapper.find('h2').text()).toBe('Portfolio Risk')
    })

    it('should render refresh button', () => {
      const wrapper = mountComponent()
      const refreshBtn = wrapper.find('.refresh-btn')
      expect(refreshBtn.exists()).toBe(true)
    })
  })

  describe('loading state', () => {
    it('should display loading spinner when loading and no data', async () => {
      const wrapper = mountComponent()
      const store = usePortfolioStore()

      store.$patch({
        loading: true,
        totalHeat: null,
      })

      await flushPromises()

      const spinner = wrapper.find('[data-testid="spinner"]')
      expect(spinner.exists()).toBe(true)
      expect(wrapper.text()).toContain('Loading risk data')
    })

    it('should not show spinner when data exists', async () => {
      const wrapper = mountComponent()
      const store = usePortfolioStore()

      store.$patch({
        loading: true,
        totalHeat: new Big(5),
        totalHeatLimit: new Big(10),
      })

      await flushPromises()

      const spinner = wrapper.find('[data-testid="spinner"]')
      expect(spinner.exists()).toBe(false)
    })
  })

  describe('error state', () => {
    it('should display error message when error occurs', async () => {
      const wrapper = mountComponent()
      const store = usePortfolioStore()

      store.$patch({
        loading: false,
        error: 'Failed to fetch risk dashboard',
        totalHeat: null,
      })

      await flushPromises()

      const errorMessage = wrapper.find('[data-testid="error-message"]')
      expect(errorMessage.exists()).toBe(true)
      expect(wrapper.text()).toContain('Failed to fetch risk dashboard')
    })
  })

  describe('heat gauge display', () => {
    it('should display heat percentage', async () => {
      const wrapper = mountComponent()
      const store = usePortfolioStore()

      store.$patch({
        loading: false,
        totalHeat: new Big(5),
        totalHeatLimit: new Big(10),
      })

      await flushPromises()

      expect(wrapper.text()).toContain('50.0%')
    })

    it('should display heat values in details', async () => {
      const wrapper = mountComponent()
      const store = usePortfolioStore()

      store.$patch({
        loading: false,
        totalHeat: new Big(5),
        totalHeatLimit: new Big(10),
      })

      await flushPromises()

      expect(wrapper.text()).toContain('5.00%')
      expect(wrapper.text()).toContain('10.00%')
      expect(wrapper.text()).toContain('limit')
    })
  })

  describe('risk level calculation', () => {
    it('should show LOW risk level for heat < 60%', async () => {
      const wrapper = mountComponent()
      const store = usePortfolioStore()

      store.$patch({
        loading: false,
        totalHeat: new Big(4),
        totalHeatLimit: new Big(10),
      })

      await flushPromises()

      expect(wrapper.text()).toContain('LOW')
      expect(wrapper.find('.risk-level-badge').classes()).toContain('risk-low')
    })

    it('should show MEDIUM risk level for heat 60-79%', async () => {
      const wrapper = mountComponent()
      const store = usePortfolioStore()

      store.$patch({
        loading: false,
        totalHeat: new Big(7),
        totalHeatLimit: new Big(10),
      })

      await flushPromises()

      expect(wrapper.text()).toContain('MEDIUM')
      expect(wrapper.find('.risk-level-badge').classes()).toContain(
        'risk-medium'
      )
    })

    it('should show HIGH risk level for heat 80-89%', async () => {
      const wrapper = mountComponent()
      const store = usePortfolioStore()

      store.$patch({
        loading: false,
        totalHeat: new Big(8.5),
        totalHeatLimit: new Big(10),
      })

      await flushPromises()

      expect(wrapper.text()).toContain('HIGH')
      expect(wrapper.find('.risk-level-badge').classes()).toContain('risk-high')
    })

    it('should show CRITICAL risk level for heat >= 90%', async () => {
      const wrapper = mountComponent()
      const store = usePortfolioStore()

      store.$patch({
        loading: false,
        totalHeat: new Big(9.5),
        totalHeatLimit: new Big(10),
      })

      await flushPromises()

      expect(wrapper.text()).toContain('CRITICAL')
      expect(wrapper.find('.risk-level-badge').classes()).toContain(
        'risk-critical'
      )
    })
  })

  describe('warning badge', () => {
    it('should show warning badge when heat > 80%', async () => {
      const wrapper = mountComponent()
      const store = usePortfolioStore()

      store.$patch({
        loading: false,
        totalHeat: new Big(8.5),
        totalHeatLimit: new Big(10),
      })

      await flushPromises()

      const warningBadge = wrapper.find('[data-testid="warning-badge"]')
      expect(warningBadge.exists()).toBe(true)
    })

    it('should show warning badge when proximity warnings exist', async () => {
      const wrapper = mountComponent()
      const store = usePortfolioStore()

      store.$patch({
        loading: false,
        totalHeat: new Big(5),
        totalHeatLimit: new Big(10),
        proximityWarnings: ['Approaching sector limit'],
      })

      await flushPromises()

      const warningBadge = wrapper.find('[data-testid="warning-badge"]')
      expect(warningBadge.exists()).toBe(true)
    })

    it('should not show warning badge when heat < 80% and no warnings', async () => {
      const wrapper = mountComponent()
      const store = usePortfolioStore()

      store.$patch({
        loading: false,
        totalHeat: new Big(5),
        totalHeatLimit: new Big(10),
        proximityWarnings: [],
      })

      await flushPromises()

      const warningBadge = wrapper.find('[data-testid="warning-badge"]')
      expect(warningBadge.exists()).toBe(false)
    })
  })

  describe('proximity warnings', () => {
    it('should display proximity warnings when present', async () => {
      const wrapper = mountComponent()
      const store = usePortfolioStore()

      store.$patch({
        loading: false,
        totalHeat: new Big(5),
        totalHeatLimit: new Big(10),
        proximityWarnings: ['Warning 1', 'Warning 2'],
      })

      await flushPromises()

      const warningsSection = wrapper.find('.warnings-section')
      expect(warningsSection.exists()).toBe(true)
      expect(wrapper.text()).toContain('Warning 1')
      expect(wrapper.text()).toContain('Warning 2')
    })

    it('should not show warnings section when no warnings', async () => {
      const wrapper = mountComponent()
      const store = usePortfolioStore()

      store.$patch({
        loading: false,
        totalHeat: new Big(5),
        totalHeatLimit: new Big(10),
        proximityWarnings: [],
      })

      await flushPromises()

      const warningsSection = wrapper.find('.warnings-section')
      expect(warningsSection.exists()).toBe(false)
    })
  })

  describe('summary cards', () => {
    it('should display campaign risk count', async () => {
      const wrapper = mountComponent()
      const store = usePortfolioStore()

      store.$patch({
        loading: false,
        totalHeat: new Big(5),
        totalHeatLimit: new Big(10),
        campaignRisks: [
          { campaign_id: 'CAMP-1', risk_allocated: '2.0', positions_count: 3 },
          { campaign_id: 'CAMP-2', risk_allocated: '1.5', positions_count: 2 },
        ],
      })

      await flushPromises()

      expect(wrapper.text()).toContain('2')
      expect(wrapper.text()).toContain('active campaigns')
    })

    it('should display correlation groups count', async () => {
      const wrapper = mountComponent()
      const store = usePortfolioStore()

      store.$patch({
        loading: false,
        totalHeat: new Big(5),
        totalHeatLimit: new Big(10),
        correlatedRisks: [
          {
            sector: 'Tech',
            risk_allocated: new Big(3),
            sector_limit: new Big(6),
          },
        ],
      })

      await flushPromises()

      expect(wrapper.text()).toContain('1')
      expect(wrapper.text()).toContain('sector groups')
    })
  })

  describe('detail dialog', () => {
    it('should open campaigns detail dialog on card click', async () => {
      const wrapper = mountComponent()
      const store = usePortfolioStore()

      store.$patch({
        loading: false,
        totalHeat: new Big(5),
        totalHeatLimit: new Big(10),
        campaignRisks: [
          { campaign_id: 'CAMP-1', risk_allocated: '2.0', positions_count: 3 },
        ],
      })

      await flushPromises()

      // Find and click the campaigns card
      const summaryCards = wrapper.findAll('.summary-card')
      await summaryCards[0].trigger('click')

      // Check that dialog state is updated
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      expect((wrapper.vm as any).showDetailDialog).toBe(true)
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      expect((wrapper.vm as any).detailView).toBe('campaigns')
    })

    it('should open correlations detail dialog on card click', async () => {
      const wrapper = mountComponent()
      const store = usePortfolioStore()

      store.$patch({
        loading: false,
        totalHeat: new Big(5),
        totalHeatLimit: new Big(10),
        correlatedRisks: [
          {
            sector: 'Tech',
            risk_allocated: new Big(3),
            sector_limit: new Big(6),
          },
        ],
      })

      await flushPromises()

      // Find and click the correlations card
      const summaryCards = wrapper.findAll('.summary-card')
      await summaryCards[1].trigger('click')

      // Check that dialog state is updated
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      expect((wrapper.vm as any).showDetailDialog).toBe(true)
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      expect((wrapper.vm as any).detailView).toBe('correlations')
    })
  })

  describe('refresh functionality', () => {
    it('should call fetchRiskDashboard on refresh button click', async () => {
      const wrapper = mountComponent()
      const store = usePortfolioStore()

      store.$patch({
        loading: false,
        totalHeat: new Big(5),
        totalHeatLimit: new Big(10),
      })

      await flushPromises()

      const refreshBtn = wrapper.find('.refresh-btn')
      await refreshBtn.trigger('click')

      expect(store.fetchRiskDashboard).toHaveBeenCalled()
    })

    it('should disable refresh button while loading', async () => {
      const wrapper = mountComponent()
      const store = usePortfolioStore()

      store.$patch({
        loading: true,
        totalHeat: new Big(5),
        totalHeatLimit: new Big(10),
      })

      await flushPromises()

      const refreshBtn = wrapper.find('.refresh-btn')
      expect(refreshBtn.attributes('disabled')).toBeDefined()
    })
  })

  describe('last updated display', () => {
    it('should display last updated time when available', async () => {
      const wrapper = mountComponent()
      const store = usePortfolioStore()

      store.$patch({
        loading: false,
        totalHeat: new Big(5),
        totalHeatLimit: new Big(10),
        lastUpdated: '2023-06-15T10:30:00Z',
      })

      await flushPromises()

      expect(wrapper.text()).toContain('Updated:')
    })
  })

  describe('panel header', () => {
    it('should have panel header with title and refresh button', () => {
      const wrapper = mountComponent()

      const header = wrapper.find('.panel-header')
      expect(header.exists()).toBe(true)

      const title = header.find('h2')
      expect(title.text()).toBe('Portfolio Risk')

      const refreshBtn = header.find('.refresh-btn')
      expect(refreshBtn.exists()).toBe(true)
    })
  })

  describe('initial data fetch', () => {
    it('should call fetchRiskDashboard on mount if data not loaded', async () => {
      const store = usePortfolioStore()
      store.$patch({
        totalHeat: null,
        totalHeatLimit: null,
      })

      mountComponent()

      await flushPromises()

      expect(store.fetchRiskDashboard).toHaveBeenCalled()
    })
  })
})
