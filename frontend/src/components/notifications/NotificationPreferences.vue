<template>
  <div class="notification-preferences">
    <div v-if="isLoading" class="loading-state">
      <i class="pi pi-spin pi-spinner"></i>
      <p>Loading preferences...</p>
    </div>

    <div v-else class="preferences-container">
      <!-- Channel Settings -->
      <section class="section">
        <h2 class="section-title">Notification Channels</h2>
        <p class="section-description">
          Choose how you want to receive notifications
        </p>

        <div class="channel-settings">
          <!-- Email -->
          <div class="channel-card">
            <div class="channel-header">
              <div class="channel-info">
                <i class="pi pi-envelope channel-icon"></i>
                <div>
                  <h3>Email Notifications</h3>
                  <p class="channel-desc">Receive notifications via email</p>
                </div>
              </div>
              <InputSwitch
                v-model="localPreferences.email_enabled"
                @update:model-value="handleChannelToggle('email', $event)"
              />
            </div>

            <div v-if="localPreferences.email_enabled" class="channel-details">
              <InputText
                v-model="localPreferences.email_address"
                type="email"
                placeholder="your.email@example.com"
                class="w-full"
              />
              <Button
                label="Send Test Email"
                severity="secondary"
                size="small"
                :loading="testLoading.email"
                :disabled="!localPreferences.email_address"
                @click="sendTest('email')"
              />
            </div>
          </div>

          <!-- SMS -->
          <div class="channel-card">
            <div class="channel-header">
              <div class="channel-info">
                <i class="pi pi-mobile channel-icon"></i>
                <div>
                  <h3>SMS Notifications</h3>
                  <p class="channel-desc">
                    Receive critical alerts via text message
                  </p>
                </div>
              </div>
              <InputSwitch
                v-model="localPreferences.sms_enabled"
                @update:model-value="handleChannelToggle('sms', $event)"
              />
            </div>

            <div v-if="localPreferences.sms_enabled" class="channel-details">
              <InputText
                v-model="localPreferences.sms_phone_number"
                type="tel"
                placeholder="+1234567890 (E.164 format)"
                class="w-full"
              />
              <small class="text-gray-500">
                Format: +[country code][number] (e.g., +12345678901)
              </small>
              <Button
                label="Send Test SMS"
                severity="secondary"
                size="small"
                :loading="testLoading.sms"
                :disabled="!localPreferences.sms_phone_number"
                @click="sendTest('sms')"
              />
            </div>
          </div>

          <!-- Push Notifications -->
          <div class="channel-card">
            <div class="channel-header">
              <div class="channel-info">
                <i class="pi pi-bell channel-icon"></i>
                <div>
                  <h3>Push Notifications</h3>
                  <p class="channel-desc">
                    Browser notifications for real-time alerts
                  </p>
                </div>
              </div>
              <InputSwitch
                v-model="localPreferences.push_enabled"
                @update:model-value="handleChannelToggle('push', $event)"
              />
            </div>

            <div v-if="localPreferences.push_enabled" class="channel-details">
              <p class="text-sm text-gray-600">
                Push notifications are enabled. You will receive alerts in your
                browser.
              </p>
              <Button
                label="Send Test Push"
                severity="secondary"
                size="small"
                :loading="testLoading.push"
                @click="sendTest('push')"
              />
            </div>
          </div>
        </div>
      </section>

      <!-- Signal Confidence Threshold -->
      <section class="section">
        <h2 class="section-title">Signal Confidence Threshold</h2>
        <p class="section-description">
          Only notify when signal confidence is at or above this threshold
        </p>

        <div class="threshold-control">
          <div class="threshold-value">
            {{ localPreferences.min_confidence_threshold }}%
          </div>
          <Slider
            v-model="localPreferences.min_confidence_threshold"
            :min="70"
            :max="95"
            :step="1"
            class="w-full"
          />
          <div class="threshold-labels">
            <span>70% (More signals)</span>
            <span>95% (High confidence only)</span>
          </div>
        </div>
      </section>

      <!-- Quiet Hours -->
      <section class="section">
        <h2 class="section-title">Quiet Hours</h2>
        <p class="section-description">
          Pause non-critical notifications during specified hours (Critical
          alerts always override)
        </p>

        <div class="quiet-hours-settings">
          <div class="quiet-hours-toggle">
            <label>Enable Quiet Hours</label>
            <InputSwitch v-model="localPreferences.quiet_hours.enabled" />
          </div>

          <div
            v-if="localPreferences.quiet_hours.enabled"
            class="quiet-hours-details"
          >
            <div class="time-range">
              <div class="time-input">
                <label>Start Time</label>
                <InputMask
                  v-model="localPreferences.quiet_hours.start_time"
                  mask="99:99"
                  placeholder="22:00"
                />
              </div>

              <i class="pi pi-arrow-right"></i>

              <div class="time-input">
                <label>End Time</label>
                <InputMask
                  v-model="localPreferences.quiet_hours.end_time"
                  mask="99:99"
                  placeholder="08:00"
                />
              </div>
            </div>

            <div class="timezone-select">
              <label>Timezone</label>
              <Dropdown
                v-model="localPreferences.quiet_hours.timezone"
                :options="timezones"
                placeholder="Select timezone"
                class="w-full"
              />
            </div>
          </div>
        </div>
      </section>

      <!-- Priority Channel Routing -->
      <section class="section">
        <h2 class="section-title">Channel Routing by Priority</h2>
        <p class="section-description">
          Configure which channels to use for each notification priority level
        </p>

        <div class="priority-routing">
          <!-- INFO -->
          <div class="priority-card">
            <div class="priority-header">
              <i class="pi pi-info-circle priority-icon info"></i>
              <h3>Info</h3>
            </div>
            <div class="channel-checkboxes">
              <div
                v-for="channel in availableChannels"
                :key="`info-${channel.value}`"
                class="channel-checkbox"
              >
                <Checkbox
                  v-model="localPreferences.channel_preferences.info_channels"
                  :value="channel.value"
                  :input-id="`info-${channel.value}`"
                />
                <label :for="`info-${channel.value}`">
                  {{ channel.label }}
                </label>
              </div>
            </div>
          </div>

          <!-- WARNING -->
          <div class="priority-card">
            <div class="priority-header">
              <i class="pi pi-exclamation-triangle priority-icon warning"></i>
              <h3>Warning</h3>
            </div>
            <div class="channel-checkboxes">
              <div
                v-for="channel in availableChannels"
                :key="`warning-${channel.value}`"
                class="channel-checkbox"
              >
                <Checkbox
                  v-model="
                    localPreferences.channel_preferences.warning_channels
                  "
                  :value="channel.value"
                  :input-id="`warning-${channel.value}`"
                />
                <label :for="`warning-${channel.value}`">
                  {{ channel.label }}
                </label>
              </div>
            </div>
          </div>

          <!-- CRITICAL -->
          <div class="priority-card">
            <div class="priority-header">
              <i class="pi pi-times-circle priority-icon critical"></i>
              <h3>Critical</h3>
            </div>
            <div class="channel-checkboxes">
              <div
                v-for="channel in availableChannels"
                :key="`critical-${channel.value}`"
                class="channel-checkbox"
              >
                <Checkbox
                  v-model="
                    localPreferences.channel_preferences.critical_channels
                  "
                  :value="channel.value"
                  :input-id="`critical-${channel.value}`"
                />
                <label :for="`critical-${channel.value}`">
                  {{ channel.label }}
                </label>
              </div>
            </div>
          </div>
        </div>
      </section>

      <!-- Save Button -->
      <div class="actions">
        <Button
          label="Save Preferences"
          icon="pi pi-check"
          :loading="isSaving"
          @click="savePreferences"
        />
        <Button
          label="Reset to Defaults"
          severity="secondary"
          icon="pi pi-refresh"
          @click="resetToDefaults"
        />
      </div>

      <!-- Success/Error Messages -->
      <Message
        v-if="successMessage"
        severity="success"
        :closable="true"
        @close="successMessage = ''"
      >
        {{ successMessage }}
      </Message>
      <Message
        v-if="errorMessage"
        severity="error"
        :closable="true"
        @close="errorMessage = ''"
      >
        {{ errorMessage }}
      </Message>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useNotificationStore } from '@/stores/notificationStore'
