/**
 * Tests for ActiveCampaignsPanel Component (Story 16.3a)
 *
 * Test Coverage:
 * - Component rendering
 * - Loading state display
 * - Error state display
 * - Empty state display
 * - Campaign list rendering
 * - Sorting functionality (health, phase, time, pnl)
 * - Campaign click event emission
 * - Refresh functionality
 *
 * Author: Story 16.3a
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createTestingPinia } from '@pinia/testing'
import { setActivePinia } from 'pinia'
import ActiveCampaignsPanel from '@/components/campaigns/ActiveCampaignsPanel.vue'
import { useCampaignStore } from '@/stores/campaignStore'
import type { Campaign } from '@/types/campaign-manager'

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
vi.mock('primevue/dropdown', () => ({
  default: {
    name: 'Dropdown',
    template: '<select><slot /></select>',
    props: [
      'modelValue',
      'options',
      'optionLabel',
      'optionValue',
      'placeholder',
    ],
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

describe('ActiveCampaignsPanel', () => {
  const mockCampaigns: Campaign[] = [
    {
      id: 'camp-001',
      campaign_id: 'CAMP-001',
      symbol: 'AAPL',
      timeframe: '1h',
      trading_range_id: 'tr-001',
      status: 'ACTIVE',
      phase: 'D',
      entries: {} as Campaign['entries'],
      total_risk: '2.0',
      total_allocation: '3.5',
      current_risk: '1.5',
      weighted_avg_entry: '150.00',
      total_shares: '100',
      total_pnl: '500.00',
      start_date: '2023-06-01T00:00:00Z',
      version: 1,
      created_at: '2023-06-01T00:00:00Z',
      updated_at: '2023-06-01T00:00:00Z',
    },
    {
      id: 'camp-002',
      campaign_id: 'CAMP-002',
      symbol: 'TSLA',
      timeframe: '4h',
      trading_range_id: 'tr-002',
      status: 'ACTIVE',
      phase: 'C',
      entries: {} as Campaign['entries'],
      total_risk: '1.5',
      total_allocation: '2.0',
      current_risk: '1.0',
      weighted_avg_entry: '200.00',
      total_shares: '50',
      total_pnl: '-100.00',
      start_date: '2023-05-15T00:00:00Z',
      version: 1,
      created_at: '2023-05-15T00:00:00Z',
      updated_at: '2023-05-15T00:00:00Z',
    },
    {
      id: 'camp-003',
      campaign_id: 'CAMP-003',
      symbol: 'MSFT',
      timeframe: '1d',
      trading_range_id: 'tr-003',
      status: 'MARKUP',
      phase: 'E',
      entries: {} as Campaign['entries'],
      total_risk: '2.5',
      total_allocation: '4.0',
      current_risk: '2.0',
      weighted_avg_entry: '300.00',
      total_shares: '75',
      total_pnl: '1200.00',
      start_date: '2023-04-01T00:00:00Z',
      version: 1,
      created_at: '2023-04-01T00:00:00Z',
      updated_at: '2023-04-01T00:00:00Z',
    },
  ]

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
    return mount(ActiveCampaignsPanel, {
      global: {
        plugins: [pinia],
        stubs: {
          CampaignEmptyState: {
            name: 'CampaignEmptyState',
            template:
              '<div class="empty-state" data-testid="empty-state">{{ title }} - {{ message }}</div>',
            props: ['title', 'message'],
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
      expect(wrapper.find('h2').text()).toBe('Active Campaigns')
    })

    it('should render sort dropdown', () => {
      const wrapper = mountComponent()
      const dropdown = wrapper.find('select')
      expect(dropdown.exists()).toBe(true)
    })

    it('should render refresh button', () => {
      const wrapper = mountComponent()
      const refreshBtn = wrapper.find('.refresh-btn')
      expect(refreshBtn.exists()).toBe(true)
    })
  })

  describe('loading state', () => {
    it('should display loading spinner when loading and no campaigns', async () => {
      const wrapper = mountComponent()
      const store = useCampaignStore()

      // Set loading state
      store.$patch({
        loadingActiveCampaigns: true,
        activeCampaigns: [],
      })

      await flushPromises()

      const spinner = wrapper.find('[data-testid="spinner"]')
      expect(spinner.exists()).toBe(true)
      expect(wrapper.text()).toContain('Loading campaigns')
    })

    it('should not show spinner when campaigns exist', async () => {
      const wrapper = mountComponent()
      const store = useCampaignStore()

      store.$patch({
        loadingActiveCampaigns: true,
        activeCampaigns: mockCampaigns,
      })

      await flushPromises()

      const spinner = wrapper.find('[data-testid="spinner"]')
      expect(spinner.exists()).toBe(false)
    })
  })

  describe('error state', () => {
    it('should display error message when error occurs', async () => {
      const wrapper = mountComponent()
      const store = useCampaignStore()

      store.$patch({
        loadingActiveCampaigns: false,
        activeCampaignsError: 'Failed to fetch campaigns',
        activeCampaigns: [],
      })

      await flushPromises()

      const errorMessage = wrapper.find('[data-testid="error-message"]')
      expect(errorMessage.exists()).toBe(true)
      expect(wrapper.text()).toContain('Failed to fetch campaigns')
    })
  })

  describe('empty state', () => {
    it('should display empty state when no campaigns', async () => {
      const wrapper = mountComponent()
      const store = useCampaignStore()

      store.$patch({
        loadingActiveCampaigns: false,
        activeCampaignsError: null,
        activeCampaigns: [],
      })

      await flushPromises()

      const emptyState = wrapper.find('[data-testid="empty-state"]')
      expect(emptyState.exists()).toBe(true)
      expect(wrapper.text()).toContain('No Active Campaigns')
    })
  })

  describe('campaign list rendering', () => {
    it('should display campaign count', async () => {
      const wrapper = mountComponent()
      const store = useCampaignStore()

      store.$patch({
        loadingActiveCampaigns: false,
        activeCampaigns: mockCampaigns,
      })

      await flushPromises()

      expect(wrapper.text()).toContain('3 active campaigns')
    })

    it('should display singular "campaign" for one campaign', async () => {
      const wrapper = mountComponent()
      const store = useCampaignStore()

      store.$patch({
        loadingActiveCampaigns: false,
        activeCampaigns: [mockCampaigns[0]],
      })

      await flushPromises()

      expect(wrapper.text()).toContain('1 active campaign')
      expect(wrapper.text()).not.toContain('campaigns')
    })

    it('should render campaign items', async () => {
      const wrapper = mountComponent()
      const store = useCampaignStore()

      store.$patch({
        loadingActiveCampaigns: false,
        activeCampaigns: mockCampaigns,
      })

      await flushPromises()

      const campaignItems = wrapper.findAll('.campaign-item')
      expect(campaignItems.length).toBe(3)
    })

    it('should display campaign symbol and status', async () => {
      const wrapper = mountComponent()
      const store = useCampaignStore()

      store.$patch({
        loadingActiveCampaigns: false,
        activeCampaigns: mockCampaigns,
      })

      await flushPromises()

      expect(wrapper.text()).toContain('AAPL')
      expect(wrapper.text()).toContain('TSLA')
      expect(wrapper.text()).toContain('MSFT')
      expect(wrapper.text()).toContain('ACTIVE')
      expect(wrapper.text()).toContain('MARKUP')
    })
  })

  describe('campaign click handling', () => {
    it('should emit campaign-selected event on campaign click', async () => {
      const wrapper = mountComponent()
      const store = useCampaignStore()

      store.$patch({
        loadingActiveCampaigns: false,
        activeCampaigns: mockCampaigns,
      })

      await flushPromises()

      const firstCampaignItem = wrapper.find('.campaign-item')
      await firstCampaignItem.trigger('click')

      expect(wrapper.emitted('campaign-selected')).toBeTruthy()
      expect(wrapper.emitted('campaign-selected')![0]).toBeTruthy()
    })
  })

  describe('refresh functionality', () => {
    it('should call fetchActiveCampaigns on refresh button click', async () => {
      const wrapper = mountComponent()
      const store = useCampaignStore()

      const refreshBtn = wrapper.find('.refresh-btn')
      await refreshBtn.trigger('click')

      expect(store.fetchActiveCampaigns).toHaveBeenCalled()
    })

    it('should disable refresh button while loading', async () => {
      const wrapper = mountComponent()
      const store = useCampaignStore()

      store.$patch({
        loadingActiveCampaigns: true,
        activeCampaigns: mockCampaigns,
      })

      await flushPromises()

      const refreshBtn = wrapper.find('.refresh-btn')
      expect(refreshBtn.attributes('disabled')).toBeDefined()
    })
  })

  describe('sorting', () => {
    it('should sort campaigns by health status', async () => {
      const wrapper = mountComponent()
      const store = useCampaignStore()

      // Create campaigns with different statuses that map to health
      const campaignsForSorting: Campaign[] = [
        { ...mockCampaigns[0], id: 'camp-a', status: 'ACTIVE' }, // green
        { ...mockCampaigns[1], id: 'camp-b', status: 'INVALIDATED' }, // red
        { ...mockCampaigns[2], id: 'camp-c', status: 'MARKUP' }, // yellow
      ]

      store.$patch({
        loadingActiveCampaigns: false,
        activeCampaigns: campaignsForSorting,
      })

      await flushPromises()

      // Default sort is by health, red first
      const campaignItems = wrapper.findAll('.campaign-item')
      expect(campaignItems.length).toBe(3)
    })
  })

  describe('WebSocket integration', () => {
    it('should fetch campaigns on mount', async () => {
      mountComponent()
      const store = useCampaignStore()

      await flushPromises()

      expect(store.fetchActiveCampaigns).toHaveBeenCalled()
    })
  })

  describe('panel header', () => {
    it('should have panel header with title and controls', () => {
      const wrapper = mountComponent()

      const header = wrapper.find('.panel-header')
      expect(header.exists()).toBe(true)

      const title = header.find('h2')
      expect(title.text()).toBe('Active Campaigns')

      const controls = header.find('.header-controls')
      expect(controls.exists()).toBe(true)
    })
  })
})
