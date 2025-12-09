import { createRouter, createWebHistory, type RouteRecordRaw } from 'vue-router'
import DashboardView from '@/views/DashboardView.vue'
import BacktestView from '@/views/BacktestView.vue'
import SettingsView from '@/views/SettingsView.vue'
import NotFoundView from '@/views/NotFoundView.vue'
import TradeAuditLog from '@/components/audit/TradeAuditLog.vue'

const routes: RouteRecordRaw[] = [
  {
    path: '/',
    name: 'dashboard',
    component: DashboardView,
  },
  {
    path: '/backtest',
    name: 'backtest',
    component: BacktestView,
  },
  {
    path: '/settings',
    name: 'settings',
    component: SettingsView,
  },
  {
    path: '/audit-log',
    name: 'audit-log',
    component: TradeAuditLog,
  },
  {
    path: '/:pathMatch(.*)*',
    name: 'not-found',
    component: NotFoundView,
  },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

export default router