import { usePushNotifications } from '@/composables/usePushNotifications'
import type { NotificationPreferences } from '@/types/notification'
import { NotificationChannel } from '@/types/notification'
import InputSwitch from 'primevue/inputswitch'
import InputText from 'primevue/inputtext'
import InputMask from 'primevue/inputmask'
import Slider from 'primevue/slider'
import Dropdown from 'primevue/dropdown'
import Checkbox from 'primevue/checkbox'
import Button from 'primevue/button'
import Message from 'primevue/message'

const notificationStore = useNotificationStore()
const pushNotifications = usePushNotifications()

// State
const isLoading = ref(false)
const isSaving = ref(false)
const successMessage = ref('')
const errorMessage = ref('')
const testLoading = ref({
  email: false,
  sms: false,
  push: false,
})

const localPreferences = ref<NotificationPreferences>({
  user_id: '',
  email_enabled: true,
  email_address: '',
  sms_enabled: false,
  sms_phone_number: '',
  push_enabled: false,
  min_confidence_threshold: 85,
  quiet_hours: {
    enabled: false,
    start_time: '22:00',
    end_time: '08:00',
    timezone: 'America/New_York',
  },
  channel_preferences: {
    info_channels: [NotificationChannel.TOAST],
    warning_channels: [NotificationChannel.TOAST, NotificationChannel.EMAIL],
    critical_channels: [
      NotificationChannel.TOAST,
      NotificationChannel.EMAIL,
      NotificationChannel.SMS,
      NotificationChannel.PUSH,
    ],
  },
  updated_at: new Date().toISOString(),
})

