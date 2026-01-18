/**
 * Push Notifications Composable (Story 11.6)
 *
 * Provides functionality for managing browser push notification subscriptions.
 */

import { ref, type Ref } from 'vue'
import { apiClient } from '@/services/api'

export interface PushSubscriptionState {
  isSupported: boolean
  isSubscribed: boolean
  permission: NotificationPermission
  isLoading: boolean
  error: string | null
}

/**
 * Composable for managing push notifications.
 *
 * Handles:
 * - Permission requests
 * - Service worker registration
 * - Push subscription creation/deletion
 * - Backend sync
 */
export function usePushNotifications() {
  const state: Ref<PushSubscriptionState> = ref({
    isSupported: 'serviceWorker' in navigator && 'PushManager' in window,
    isSubscribed: false,
    permission: 'default' as NotificationPermission,
    isLoading: false,
    error: null,
  })

  /**
   * Check if push notifications are supported.
   */
  function checkSupport(): boolean {
    state.value.isSupported =
      'serviceWorker' in navigator && 'PushManager' in window

    if (!state.value.isSupported) {
      state.value.error = 'Push notifications are not supported in this browser'
    }

    return state.value.isSupported
  }

  /**
   * Register service worker.
   */
  async function registerServiceWorker(): Promise<ServiceWorkerRegistration> {
    if (!checkSupport()) {
      throw new Error('Service workers not supported')
    }

    try {
      const registration = await navigator.serviceWorker.register('/sw.js', {
        scope: '/',
      })

      console.log('[Push] Service worker registered:', registration)

      // Wait for service worker to be ready
      await navigator.serviceWorker.ready

      return registration
    } catch (err: unknown) {
      console.error('[Push] Service worker registration failed:', err)
      state.value.error = 'Failed to register service worker'
      throw err
    }
  }

  /**
   * Request notification permission from user.
   */
  async function requestPermission(): Promise<NotificationPermission> {
    if (!checkSupport()) {
      throw new Error('Notifications not supported')
    }

    try {
      const permission = await Notification.requestPermission()
      state.value.permission = permission

      console.log('[Push] Permission:', permission)

      if (permission === 'denied') {
        state.value.error =
          'Notification permission denied. Please enable in browser settings.'
      }

      return permission
    } catch (err: unknown) {
      console.error('[Push] Permission request failed:', err)
      state.value.error = 'Failed to request permission'
      throw err
    }
  }

  /**
   * Subscribe to push notifications.
   *
   * @param vapidPublicKey - VAPID public key from backend
   */
  async function subscribe(vapidPublicKey: string): Promise<void> {
    state.value.isLoading = true
    state.value.error = null

    try {
      // Check permission
      if (Notification.permission !== 'granted') {
        const permission = await requestPermission()
        if (permission !== 'granted') {
          throw new Error('Notification permission not granted')
        }
      }

      // Register service worker
      const registration = await registerServiceWorker()

      // Subscribe to push manager
      const subscription = await registration.pushManager.subscribe({
        userVisibleOnly: true,
        applicationServerKey: urlBase64ToUint8Array(vapidPublicKey),
      })

      console.log('[Push] Subscription created:', subscription)

      // Send subscription to backend
      const subscriptionData = {
        endpoint: subscription.endpoint,
        keys: {
          p256dh: arrayBufferToBase64(subscription.getKey('p256dh')),
          auth: arrayBufferToBase64(subscription.getKey('auth')),
        },
      }

      await apiClient.post(
        '/api/v1/notifications/push/subscribe',
        subscriptionData
      )

      state.value.isSubscribed = true
      console.log('[Push] Subscribed successfully')
    } catch (err: unknown) {
      console.error('[Push] Subscription failed:', err)
      state.value.error =
        (err instanceof Error ? err.message : null) ||
        'Failed to subscribe to push notifications'
      throw err
    } finally {
      state.value.isLoading = false
    }
  }

  /**
   * Unsubscribe from push notifications.
   */
  async function unsubscribe(): Promise<void> {
    state.value.isLoading = true
    state.value.error = null

    try {
      const registration = await navigator.serviceWorker.ready
      const subscription = await registration.pushManager.getSubscription()

      if (!subscription) {
        console.log('[Push] No active subscription')
        state.value.isSubscribed = false
        return
      }

      // Unsubscribe from push manager
      await subscription.unsubscribe()

      // Remove subscription from backend
      await apiClient.delete('/api/v1/notifications/push/unsubscribe', {
        params: { endpoint: subscription.endpoint },
      })

      state.value.isSubscribed = false
      console.log('[Push] Unsubscribed successfully')
    } catch (err: unknown) {
      console.error('[Push] Unsubscribe failed:', err)
      state.value.error =
        (err instanceof Error ? err.message : null) ||
        'Failed to unsubscribe from push notifications'
      throw err
    } finally {
      state.value.isLoading = false
    }
  }

  /**
   * Check current subscription status.
   */
  async function checkSubscriptionStatus(): Promise<boolean> {
    if (!checkSupport()) {
      return false
    }

    try {
      const registration = await navigator.serviceWorker.getRegistration()
      if (!registration) {
        state.value.isSubscribed = false
        return false
      }

      const subscription = await registration.pushManager.getSubscription()
      state.value.isSubscribed = !!subscription
      state.value.permission = Notification.permission

      return state.value.isSubscribed
    } catch (err: unknown) {
      console.error('[Push] Failed to check subscription:', err)
      return false
    }
  }

  /**
   * Convert URL-safe base64 to Uint8Array for VAPID key.
   */
  function urlBase64ToUint8Array(base64String: string): Uint8Array {
    const padding = '='.repeat((4 - (base64String.length % 4)) % 4)
    const base64 = (base64String + padding)
      .replace(/-/g, '+')
      .replace(/_/g, '/')

    const rawData = window.atob(base64)
    const outputArray = new Uint8Array(rawData.length)

    for (let i = 0; i < rawData.length; ++i) {
      outputArray[i] = rawData.charCodeAt(i)
    }

    return outputArray
  }

  /**
   * Convert ArrayBuffer to base64 string.
   */
  function arrayBufferToBase64(buffer: ArrayBuffer | null): string {
    if (!buffer) return ''

    const bytes = new Uint8Array(buffer)
    let binary = ''
    for (let i = 0; i < bytes.length; i++) {
      binary += String.fromCharCode(bytes[i])
    }
    return window.btoa(binary)
  }

  return {
    state,
    checkSupport,
    requestPermission,
    subscribe,
    unsubscribe,
    checkSubscriptionStatus,
  }
}
