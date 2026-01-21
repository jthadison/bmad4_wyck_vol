/**
 * Unit Tests for RiskDashboard Component (Story 10.6)
 *
 * Purpose:
 * --------
 * Integration tests for RiskDashboard.vue main component including:
 * - Complete dashboard rendering with all sub-components
 * - Store integration (portfolioStore)
 * - Loading and error states
 * - Refresh functionality
 * - WebSocket connection status
 * - Real-time updates simulation
 *
 * Test Coverage:
 * --------------
 * - Renders all sub-components (HeatGauge, CampaignRiskList, etc.)
 * - Fetches data from store on mount
 * - Displays loading state correctly
 * - Displays error state with retry button
 * - Manual refresh triggers store fetch
 * - WebSocket connection status indicator
 * - Proximity warnings banner appears when warnings exist
 *
 * Author: Story 10.6
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { mount, VueWrapper } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import Big from 'big.js'
import RiskDashboard from '@/components/RiskDashboard.vue'
import { usePortfolioStore } from '@/stores/portfolioStore'
import type { RiskDashboardData } from '@/types'

// Mock composables
vi.mock('@/composables/useWebSocket', () => ({
  useWebSocket: () => ({
    isConnected: { value: true },
    subscribe: vi.fn(),
  }),
}))

describe('RiskDashboard.vue', () => {
  let wrapper: VueWrapper
  let pinia: ReturnType<typeof createPinia>

  // Mock risk dashboard data
  const mockDashboardData: RiskDashboardData = {
    total_heat: new Big('7.2'),
    total_heat_limit: new Big('10.0'),
    available_capacity: new Big('2.8'),
    estimated_signals_capacity: 3,
    per_trade_risk_range: '0.5-1.0% per signal',
    campaign_risks: [
      {
        campaign_id: 'C-12345678',
        risk_allocated: new Big('4.1'),
        positions_count: 2,
        campaign_limit: new Big('5.0'),
        phase_distribution: { C: 1, D: 1 },
      },
    ],
    correlated_risks: [
      {
        sector: 'Technology',
        risk_allocated: new Big('4.1'),
        sector_limit: new Big('6.0'),
      },
    ],
    proximity_warnings: ['Portfolio heat at 72% capacity'],
    heat_history_7d: [
      {
        timestamp: '2024-03-10T00:00:00Z',
        heat_percentage: new Big('5.0'),
      },
      {
        timestamp: '2024-03-11T00:00:00Z',
        heat_percentage: new Big('6.0'),
      },
      {
        timestamp: '2024-03-12T00:00:00Z',
        heat_percentage: new Big('7.2'),
      },
    ],
    last_updated: '2024-03-15T14:30:00Z',
  }

  beforeEach(() => {
    // Create fresh Pinia instance for each test
    pinia = createPinia()
    setActivePinia(pinia)

    // Clear all mocks
    vi.clearAllMocks()
  })

  afterEach(() => {
    if (wrapper) {
      wrapper.unmount()
    }
  })

  describe('Component Rendering', () => {
    it('should render dashboard container', () => {
      wrapper = mount(RiskDashboard, {
        global: {
          plugins: [pinia],
          stubs: {
            HeatGauge: true,
            HeatSparkline: true,
            CampaignRiskList: true,
            ProximityWarningsBanner: true,
          },
        },
      })

      expect(wrapper.exists()).toBe(true)
      expect(wrapper.find('.risk-dashboard').exists()).toBe(true)
      expect(wrapper.text()).toContain('Risk Dashboard')
    })

    it('should have proper ARIA labels', () => {
      wrapper = mount(RiskDashboard, {
        global: {
          plugins: [pinia],
          stubs: {
            HeatGauge: true,
            HeatSparkline: true,
            CampaignRiskList: true,
            ProximityWarningsBanner: true,
          },
        },
      })

      const container = wrapper.find('.risk-dashboard')
      expect(container.attributes('role')).toBe('region')
      expect(container.attributes('aria-label')).toContain('Risk Dashboard')
    })
  })

  describe('Loading State', () => {
    it('should show loading spinner when loading and no data', async () => {
      const store = usePortfolioStore()
      store.loading = true
      store.totalHeat = null
      store.totalHeatLimit = null

      wrapper = mount(RiskDashboard, {
        global: {
          plugins: [pinia],
          stubs: {
            HeatGauge: true,
            HeatSparkline: true,
            CampaignRiskList: true,
            ProximityWarningsBanner: true,
          },
        },
      })

      await wrapper.vm.$nextTick()

      expect(wrapper.find('.pi-spinner').exists()).toBe(true)
      expect(wrapper.text()).toContain('Loading risk dashboard')
    })

    it('should not show loading spinner when data is already loaded', async () => {
      const store = usePortfolioStore()
      store.loading = true
      store.totalHeat = new Big('7.2')
      store.totalHeatLimit = new Big('10.0')

      wrapper = mount(RiskDashboard, {
        global: {
          plugins: [pinia],
          stubs: {
            HeatGauge: true,
            HeatSparkline: true,
            CampaignRiskList: true,
            ProximityWarningsBanner: true,
          },
        },
      })

      await wrapper.vm.$nextTick()

      // Should not show full loading state since data exists
      expect(wrapper.text()).not.toContain('Loading risk dashboard')
    })
  })

  describe('Error State', () => {
    it('should show error message when fetch fails', async () => {
      const store = usePortfolioStore()
      // Mock fetchRiskDashboard to reject and set error state
      vi.spyOn(store, 'fetchRiskDashboard').mockImplementation(async () => {
        store.error = 'Failed to fetch risk dashboard'
        store.loading = false
        throw new Error('API Error')
      })

      wrapper = mount(RiskDashboard, {
        global: {
          plugins: [pinia],
          stubs: {
            HeatGauge: true,
            HeatSparkline: true,
            CampaignRiskList: true,
            ProximityWarningsBanner: true,
          },
        },
      })

      // Wait for async operations to complete
      await wrapper.vm.$nextTick()
      await new Promise((resolve) => setTimeout(resolve, 50))

      expect(wrapper.find('.pi-exclamation-triangle').exists()).toBe(true)
      expect(wrapper.text()).toContain('Failed to load risk dashboard')
      expect(wrapper.text()).toContain('Failed to fetch risk dashboard')
    })

    it('should show retry button in error state', async () => {
      const store = usePortfolioStore()
      // Mock fetchRiskDashboard to reject and set error state
      vi.spyOn(store, 'fetchRiskDashboard').mockImplementation(async () => {
        store.error = 'Connection error'
        store.loading = false
        throw new Error('Connection Error')
      })

      wrapper = mount(RiskDashboard, {
        global: {
          plugins: [pinia],
          stubs: {
            HeatGauge: true,
            HeatSparkline: true,
            CampaignRiskList: true,
            ProximityWarningsBanner: true,
          },
        },
      })

      // Wait for async operations to complete
      await wrapper.vm.$nextTick()
      await new Promise((resolve) => setTimeout(resolve, 50))

      // The button contains an icon and text "Try Again"
      const buttons = wrapper.findAll('button')
      const retryButton = buttons.find((b) => b.text().includes('Try Again'))
      expect(retryButton).toBeDefined()
      expect(retryButton!.text()).toContain('Try Again')
    })

    it('should call store fetch when retry button clicked', async () => {
      const store = usePortfolioStore()
      store.error = 'Connection error'
      store.totalHeat = null

      const fetchSpy = vi.spyOn(store, 'fetchRiskDashboard').mockResolvedValue()

      wrapper = mount(RiskDashboard, {
        global: {
          plugins: [pinia],
          stubs: {
            HeatGauge: true,
            HeatSparkline: true,
            CampaignRiskList: true,
            ProximityWarningsBanner: true,
          },
        },
      })

      await wrapper.vm.$nextTick()

      const retryButton = wrapper.find('button:has(.pi-refresh)')
      await retryButton.trigger('click')

      expect(fetchSpy).toHaveBeenCalled()
    })
  })

  describe('Data Display', () => {
    it('should display all dashboard sections when data loaded', async () => {
      const store = usePortfolioStore()
      store.totalHeat = mockDashboardData.total_heat
      store.totalHeatLimit = mockDashboardData.total_heat_limit
      store.availableCapacity = mockDashboardData.available_capacity
      store.estimatedSignalsCapacity =
        mockDashboardData.estimated_signals_capacity
      store.campaignRisks = mockDashboardData.campaign_risks
      store.correlatedRisks = mockDashboardData.correlated_risks
      store.proximityWarnings = mockDashboardData.proximity_warnings
      store.heatHistory7d = mockDashboardData.heat_history_7d

      wrapper = mount(RiskDashboard, {
        global: {
          plugins: [pinia],
          stubs: {
            HeatGauge: true,
            HeatSparkline: true,
            CampaignRiskList: true,
            ProximityWarningsBanner: true,
          },
        },
      })

      await wrapper.vm.$nextTick()

      // Should show available capacity
      expect(wrapper.text()).toContain('Available Capacity')
      expect(wrapper.text()).toContain('2.8%')
      expect(wrapper.text()).toContain('3') // estimated signals

      // Should show sector correlation
      expect(wrapper.text()).toContain('Sector Correlation Risk')
    })

    it('should display estimated signals capacity', async () => {
      const store = usePortfolioStore()
      store.totalHeat = new Big('7.2')
      store.totalHeatLimit = new Big('10.0')
      store.estimatedSignalsCapacity = 3
      store.perTradeRiskRange = '0.5-1.0% per signal'

      wrapper = mount(RiskDashboard, {
        global: {
          plugins: [pinia],
          stubs: {
            HeatGauge: true,
            HeatSparkline: true,
            CampaignRiskList: true,
            ProximityWarningsBanner: true,
          },
        },
      })

      await wrapper.vm.$nextTick()

      expect(wrapper.text()).toContain('3')
      expect(wrapper.text()).toContain('0.5-1.0% per signal')
    })

    it('should display campaign and position counts', async () => {
      const store = usePortfolioStore()
      store.totalHeat = new Big('7.2')
      store.totalHeatLimit = new Big('10.0')
      store.campaignRisks = mockDashboardData.campaign_risks

      wrapper = mount(RiskDashboard, {
        global: {
          plugins: [pinia],
          stubs: {
            HeatGauge: true,
            HeatSparkline: true,
            CampaignRiskList: true,
            ProximityWarningsBanner: true,
          },
        },
      })

      await wrapper.vm.$nextTick()

      expect(wrapper.text()).toContain('Active Campaigns')
      expect(wrapper.text()).toContain('Total Positions')
    })
  })

  describe('Refresh Functionality', () => {
    it('should call store fetch when refresh button clicked', async () => {
      const store = usePortfolioStore()
      store.totalHeat = new Big('7.2')
      store.totalHeatLimit = new Big('10.0')

      const fetchSpy = vi.spyOn(store, 'fetchRiskDashboard').mockResolvedValue()

      wrapper = mount(RiskDashboard, {
        global: {
          plugins: [pinia],
          stubs: {
            HeatGauge: true,
            HeatSparkline: true,
            CampaignRiskList: true,
            ProximityWarningsBanner: true,
          },
        },
      })

      await wrapper.vm.$nextTick()

      // Find and click refresh button (not retry button)
      const buttons = wrapper.findAll('button')
      const refreshButton = buttons.find(
        (btn) => btn.attributes('title')?.includes('Refresh')
      )

      expect(refreshButton).toBeDefined()
      await refreshButton!.trigger('click')

      expect(fetchSpy).toHaveBeenCalled()
    })

    it('should disable refresh button while loading', async () => {
      const store = usePortfolioStore()
      store.loading = true
      store.totalHeat = new Big('7.2')
      store.totalHeatLimit = new Big('10.0')

      wrapper = mount(RiskDashboard, {
        global: {
          plugins: [pinia],
          stubs: {
            HeatGauge: true,
            HeatSparkline: true,
            CampaignRiskList: true,
            ProximityWarningsBanner: true,
          },
        },
      })

      await wrapper.vm.$nextTick()

      const buttons = wrapper.findAll('button')
      const refreshButton = buttons.find(
        (btn) => btn.attributes('title')?.includes('Loading')
      )

      expect(refreshButton).toBeDefined()
      expect(refreshButton!.attributes('disabled')).toBeDefined()
    })
  })

  describe('WebSocket Connection Status', () => {
    it('should show "Real-time updates active" when WebSocket connected', async () => {
      const store = usePortfolioStore()
      store.totalHeat = new Big('7.2')
      store.totalHeatLimit = new Big('10.0')

      wrapper = mount(RiskDashboard, {
        global: {
          plugins: [pinia],
          stubs: {
            HeatGauge: true,
            HeatSparkline: true,
            CampaignRiskList: true,
            ProximityWarningsBanner: true,
          },
        },
      })

      await wrapper.vm.$nextTick()

      expect(wrapper.text()).toContain('Real-time updates active')
      // Should have green indicator
      expect(wrapper.find('.bg-green-500').exists()).toBe(true)
    })
  })

  describe('Proximity Warnings', () => {
    it('should display proximity warnings banner when warnings exist', async () => {
      const store = usePortfolioStore()
      store.totalHeat = new Big('8.5')
      store.totalHeatLimit = new Big('10.0')
      store.proximityWarnings = ['Portfolio heat at 85% capacity']

      wrapper = mount(RiskDashboard, {
        global: {
          plugins: [pinia],
          stubs: {
            HeatGauge: true,
            HeatSparkline: true,
            CampaignRiskList: true,
            // Don't stub ProximityWarningsBanner so we can test it renders
          },
        },
      })

      await wrapper.vm.$nextTick()

      // ProximityWarningsBanner component should be rendered
      expect(wrapper.html()).toContain('proximity-warnings')
    })
  })

  describe('Sector Risk Display', () => {
    it('should display sector correlation risks', async () => {
      const store = usePortfolioStore()
      store.totalHeat = new Big('7.2')
      store.totalHeatLimit = new Big('10.0')
      store.correlatedRisks = mockDashboardData.correlated_risks

      wrapper = mount(RiskDashboard, {
        global: {
          plugins: [pinia],
          stubs: {
            HeatGauge: true,
            HeatSparkline: true,
            CampaignRiskList: true,
            ProximityWarningsBanner: true,
          },
        },
      })

      await wrapper.vm.$nextTick()

      expect(wrapper.text()).toContain('Technology')
      expect(wrapper.text()).toContain('4.1%')
    })

    it('should show empty state when no sector risks', async () => {
      const store = usePortfolioStore()
      store.totalHeat = new Big('7.2')
      store.totalHeatLimit = new Big('10.0')
      store.correlatedRisks = []

      wrapper = mount(RiskDashboard, {
        global: {
          plugins: [pinia],
          stubs: {
            HeatGauge: true,
            HeatSparkline: true,
            CampaignRiskList: true,
            ProximityWarningsBanner: true,
          },
        },
      })

      await wrapper.vm.$nextTick()

      expect(wrapper.text()).toContain('No sector concentration detected')
    })
  })
})