// Constants
const availableChannels = [
  { label: 'Toast', value: 'toast' },
  { label: 'Email', value: 'email' },
  { label: 'SMS', value: 'sms' },
  { label: 'Push', value: 'push' },
]

const timezones = [
  'America/New_York',
  'America/Chicago',
  'America/Denver',
  'America/Los_Angeles',
  'America/Anchorage',
  'Pacific/Honolulu',
  'UTC',
  'Europe/London',
  'Europe/Paris',
  'Asia/Tokyo',
  'Asia/Shanghai',
  'Australia/Sydney',
]

// Methods
async function loadPreferences() {
  isLoading.value = true
  try {
    await notificationStore.fetchPreferences()
    if (notificationStore.preferences) {
      localPreferences.value = { ...notificationStore.preferences }
    }
  } catch (err: unknown) {
    errorMessage.value = 'Failed to load preferences'
    console.error('Error loading preferences:', err)
  } finally {
    isLoading.value = false
  }
}

async function savePreferences() {
  isSaving.value = true
  successMessage.value = ''
  errorMessage.value = ''

  try {
    await notificationStore.updatePreferences(localPreferences.value)
    successMessage.value = 'Preferences saved successfully!'

    // Clear success message after 3 seconds
    setTimeout(() => {
      successMessage.value = ''
    }, 3000)
  } catch (err: unknown) {
    errorMessage.value = err.message || 'Failed to save preferences'
  } finally {
    isSaving.value = false
  }
}

async function sendTest(channel: 'email' | 'sms' | 'push') {
  testLoading.value[channel] = true
  successMessage.value = ''
  errorMessage.value = ''

  try {
    await notificationStore.sendTestNotification(channel)
    successMessage.value = `Test ${channel} sent successfully! Check your ${channel}.`

    setTimeout(() => {
      successMessage.value = ''
    }, 3000)
  } catch (err: unknown) {
    errorMessage.value =
      err.response?.data?.detail ||
      err.message ||
      `Failed to send test ${channel}`
  } finally {
    testLoading.value[channel] = false
  }
}

async function handleChannelToggle(channel: string, enabled: boolean) {
  // Auto-clear contact info when channel disabled
  if (!enabled) {
    if (channel === 'email') {
      localPreferences.value.email_address = ''
    } else if (channel === 'sms') {
      localPreferences.value.sms_phone_number = ''
    } else if (channel === 'push') {
      // Unsubscribe from push notifications
      try {
        await pushNotifications.unsubscribe()
      } catch (err) {
        console.error('Failed to unsubscribe from push:', err)
      }
    }
  } else if (channel === 'push' && enabled) {
    // Subscribe to push notifications
    try {
      // VAPID public key should be loaded from backend config
      // For now, using placeholder - implement backend endpoint to fetch this
      const vapidPublicKey = import.meta.env.VITE_VAPID_PUBLIC_KEY || ''

      if (!vapidPublicKey) {
        errorMessage.value =
          'Push notifications not configured. Contact administrator.'
        localPreferences.value.push_enabled = false
        return
      }

      await pushNotifications.subscribe(vapidPublicKey)
      successMessage.value = 'Successfully subscribed to push notifications!'
      setTimeout(() => {
        successMessage.value = ''
      }, 3000)
    } catch (err: unknown) {
      errorMessage.value =
        err.message || 'Failed to subscribe to push notifications'
      localPreferences.value.push_enabled = false
    }
  }
}

