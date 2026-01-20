<script setup lang="ts">
/**
 * EventFeedPanel Component (Story 16.3b)
 *
 * Displays live campaign events in a scrollable feed.
 * Integrates with WebSocket for real-time event updates.
 *
 * Features:
 * - Display live campaign events
 * - Filter by event type
 * - Relative timestamp display
 * - Auto-scroll to latest
 * - Event detail popup
 *
 * Author: Story 16.3b
 */

import { ref, computed, onMounted, onUnmounted, nextTick } from 'vue'
import Dropdown from 'primevue/dropdown'
import Dialog from 'primevue/dialog'
import Badge from 'primevue/badge'
import { useWebSocket } from '@/composables/useWebSocket'
import type { WebSocketMessage } from '@/types/websocket'

/**
 * Campaign event types for filtering
 */
type EventType =
  | 'all'
  | 'campaign:created'
  | 'campaign:updated'
  | 'campaign:invalidated'
  | 'signal:new'
  | 'pattern_detected'

interface FilterOption {
  label: string
  value: EventType
}

/**
 * Event data structure for display
 */
interface CampaignEvent {
  id: string
  type: string
  timestamp: Date
  data: Record<string, unknown>
  message: string
}

const filterOptions: FilterOption[] = [
  { label: 'All Events', value: 'all' },
  { label: 'Campaign Created', value: 'campaign:created' },
  { label: 'Campaign Updated', value: 'campaign:updated' },
  { label: 'Campaign Invalidated', value: 'campaign:invalidated' },
  { label: 'New Signal', value: 'signal:new' },
  { label: 'Pattern Detected', value: 'pattern_detected' },
]

/**
 * Local state
 */
const events = ref<CampaignEvent[]>([])
const selectedFilter = ref<EventType>('all')
const showDetailDialog = ref(false)
const selectedEvent = ref<CampaignEvent | null>(null)
const feedContainer = ref<HTMLElement | null>(null)
const autoScroll = ref(true)
const MAX_EVENTS = 100 // Keep last 100 events

/**
 * WebSocket
 */
const ws = useWebSocket()

/**
 * Filtered events based on selected filter
 */
const filteredEvents = computed(() => {
  if (selectedFilter.value === 'all') {
    return events.value
  }
  return events.value.filter((event) => event.type === selectedFilter.value)
})

/**
 * Format relative time (e.g., "2m ago", "1h ago")
 */
function formatRelativeTime(date: Date): string {
  const now = new Date()
  const diffMs = now.getTime() - date.getTime()
  const diffSec = Math.floor(diffMs / 1000)
  const diffMin = Math.floor(diffSec / 60)
  const diffHour = Math.floor(diffMin / 60)
  const diffDay = Math.floor(diffHour / 24)

  if (diffSec < 60) return 'just now'
  if (diffMin < 60) return `${diffMin}m ago`
  if (diffHour < 24) return `${diffHour}h ago`
  return `${diffDay}d ago`
}

/**
 * Get event icon based on type
 */
function getEventIcon(type: string): string {
  switch (type) {
    case 'campaign:created':
      return 'pi pi-plus-circle'
    case 'campaign:updated':
      return 'pi pi-sync'
    case 'campaign:invalidated':
      return 'pi pi-times-circle'
    case 'signal:new':
      return 'pi pi-bolt'
    case 'pattern_detected':
      return 'pi pi-chart-line'
    default:
      return 'pi pi-info-circle'
  }
}

/**
 * Get event color class based on type
 */
function getEventColorClass(type: string): string {
  switch (type) {
    case 'campaign:created':
      return 'event-created'
    case 'campaign:updated':
      return 'event-updated'
    case 'campaign:invalidated':
      return 'event-invalidated'
    case 'signal:new':
      return 'event-signal'
    case 'pattern_detected':
      return 'event-pattern'
    default:
      return 'event-default'
  }
}

/**
 * Format event message for display
 */
function formatEventMessage(
  type: string,
  data: Record<string, unknown>
): string {
  switch (type) {
    case 'campaign:created':
      return `Campaign created for ${data.symbol || 'unknown'}`
    case 'campaign:updated':
      return `Campaign ${data.campaign_id || data.symbol || 'unknown'} updated`
    case 'campaign:invalidated':
      return `Campaign ${
        data.campaign_id || data.symbol || 'unknown'
      } invalidated`
    case 'signal:new':
      return `New ${data.pattern_type || 'signal'} signal for ${
        data.symbol || 'unknown'
      }`
    case 'pattern_detected':
      return `${data.pattern_type || 'Pattern'} detected for ${
        data.symbol || 'unknown'
      }`
    default:
      return `${type} event received`
  }
}

/**
 * Add event to the feed
 */
