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
  // Help System Routes (Story 11.8a - Task 15)
  {
    path: '/help',
    name: 'help',
    component: () => import('@/components/help/HelpCenter.vue'),
    meta: {
      title: 'Help Center',
      breadcrumb: [{ label: 'Help' }],
    },
    children: [
      {
        path: 'glossary',
        name: 'help-glossary',
        component: () => import('@/components/help/GlossaryView.vue'),
        meta: {
          title: 'Glossary',
          breadcrumb: [{ label: 'Help', to: '/help' }, { label: 'Glossary' }],
        },
      },
      {
        path: 'article/:slug',
        name: 'help-article',
        component: () => import('@/components/help/ArticleView.vue'),
        meta: {
          title: 'Article',
          breadcrumb: [{ label: 'Help', to: '/help' }, { label: 'Article' }],
        },
      },
      {
        path: 'search',
        name: 'help-search',
        component: () => import('@/components/help/SearchResults.vue'),
        meta: {
          title: 'Search Results',
          breadcrumb: [{ label: 'Help', to: '/help' }, { label: 'Search' }],
        },
      },
    ],
  },
  // Tutorial System Routes (Story 11.8b - Task 10)
  {
    path: '/tutorials',
    name: 'tutorials',
    component: () => import('@/components/help/TutorialView.vue'),
    meta: {
      title: 'Tutorials',
      breadcrumb: [{ label: 'Tutorials' }],
    },
  },
  {
    path: '/tutorials/:slug',
    name: 'tutorial-walkthrough',
    component: () => import('@/components/help/TutorialWalkthrough.vue'),
    meta: {
      title: 'Tutorial',
      breadcrumb: [
        { label: 'Tutorials', to: '/tutorials' },
        { label: 'Tutorial' },
      ],
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