function resetToDefaults() {
  localPreferences.value = {
    user_id: localPreferences.value.user_id,
    email_enabled: true,
    email_address: '',
    sms_enabled: false,
    sms_phone_number: '',
    push_enabled: false,
    min_confidence_threshold: 85,
    quiet_hours: {
      enabled: false,
      start_time: '22:00',
      end_time: '08:00',
      timezone: 'America/New_York',
    },
    channel_preferences: {
      info_channels: [NotificationChannel.TOAST],
      warning_channels: [NotificationChannel.TOAST, NotificationChannel.EMAIL],
      critical_channels: [
        NotificationChannel.TOAST,
        NotificationChannel.EMAIL,
        NotificationChannel.SMS,
        NotificationChannel.PUSH,
      ],
    },
    updated_at: new Date().toISOString(),
  }
}

onMounted(async () => {
  loadPreferences()

  // Check push notification subscription status
  await pushNotifications.checkSubscriptionStatus()
})
</script>

<style scoped>
.notification-preferences {
  max-width: 800px;
  margin: 0 auto;
}

.loading-state {
  text-align: center;
  padding: 60px 20px;
  color: #64748b;
}

.loading-state i {
  font-size: 48px;
  margin-bottom: 16px;
}

.preferences-container {
  display: flex;
  flex-direction: column;
  gap: 32px;
}

.section {
  background: white;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  padding: 24px;
}

.section-title {
  font-size: 18px;
  font-weight: 600;
  color: #1e293b;
  margin: 0 0 8px 0;
}

.section-description {
  color: #64748b;
  font-size: 14px;
  margin: 0 0 24px 0;
}

/* Channel Settings */
.channel-settings {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.channel-card {
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  padding: 16px;
  background: #f8fafc;
}

.channel-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.channel-info {
  display: flex;
  gap: 12px;
  align-items: center;
}

.channel-icon {
  font-size: 24px;
  color: #3b82f6;
}

.channel-card h3 {
  font-size: 16px;
  font-weight: 600;
  color: #1e293b;
  margin: 0;
}

.channel-desc {
  color: #64748b;
  font-size: 13px;
  margin: 4px 0 0 0;
}

.channel-details {
  margin-top: 16px;
  padding-top: 16px;
  border-top: 1px solid #e2e8f0;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

/* Threshold Control */
.threshold-control {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.threshold-value {
  font-size: 32px;
  font-weight: 700;
  color: #3b82f6;
  text-align: center;
}

.threshold-labels {
  display: flex;
  justify-content: space-between;
  font-size: 12px;
  color: #94a3b8;
}

/* Quiet Hours */
.quiet-hours-settings {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.quiet-hours-toggle {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px;
  background: #f8fafc;
  border-radius: 6px;
}

.quiet-hours-toggle label {
  font-weight: 500;
  color: #1e293b;
}

.quiet-hours-details {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.time-range {
  display: flex;
  align-items: center;
  gap: 16px;
}

.time-input {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.time-input label {
  font-size: 14px;
  font-weight: 500;
  color: #475569;
}

.timezone-select {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.timezone-select label {
  font-size: 14px;
  font-weight: 500;
  color: #475569;
}

/* Priority Routing */
.priority-routing {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
  gap: 16px;
}

.priority-card {
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  padding: 16px;
  background: #f8fafc;
}

.priority-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 16px;
}

.priority-header h3 {
  font-size: 15px;
  font-weight: 600;
  color: #1e293b;
  margin: 0;
}

.priority-icon {
  font-size: 20px;
}

.priority-icon.info {
  color: #3b82f6;
}

.priority-icon.warning {
  color: #f59e0b;
}

.priority-icon.critical {
  color: #ef4444;
}

.channel-checkboxes {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.channel-checkbox {
  display: flex;
  align-items: center;
  gap: 8px;
}

.channel-checkbox label {
  font-size: 14px;
  color: #475569;
  cursor: pointer;
}

/* Actions */
.actions {
  display: flex;
  gap: 12px;
  padding-top: 8px;
}
</style>
