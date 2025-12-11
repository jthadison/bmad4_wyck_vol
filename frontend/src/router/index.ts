import { createRouter, createWebHistory, type RouteRecordRaw } from 'vue-router'
import DashboardView from '@/views/DashboardView.vue'
import BacktestView from '@/views/BacktestView.vue'
import SettingsView from '@/views/SettingsView.vue'
import NotFoundView from '@/views/NotFoundView.vue'
import TradeAuditLog from '@/components/audit/TradeAuditLog.vue'
import ConfigurationWizard from '@/components/configuration/ConfigurationWizard.vue'
import CampaignTracker from '@/components/campaigns/CampaignTracker.vue'

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
    path: '/settings/configuration',
    name: 'configuration',
    component: ConfigurationWizard,
    meta: {
      title: 'System Configuration',
      breadcrumb: [
        { label: 'Settings', to: '/settings' },
        { label: 'Configuration' },
      ],
    },
  },
  {
    path: '/audit-log',
    name: 'audit-log',
    component: TradeAuditLog,
  },
  {
    path: '/campaigns',
    name: 'campaigns',
    component: CampaignTracker,
    meta: {
      title: 'Campaign Tracker',
      description:
        'Monitor active trading campaigns with progression and health status',
    },
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
