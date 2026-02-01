/**
 * Service Worker for Push Notifications (Story 11.6)
 *
 * Handles browser push notifications from the backend notification system.
 */

// Service worker install event
self.addEventListener('install', () => {
  console.log('[Service Worker] Installed')
  self.skipWaiting() // Activate immediately
})

// Service worker activate event
self.addEventListener('activate', (event) => {
  console.log('[Service Worker] Activated')
  event.waitUntil(self.clients.claim()) // Take control of all pages
})

// Push event handler
self.addEventListener('push', (event) => {
  console.log('[Service Worker] Push received', event)

  if (!event.data) {
    console.log('[Service Worker] Push event has no data')
    return
  }

  let data
  try {
    data = event.data.json()
  } catch (e) {
    console.error('[Service Worker] Failed to parse push data:', e)
    data = { title: 'Notification', body: event.data.text() }
  }

  const title = data.title || 'BMAD Wyckoff'
  const options = {
    body: data.body || data.message || 'You have a new notification',
    icon: '/favicon.ico',
    badge: '/favicon.ico',
    tag: data.notification_id || 'default',
    data: {
      notification_id: data.notification_id,
      notification_type: data.notification_type,
      url: data.url || '/',
    },
    requireInteraction: data.priority === 'critical', // Sticky for critical
    vibrate: data.priority === 'critical' ? [200, 100, 200] : [100],
  }

  event.waitUntil(self.registration.showNotification(title, options))
})

// Notification click handler
self.addEventListener('notificationclick', (event) => {
  console.log('[Service Worker] Notification clicked:', event.notification)

  event.notification.close()

  const notificationData = event.notification.data || {}
  const url = notificationData.url || '/'

  // Navigate to notification URL
  event.waitUntil(
    clients
      .matchAll({ type: 'window', includeUncontrolled: true })
      .then((clientList) => {
        // Check if app is already open
        for (const client of clientList) {
          if (client.url.includes(url) && 'focus' in client) {
            return client.focus()
          }
        }

        // Open new window if app not open
        if (clients.openWindow) {
          return clients.openWindow(url)
        }
      })
  )
})

// Message handler for communication with main thread
self.addEventListener('message', (event) => {
  console.log('[Service Worker] Message received:', event.data)

  if (event.data && event.data.type === 'SKIP_WAITING') {
    self.skipWaiting()
  }
})
