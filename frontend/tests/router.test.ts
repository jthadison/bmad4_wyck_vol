import { describe, it, expect } from 'vitest'
import { createMemoryHistory, createRouter } from 'vue-router'
import DashboardView from '../src/views/DashboardView.vue'
import BacktestView from '../src/views/BacktestView.vue'
import SettingsView from '../src/views/SettingsView.vue'
import NotFoundView from '../src/views/NotFoundView.vue'

describe('Vue Router', () => {
  const routes = [
    { path: '/', name: 'dashboard', component: DashboardView },
    { path: '/backtest', name: 'backtest', component: BacktestView },
    { path: '/settings', name: 'settings', component: SettingsView },
    { path: '/:pathMatch(.*)*', name: 'not-found', component: NotFoundView },
  ]

  it('creates router instance', () => {
    const router = createRouter({
      history: createMemoryHistory(),
      routes,
    })

    expect(router).toBeDefined()
  })

  it('registers all routes', () => {
    const router = createRouter({
      history: createMemoryHistory(),
      routes,
    })

    const routeNames = router.getRoutes().map((r) => r.name)
    expect(routeNames).toContain('dashboard')
    expect(routeNames).toContain('backtest')
    expect(routeNames).toContain('settings')
    expect(routeNames).toContain('not-found')
  })

  it('navigates to dashboard route', async () => {
    const router = createRouter({
      history: createMemoryHistory(),
      routes,
    })

    await router.push('/')
    expect(router.currentRoute.value.name).toBe('dashboard')
  })

  it('navigates to backtest route', async () => {
    const router = createRouter({
      history: createMemoryHistory(),
      routes,
    })

    await router.push('/backtest')
    expect(router.currentRoute.value.name).toBe('backtest')
  })

  it('navigates to settings route', async () => {
    const router = createRouter({
      history: createMemoryHistory(),
      routes,
    })

    await router.push('/settings')
    expect(router.currentRoute.value.name).toBe('settings')
  })

  it('handles 404 not found route', async () => {
    const router = createRouter({
      history: createMemoryHistory(),
      routes,
    })

    await router.push('/invalid-route')
    expect(router.currentRoute.value.name).toBe('not-found')
  })
})
