<template>
  <div class="notification-center">
    <!-- Notification Bell Icon with Badge -->
    <div class="notification-bell" @click="togglePanel">
      <i class="pi pi-bell" :class="{ 'has-unread': unreadCount > 0 }"></i>
      <span v-if="unreadCount > 0" class="badge">{{ unreadCount }}</span>
    </div>

    <!-- Notification Panel (Dropdown) -->
    <div v-if="isPanelOpen" class="notification-panel">
      <div class="panel-header">
        <h3>Notifications</h3>
        <button
          v-if="unreadCount > 0"
          class="mark-all-btn"
          @click="markAllRead"
        >
          Mark all read
        </button>
      </div>

      <!-- Filter Tabs -->
      <div class="filter-tabs">
        <button
          v-for="filter in filters"
          :key="filter.value"
          :class="['filter-tab', { active: currentFilter === filter.value }]"
          @click="currentFilter = filter.value"
        >
          {{ filter.label }}
        </button>
      </div>

      <!-- Notification List -->
      <div class="notification-list">
        <div v-if="filteredNotifications.length === 0" class="empty-state">
          <p>No notifications</p>
        </div>

        <div
          v-for="notification in filteredNotifications"
          :key="notification.id"
          :class="['notification-item', { unread: !notification.read }]"
          @click="handleNotificationClick(notification)"
        >
          <div class="notification-icon">
            <i :class="getNotificationIcon(notification.notification_type)"></i>
          </div>

          <div class="notification-content">
            <div class="notification-title">{{ notification.title }}</div>
            <div class="notification-message">{{ notification.message }}</div>
            <div class="notification-time">
              {{ formatTime(notification.created_at) }}
            </div>
          </div>

          <div v-if="!notification.read" class="unread-indicator"></div>
        </div>
      </div>

      <!-- View All Link -->
      <div class="panel-footer">
        <router-link to="/notifications" class="view-all-link">
          View all notifications
        </router-link>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useNotificationStore } from '@/stores/notificationStore'
import { useRouter } from 'vue-router'
import type { Notification, NotificationType } from '@/types/notification'

const notificationStore = useNotificationStore()
const router = useRouter()

const isPanelOpen = ref(false)
const currentFilter = ref<string>('all')

const filters = [
  { label: 'All', value: 'all' },
  { label: 'Unread', value: 'unread' },
  { label: 'Signals', value: 'signal_generated' },
  { label: 'Warnings', value: 'warnings' },
]

const unreadCount = computed(() => notificationStore.unreadCount)

const filteredNotifications = computed(() => {
  let filtered = notificationStore.notifications

  if (currentFilter.value === 'unread') {
    filtered = notificationStore.unreadNotifications
  } else if (currentFilter.value === 'signal_generated') {
    filtered = filtered.filter(
      (n) => n.notification_type === 'signal_generated'
    )
  } else if (currentFilter.value === 'warnings') {
    filtered = filtered.filter(
      (n) =>
        n.notification_type === 'risk_warning' ||
        n.notification_type === 'emergency_exit'
    )
  }

  return filtered.slice(0, 10) // Show max 10 in dropdown
})

function togglePanel() {
  isPanelOpen.value = !isPanelOpen.value
}

async function markAllRead() {
  await notificationStore.markAllAsRead()
}

async function handleNotificationClick(notification: Notification) {
  // Mark as read
  if (!notification.read) {
    await notificationStore.markAsRead(notification.id)
  }

  // Navigate based on notification type
  if (notification.notification_type === 'signal_generated') {
    const signalId = notification.metadata.signal_id
    if (signalId) {
      router.push(`/signals/${signalId}`)
    }
  } else if (notification.notification_type === 'risk_warning') {
    router.push('/risk-dashboard')
  }

  isPanelOpen.value = false
}

