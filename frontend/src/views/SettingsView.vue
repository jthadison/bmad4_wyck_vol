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

      <div v-else-if="activeTab === 'general'" class="placeholder-content">
        <i class="pi pi-cog placeholder-icon"></i>
        <p>General settings coming soon in Epic 11</p>
      </div>

      <div v-else-if="activeTab === 'account'" class="placeholder-content">
        <i class="pi pi-user placeholder-icon"></i>
        <p>Account settings coming soon in Epic 11</p>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import NotificationPreferences from '@/components/notifications/NotificationPreferences.vue'
import WatchlistSettings from '@/components/watchlist/WatchlistSettings.vue'

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
    id: 'general',
    label: 'General',
    icon: 'pi pi-cog',
  },
  {
    id: 'account',
    label: 'Account',
    icon: 'pi pi-user',
  },
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
</style>
