import { createRouter, createWebHistory, type RouteRecordRaw } from 'vue-router'
import DashboardView from '@/views/DashboardView.vue'
import BacktestView from '@/views/BacktestView.vue'
import SettingsView from '@/views/SettingsView.vue'
import NotFoundView from '@/views/NotFoundView.vue'
import TradeAuditLog from '@/components/audit/TradeAuditLog.vue'
import ConfigurationWizard from '@/components/configuration/ConfigurationWizard.vue'
import CampaignTracker from '@/components/campaigns/CampaignTracker.vue'
import ScannerView from '@/views/ScannerView.vue'

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
    path: '/settings/auto-execution',
    name: 'auto-execution',
    component: () => import('@/views/settings/AutoExecutionSettings.vue'),
    meta: {
      title: 'Auto-Execution Settings',
      breadcrumb: [
        { label: 'Settings', to: '/settings' },
        { label: 'Auto-Execution' },
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
  // Scanner Control UI (Story 20.6)
  {
    path: '/scanner',
    name: 'scanner',
    component: ScannerView,
    meta: {
      title: 'Signal Scanner',
      description: 'Configure and control the background signal scanner',
      breadcrumb: [{ label: 'Scanner' }],
    },
  },
  // /signals → redirect to queue (signal-generation tests navigate here)
  {
    path: '/signals',
    redirect: '/signals/queue',
  },
  // Signal Approval Queue (Story 23.10)
  {
    path: '/signals/queue',
    name: 'signal-queue',
    component: () => import('@/views/signals/SignalApprovalView.vue'),
    meta: {
      title: 'Signal Approval Queue',
      breadcrumb: [{ label: 'Signal Queue' }],
    },
  },
  // Signal Performance Dashboard (Story 19.18)
  {
    path: '/signals/performance',
    name: 'signal-performance',
    component: () => import('@/views/signals/SignalDashboard.vue'),
    meta: {
      title: 'Signal Performance',
      breadcrumb: [{ label: 'Signal Performance' }],
    },
  },
  // Pattern Effectiveness Report (Story 19.19)
  {
    path: '/signals/patterns/effectiveness',
    name: 'pattern-effectiveness',
    component: () => import('@/views/signals/PatternEffectivenessReport.vue'),
    meta: {
      title: 'Pattern Effectiveness',
      breadcrumb: [
        { label: 'Signals', to: '/signals/performance' },
        { label: 'Pattern Effectiveness' },
      ],
    },
  },
  // Help System Routes (Story 11.8a - Task 15, Story 11.8c - Task 7)
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
        path: 'faq',
        name: 'help-faq',
        component: () => import('@/components/help/FAQView.vue'),
        meta: {
          title: 'FAQ',
          breadcrumb: [{ label: 'Help', to: '/help' }, { label: 'FAQ' }],
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
  // Production Monitoring Dashboard (Story 23.13)
  {
    path: '/monitoring',
    name: 'monitoring',
    component: () => import('@/components/monitoring/MonitoringDashboard.vue'),
    meta: {
      title: 'Production Monitoring',
      breadcrumb: [{ label: 'Monitoring' }],
    },
  },
  // Backtest Report Routes (Story 12.6D - Task 24)
  {
    path: '/backtest/results',
    name: 'BacktestResultsList',
    component: () => import('@/views/backtest/BacktestResultsListView.vue'),
    meta: {
      title: 'Backtest Results',
      breadcrumb: [{ label: 'Backtest Results' }],
    },
  },
  {
    path: '/backtest/results/:backtest_run_id',
    name: 'BacktestReportDetail',
    component: () => import('@/views/backtest/BacktestReportView.vue'),
    props: true,
    meta: {
      title: 'Backtest Report',
      breadcrumb: [
        { label: 'Backtest Results', to: '/backtest/results' },
        { label: 'Report Detail' },
      ],
    },
  },
  // Audit Trail Admin Dashboard (Task #2)
  {
    path: '/admin/audit-trail',
    name: 'audit-trail',
    component: () => import('@/views/admin/AuditTrailView.vue'),
    meta: {
      title: 'Audit Trail',
      breadcrumb: [{ label: 'Admin' }, { label: 'Audit Trail' }],
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