function addEvent(type: string, data: Record<string, unknown>): void {
  const event: CampaignEvent = {
    id: `${Date.now()}-${Math.random().toString(36).substr(2, 9)}`,
    type,
    timestamp: new Date(),
    data,
    message: formatEventMessage(type, data),
  }

  events.value.unshift(event)

  // Trim to max events
  if (events.value.length > MAX_EVENTS) {
    events.value = events.value.slice(0, MAX_EVENTS)
  }

  // Auto-scroll to top if enabled
  if (autoScroll.value) {
    nextTick(() => {
      if (feedContainer.value) {
        feedContainer.value.scrollTop = 0
      }
    })
  }
}

/**
 * Handle WebSocket events
 */
function handleCampaignCreated(message: WebSocketMessage): void {
  if ('data' in message && message.data) {
    addEvent('campaign:created', message.data as Record<string, unknown>)
  }
}

function handleCampaignUpdated(message: WebSocketMessage): void {
  if ('data' in message && message.data) {
    addEvent('campaign:updated', message.data as Record<string, unknown>)
  }
}

function handleCampaignInvalidated(message: WebSocketMessage): void {
  if ('data' in message && message.data) {
    addEvent('campaign:invalidated', message.data as Record<string, unknown>)
  }
}

function handleSignalNew(message: WebSocketMessage): void {
  if ('data' in message && message.data) {
    addEvent('signal:new', message.data as Record<string, unknown>)
  }
}

function handlePatternDetected(message: WebSocketMessage): void {
  if ('data' in message && message.data) {
    addEvent('pattern_detected', message.data as Record<string, unknown>)
  }
}

/**
 * Show event detail dialog
 */
function showEventDetail(event: CampaignEvent): void {
  selectedEvent.value = event
  showDetailDialog.value = true
}

/**
 * Clear all events
 */
function clearEvents(): void {
  events.value = []
}

/**
 * Toggle auto-scroll
 */
function toggleAutoScroll(): void {
  autoScroll.value = !autoScroll.value
}

/**
 * Lifecycle: Subscribe to WebSocket events
 */
onMounted(() => {
  ws.subscribe('campaign:created', handleCampaignCreated)
  ws.subscribe('campaign:updated', handleCampaignUpdated)
  ws.subscribe('campaign:invalidated', handleCampaignInvalidated)
  ws.subscribe('signal:new', handleSignalNew)
  ws.subscribe('pattern_detected', handlePatternDetected)
})

/**
 * Lifecycle: Cleanup subscriptions
 */
onUnmounted(() => {
  ws.unsubscribe('campaign:created', handleCampaignCreated)
  ws.unsubscribe('campaign:updated', handleCampaignUpdated)
  ws.unsubscribe('campaign:invalidated', handleCampaignInvalidated)
  ws.unsubscribe('signal:new', handleSignalNew)
  ws.unsubscribe('pattern_detected', handlePatternDetected)
})

// Update relative times every minute
const updateInterval = ref<ReturnType<typeof setInterval> | null>(null)

onMounted(() => {
  updateInterval.value = setInterval(() => {
    // Force reactivity update for relative times
    events.value = [...events.value]
  }, 60000)
})

onUnmounted(() => {
  if (updateInterval.value) {
    clearInterval(updateInterval.value)
  }
})
</script>

<template>
  <div class="event-feed-panel">
    <!-- Panel Header -->
    <div class="panel-header">
      <h2 class="text-xl font-semibold text-gray-900 dark:text-gray-100">
        Event Feed
      </h2>
      <div class="header-controls">
        <Dropdown
          v-model="selectedFilter"
          :options="filterOptions"
          option-label="label"
          option-value="value"
          placeholder="Filter events"
          class="filter-dropdown"
        />
        <button
          class="control-btn"
          :class="{ active: autoScroll }"
          title="Auto-scroll to latest"
          @click="toggleAutoScroll"
        >
          <i class="pi pi-arrow-down"></i>
        </button>
        <button class="control-btn" title="Clear events" @click="clearEvents">
          <i class="pi pi-trash"></i>
        </button>
      </div>
    </div>

    <!-- Event Count Badge -->
    <div class="event-summary">
      <Badge
        v-if="filteredEvents.length > 0"
        :value="filteredEvents.length"
        severity="info"
      />
      <span class="text-sm text-gray-600 dark:text-gray-400">
        {{ filteredEvents.length }} event{{
          filteredEvents.length !== 1 ? 's' : ''
        }}
      </span>
    </div>

    <!-- Empty State -->
    <div v-if="filteredEvents.length === 0" class="empty-state">
      <i class="pi pi-inbox text-4xl text-gray-400 mb-2"></i>
      <p class="text-gray-600 dark:text-gray-400">No events yet</p>
      <p class="text-sm text-gray-500">Events will appear as they occur</p>
    </div>

    <!-- Event List -->
    <div v-else ref="feedContainer" class="event-list">
      <div
        v-for="event in filteredEvents"
        :key="event.id"
        class="event-item"
        :class="getEventColorClass(event.type)"
        @click="showEventDetail(event)"
      >
        <div class="event-icon">
          <i :class="getEventIcon(event.type)"></i>
        </div>
        <div class="event-content">
          <p class="event-message">{{ event.message }}</p>
          <span class="event-time">{{
            formatRelativeTime(event.timestamp)
          }}</span>
        </div>
        <i class="pi pi-chevron-right event-chevron"></i>
      </div>
    </div>

    <!-- Event Detail Dialog -->
    <Dialog
      v-model:visible="showDetailDialog"
      header="Event Details"
      :modal="true"
      :draggable="false"
      :style="{ width: '500px' }"
    >
      <div v-if="selectedEvent" class="event-detail">
        <div class="detail-row">
          <span class="detail-label">Type:</span>
          <span class="detail-value">{{ selectedEvent.type }}</span>
        </div>
        <div class="detail-row">
          <span class="detail-label">Time:</span>
          <span class="detail-value">{{
            selectedEvent.timestamp.toLocaleString()
          }}</span>
        </div>
        <div class="detail-row">
          <span class="detail-label">Message:</span>
          <span class="detail-value">{{ selectedEvent.message }}</span>
        </div>
        <div class="detail-section">
          <span class="detail-label">Data:</span>
          <pre class="detail-json">{{
            JSON.stringify(selectedEvent.data, null, 2)
          }}</pre>
        </div>
      </div>
    </Dialog>
  </div>