function getNotificationIcon(type: NotificationType): string {
  switch (type) {
    case 'signal_generated':
      return 'pi pi-chart-line'
    case 'risk_warning':
      return 'pi pi-exclamation-triangle'
    case 'emergency_exit':
      return 'pi pi-times-circle'
    case 'system_error':
      return 'pi pi-exclamation-circle'
    default:
      return 'pi pi-info-circle'
  }
}

function formatTime(timestamp: string): string {
  const date = new Date(timestamp)
  const now = new Date()
  const diff = now.getTime() - date.getTime()

  const minutes = Math.floor(diff / 60000)
  const hours = Math.floor(diff / 3600000)
  const days = Math.floor(diff / 86400000)

  if (minutes < 1) return 'Just now'
  if (minutes < 60) return `${minutes}m ago`
  if (hours < 24) return `${hours}h ago`
  if (days < 7) return `${days}d ago`

  return date.toLocaleDateString()
}

onMounted(() => {
  notificationStore.fetchNotifications()
})
</script>

<style scoped>
.notification-center {
  position: relative;
}

.notification-bell {
  position: relative;
  cursor: pointer;
  padding: 8px;
}

.notification-bell i {
  font-size: 20px;
  color: #64748b;
  transition: color 0.3s;
}

.notification-bell i.has-unread {
  color: #3b82f6;
}

.badge {
  position: absolute;
  top: 4px;
  right: 4px;
  background-color: #ef4444;
  color: white;
  border-radius: 10px;
  padding: 2px 6px;
  font-size: 11px;
  font-weight: bold;
}

.notification-panel {
  position: absolute;
  top: 50px;
  right: 0;
  width: 380px;
  max-height: 600px;
  background: white;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
  z-index: 1000;
  display: flex;
  flex-direction: column;
}

.panel-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 16px;
  border-bottom: 1px solid #e2e8f0;
}

.panel-header h3 {
  margin: 0;
  font-size: 18px;
  font-weight: 600;
}

.mark-all-btn {
  background: none;
  border: none;
  color: #3b82f6;
  cursor: pointer;
  font-size: 14px;
}

.filter-tabs {
  display: flex;
  padding: 8px 16px;
  border-bottom: 1px solid #e2e8f0;
  gap: 8px;
}

.filter-tab {
  background: none;
  border: none;
  padding: 6px 12px;
  border-radius: 4px;
  cursor: pointer;
  font-size: 14px;
  color: #64748b;
  transition: background-color 0.2s;
}

.filter-tab.active {
  background-color: #eff6ff;
  color: #3b82f6;
  font-weight: 600;
}

.notification-list {
  overflow-y: auto;
  flex: 1;
}

.empty-state {
  padding: 40px 20px;
  text-align: center;
  color: #94a3b8;
}

.notification-item {
  display: flex;
  padding: 12px 16px;
  border-bottom: 1px solid #f1f5f9;
  cursor: pointer;
  transition: background-color 0.2s;
}

.notification-item:hover {
  background-color: #f8fafc;
}

.notification-item.unread {
  background-color: #eff6ff;
}

.notification-icon {
  flex-shrink: 0;
  width: 40px;
  height: 40px;
  border-radius: 50%;
  background-color: #e0e7ff;
  display: flex;
  align-items: center;
  justify-content: center;
  margin-right: 12px;
}

.notification-icon i {
  color: #3b82f6;
  font-size: 18px;
}

.notification-content {
  flex: 1;
  min-width: 0;
}

.notification-title {
  font-weight: 600;
  font-size: 14px;
  color: #1e293b;
  margin-bottom: 4px;
}

.notification-message {
  font-size: 13px;
  color: #64748b;
  margin-bottom: 4px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.notification-time {
  font-size: 12px;
  color: #94a3b8;
}

.unread-indicator {
  flex-shrink: 0;
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background-color: #3b82f6;
  margin-left: 8px;
  margin-top: 16px;
}

.panel-footer {
  padding: 12px 16px;
  border-top: 1px solid #e2e8f0;
  text-align: center;
}

.view-all-link {
  color: #3b82f6;
  text-decoration: none;
  font-size: 14px;
  font-weight: 600;
}
</style>
