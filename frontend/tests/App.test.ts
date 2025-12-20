import { describe, it, expect, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { createRouter, createWebHistory } from 'vue-router'
import { createPinia } from 'pinia'
import PrimeVue from 'primevue/config'
import ToastService from 'primevue/toastservice'
import App from '../src/App.vue'

// Mock useWebSocket to prevent actual WebSocket connections in tests
vi.mock('@/composables/useWebSocket', () => ({
  useWebSocket: () => ({
    isConnected: { value: false },
    connectionStatus: { value: 'disconnected' },
    subscribe: vi.fn(),
    unsubscribe: vi.fn(),
    getConnectionId: vi.fn(() => null),
    getLastSequenceNumber: vi.fn(() => 0),
  }),
}))

// Mock API client
vi.mock('@/services/api', () => ({
  apiClient: {
    get: vi.fn().mockResolvedValue({
      status: 'operational',
      bars_analyzed: 0,
      patterns_detected: 0,
      signals_executed: 0,
    }),
  },
}))

describe('App.vue', () => {
  it('renders successfully', () => {
    const router = createRouter({
      history: createWebHistory(),
      routes: [{ path: '/', component: { template: '<div>Home</div>' } }],
    })

    const pinia = createPinia()

    const wrapper = mount(App, {
      global: {
        plugins: [router, pinia, PrimeVue, ToastService],
      },
    })

    expect(wrapper.exists()).toBe(true)
  })

  it('has navigation menu with router links', () => {
    const router = createRouter({
      history: createWebHistory(),
      routes: [
        { path: '/', component: { template: '<div>Home</div>' } },
        { path: '/backtest', component: { template: '<div>Backtest</div>' } },
        { path: '/settings', component: { template: '<div>Settings</div>' } },
      ],
    })

    const pinia = createPinia()

    const wrapper = mount(App, {
      global: {
        plugins: [router, pinia, PrimeVue, ToastService],
      },
    })

    expect(wrapper.text()).toContain('Dashboard')
    expect(wrapper.text()).toContain('Backtest')
    expect(wrapper.text()).toContain('Settings')
  })

  it('has router-view for route rendering', () => {
    const router = createRouter({
      history: createWebHistory(),
      routes: [{ path: '/', component: { template: '<div>Home</div>' } }],
    })

    const pinia = createPinia()

    const wrapper = mount(App, {
      global: {
        plugins: [router, pinia, PrimeVue, ToastService],
      },
    })

    expect(wrapper.findComponent({ name: 'RouterView' }).exists()).toBe(true)
  })
})