</template>

<style scoped>
.event-feed-panel {
  background: var(--surface-card);
  border-radius: 8px;
  padding: 1rem;
  height: 100%;
  display: flex;
  flex-direction: column;
}

.panel-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 0.75rem;
  padding-bottom: 0.5rem;
  border-bottom: 1px solid var(--surface-border);
}

.header-controls {
  display: flex;
  gap: 0.5rem;
  align-items: center;
}

.filter-dropdown {
  width: 160px;
}

.control-btn {
  background: transparent;
  border: 1px solid var(--surface-border);
  border-radius: 4px;
  padding: 0.5rem;
  cursor: pointer;
  color: var(--text-color);
  transition: all 0.2s;
}

.control-btn:hover {
  background: var(--surface-hover);
}

.control-btn.active {
  background: var(--primary-100);
  border-color: var(--primary-color);
  color: var(--primary-color);
}

.event-summary {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  margin-bottom: 0.75rem;
}

.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 2rem;
  flex: 1;
  text-align: center;
}

.event-list {
  flex: 1;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.event-item {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  padding: 0.75rem;
  background: var(--surface-ground);
  border-radius: 6px;
  cursor: pointer;
  transition: all 0.2s;
  border-left: 3px solid transparent;
}

.event-item:hover {
  background: var(--surface-hover);
  transform: translateX(4px);
}

.event-icon {
  width: 32px;
  height: 32px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.event-content {
  flex: 1;
  min-width: 0;
}

.event-message {
  font-size: 0.875rem;
  font-weight: 500;
  color: var(--text-color);
  margin: 0;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.event-time {
  font-size: 0.75rem;
  color: var(--text-color-secondary);
}

.event-chevron {
  color: var(--text-color-secondary);
  font-size: 0.75rem;
}

/* Event type colors */
.event-created {
  border-left-color: var(--green-500);
}

.event-created .event-icon {
  background: var(--green-100);
  color: var(--green-600);
}

.event-updated {
  border-left-color: var(--blue-500);
}

.event-updated .event-icon {
  background: var(--blue-100);
  color: var(--blue-600);
}

.event-invalidated {
  border-left-color: var(--red-500);
}

.event-invalidated .event-icon {
  background: var(--red-100);
  color: var(--red-600);
}

.event-signal {
  border-left-color: var(--yellow-500);
}

.event-signal .event-icon {
  background: var(--yellow-100);
  color: var(--yellow-700);
}

.event-pattern {
  border-left-color: var(--purple-500);
}

.event-pattern .event-icon {
  background: var(--purple-100);
  color: var(--purple-600);
}

.event-default {
  border-left-color: var(--gray-400);
}

.event-default .event-icon {
  background: var(--gray-100);
  color: var(--gray-600);
}

/* Detail dialog */
.event-detail {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}

.detail-row {
  display: flex;
  gap: 0.5rem;
}

.detail-label {
  font-weight: 600;
  color: var(--text-color-secondary);
  min-width: 80px;
}

.detail-value {
  color: var(--text-color);
}

.detail-section {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.detail-json {
  background: var(--surface-ground);
  padding: 0.75rem;
  border-radius: 4px;
  font-size: 0.75rem;
  overflow-x: auto;
  margin: 0;
}
</style>
