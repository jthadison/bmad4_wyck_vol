/**
 * Notification Store
 *
 * Pinia store for notification state management.
 * Handles fetching, updating, and WebSocket subscriptions.
 *
 * Story: 11.6 - Notification & Alert System
 */

import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import type {
  Notification,
  NotificationPreferences,
  NotificationType,
  NotificationListResponse,
} from '@/types/notification'
import { apiClient } from '@/services/api'

export const useNotificationStore = defineStore('notification', () => {
  // State
  const notifications = ref<Notification[]>([])
  const preferences = ref<NotificationPreferences | null>(null)
  const isLoading = ref(false)
  const error = ref<string | null>(null)
  const totalCount = ref(0)

  // Getters
  const unreadNotifications = computed(() =>
    notifications.value.filter((n) => !n.read)
  )

  const unreadCount = computed(() => unreadNotifications.value.length)

  const notificationsByType = computed(() => {
    const byType: Record<string, Notification[]> = {}
    notifications.value.forEach((n) => {
      if (!byType[n.notification_type]) {
        byType[n.notification_type] = []
      }
      byType[n.notification_type].push(n)
    })
    return byType
  })

  // Actions
  async function fetchNotifications(
    unreadOnly = false,
    notificationType?: NotificationType,
    limit = 50,
    offset = 0
  ): Promise<void> {
    isLoading.value = true
    error.value = null

    try {
      const params: any = { limit, offset }
      if (unreadOnly) params.unread_only = true
      if (notificationType) params.notification_type = notificationType

      const response = await apiClient.get<NotificationListResponse>(
        '/api/v1/notifications',
        { params }
      )

      if (offset === 0) {
        notifications.value = response.data.data
      } else {
        notifications.value.push(...response.data.data)
      }

      totalCount.value = response.data.pagination.total_count
    } catch (err: any) {
      error.value = err.message || 'Failed to fetch notifications'
      console.error('Error fetching notifications:', err)
    } finally {
      isLoading.value = false
    }
  }

  async function markAsRead(notificationId: string): Promise<void> {
    try {
      await apiClient.patch(`/api/v1/notifications/${notificationId}/read`)

      // Update local state
      const notification = notifications.value.find(
        (n) => n.id === notificationId
      )
      if (notification) {
        notification.read = true
      }
    } catch (err: any) {
      console.error('Error marking notification as read:', err)
      throw err
    }
  }

  async function markAllAsRead(): Promise<void> {
    const unread = unreadNotifications.value

    for (const notification of unread) {
      try {
        await markAsRead(notification.id)
      } catch (err) {
        console.error(`Failed to mark ${notification.id} as read:`, err)
      }
    }
  }

  async function fetchPreferences(): Promise<void> {
    isLoading.value = true
    error.value = null

    try {
      const response = await apiClient.get<NotificationPreferences>(
        '/api/v1/notifications/preferences'
      )
      preferences.value = response.data
    } catch (err: any) {
      error.value = err.message || 'Failed to fetch preferences'
      console.error('Error fetching preferences:', err)
    } finally {
      isLoading.value = false
    }
  }

  async function updatePreferences(
    newPreferences: NotificationPreferences
  ): Promise<void> {
    isLoading.value = true
    error.value = null

    try {
      await apiClient.post('/api/v1/notifications/preferences', newPreferences)
      preferences.value = newPreferences
    } catch (err: any) {
      error.value = err.message || 'Failed to update preferences'
      console.error('Error updating preferences:', err)
      throw err
    } finally {
      isLoading.value = false
    }
  }

  async function sendTestNotification(
    channel: 'sms' | 'email' | 'push'
  ): Promise<void> {
    try {
      await apiClient.post(`/api/v1/notifications/test/${channel}`)
    } catch (err: any) {
      console.error(`Error sending test ${channel}:`, err)
      throw err
    }
  }

  function handleToastNotification(notification: Notification): void {
    // Add to local notifications list
    notifications.value.unshift(notification)
    totalCount.value += 1

    // Notification will be displayed by toast handler in App.vue
  }

  function reset(): void {
    notifications.value = []
    preferences.value = null
    error.value = null
    totalCount.value = 0
  }

  return {
    // State
    notifications,
    preferences,
    isLoading,
    error,
    totalCount,

    // Getters
    unreadNotifications,
    unreadCount,
    notificationsByType,

    // Actions
    fetchNotifications,
    markAsRead,
    markAllAsRead,
    fetchPreferences,
    updatePreferences,
    sendTestNotification,
    handleToastNotification,
    reset,
  }
})
