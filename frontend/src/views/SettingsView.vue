<template>
  <div class="settings-view">
    <div class="settings-header">
      <h1 class="text-3xl font-bold mb-2">Settings</h1>
      <p class="text-gray-500">
        Configure your notification preferences and application settings
      </p>
    </div>

    <!-- Tab Navigation -->
    <div class="settings-tabs">
      <button
        v-for="tab in tabs"
        :key="tab.id"
        :class="['tab', { active: activeTab === tab.id }]"
        @click="activeTab = tab.id"
      >
        <i :class="tab.icon"></i>
        {{ tab.label }}
      </button>
    </div>

    <!-- Tab Content -->
    <div class="tab-content">
      <WatchlistSettings v-if="activeTab === 'watchlist'" />

      <NotificationPreferences v-else-if="activeTab === 'notifications'" />

      <PriceAlertManager v-else-if="activeTab === 'alerts'" />

      <div v-else-if="activeTab === 'system'" class="system-tab-content">
        <OrchestratorHealthPanel />
      </div>

      <div v-else-if="activeTab === 'general'" class="placeholder-content">
        <i class="pi pi-cog placeholder-icon"></i>
        <p>General settings coming soon in Epic 11</p>
      </div>

      <div v-else-if="activeTab === 'account'" class="placeholder-content">
        <i class="pi pi-user placeholder-icon"></i>
        <p>Account settings coming soon in Epic 11</p>
      </div>

      <div v-else-if="activeTab === 'baselines'" class="baselines-section">
        <h2 class="text-xl font-semibold mb-4">Backtest Baselines</h2>
        <p class="text-gray-500 mb-4">
          Regression baselines are established. Automated regression testing is
          active.
        </p>
        <table class="baselines-table">
          <thead>
            <tr>
              <th>Symbol</th>
              <th>Baseline Version</th>
              <th>Status</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="b in baselines" :key="b.symbol">
              <td>{{ b.symbol }}</td>
              <td>{{ b.version }}</td>
              <td class="status-active">Active</td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import NotificationPreferences from '@/components/notifications/NotificationPreferences.vue'
import WatchlistSettings from '@/components/watchlist/WatchlistSettings.vue'
import OrchestratorHealthPanel from '@/components/orchestrator/OrchestratorHealthPanel.vue'
import PriceAlertManager from '@/components/alerts/PriceAlertManager.vue'

const activeTab = ref('watchlist')

const tabs = [
  {
    id: 'watchlist',
    label: 'Watchlist',
    icon: 'pi pi-list',
  },
  {
    id: 'notifications',
    label: 'Notifications',
    icon: 'pi pi-bell',
  },
  {
    id: 'alerts',
    label: 'Price Alerts',
    icon: 'pi pi-bell-fill',
  },
  {
    id: 'system',
    label: 'System',
    icon: 'pi pi-server',
  },
  {
    id: 'general',
    label: 'General',
    icon: 'pi pi-cog',
  },
  {
    id: 'account',
    label: 'Account',
    icon: 'pi pi-user',
  },
  {
    id: 'baselines',
    label: 'Baselines',
    icon: 'pi pi-chart-bar',
  },
]

const baselines = [
  { symbol: 'SPX500', version: '23.3.1' },
  { symbol: 'US30', version: '23.3.1' },
  { symbol: 'EURUSD', version: '23.3.1' },
]
</script>

<style scoped>
.settings-view {
  padding: 24px;
  max-width: 1200px;
  margin: 0 auto;
}

.settings-header {
  margin-bottom: 24px;
}

.settings-tabs {
  display: flex;
  gap: 8px;
  border-bottom: 2px solid #e2e8f0;
  margin-bottom: 32px;
}

.tab {
  background: none;
  border: none;
  padding: 12px 20px;
  font-size: 15px;
  font-weight: 500;
  color: #64748b;
  cursor: pointer;
  border-bottom: 3px solid transparent;
  margin-bottom: -2px;
  transition: all 0.2s;
  display: flex;
  align-items: center;
  gap: 8px;
}

.tab:hover {
  color: #3b82f6;
}

.tab.active {
  color: #3b82f6;
  border-bottom-color: #3b82f6;
}

.tab i {
  font-size: 16px;
}

.tab-content {
  min-height: 400px;
}

.placeholder-content {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 80px 20px;
  color: #94a3b8;
}

.placeholder-icon {
  font-size: 64px;
  margin-bottom: 16px;
  opacity: 0.5;
}

.placeholder-content p {
  font-size: 16px;
}

.system-tab-content {
  max-width: 500px;
}

.baselines-section {
  padding: 16px;
  background: #f8fafc;
  border-radius: 8px;
  border: 1px solid #e2e8f0;
}

.baselines-table {
  width: 100%;
  border-collapse: collapse;
}

.baselines-table th,
.baselines-table td {
  text-align: left;
  padding: 10px 16px;
  border-bottom: 1px solid #e2e8f0;
}

.baselines-table th {
  font-weight: 600;
  color: #475569;
  font-size: 13px;
  text-transform: uppercase;
  letter-spacing: 0.05em;
}

.baselines-table td {
  font-size: 14px;
  color: #334155;
}

.status-active {
  color: #16a34a;
  font-weight: 500;
}
</style>
