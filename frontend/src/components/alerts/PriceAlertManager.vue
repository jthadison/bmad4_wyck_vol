<template>
  <div class="price-alert-manager">
    <!-- Header -->
    <div class="manager-header">
      <h2 class="manager-title">Price Alerts</h2>
      <p class="manager-subtitle">
        Set Wyckoff-specific alerts for Creek breakouts, Ice retests, Spring
        shakeouts, and custom price levels.
      </p>
    </div>

    <!-- Create Alert Form -->
    <div class="alert-form-card">
      <h3 class="form-title">Create New Alert</h3>

      <div class="form-grid">
        <!-- Symbol -->
        <div class="form-field">
          <label for="alert-symbol">Symbol</label>
          <InputText
            id="alert-symbol"
            v-model="form.symbol"
            placeholder="e.g. AAPL"
            class="w-full uppercase-input"
            :class="{ 'p-invalid': formErrors.symbol }"
            @input="
              form.symbol = (
                $event.target as HTMLInputElement
              ).value.toUpperCase()
            "
          />
          <small v-if="formErrors.symbol" class="field-error">
            {{ formErrors.symbol }}
          </small>
        </div>

        <!-- Alert Type -->
        <div class="form-field">
          <label for="alert-type">Alert Type</label>
          <Dropdown
            id="alert-type"
            v-model="form.alert_type"
            :options="alertTypeOptions"
            option-label="label"
            option-value="value"
            placeholder="Select type"
            class="w-full"
          />
          <small class="field-hint">{{ alertTypeHint }}</small>
        </div>

        <!-- Price Level (shown for non-phase_change types) -->
        <div v-if="form.alert_type !== 'phase_change'" class="form-field">
          <label for="alert-price">Price Level</label>
          <InputNumber
            id="alert-price"
            v-model="form.price_level"
            :min="0"
            :max-fraction-digits="4"
            placeholder="e.g. 150.00"
            class="w-full"
            :class="{ 'p-invalid': formErrors.price_level }"
          />
          <small v-if="formErrors.price_level" class="field-error">
            {{ formErrors.price_level }}
          </small>
        </div>

        <!-- Direction (only for price_level type) -->
        <div v-if="form.alert_type === 'price_level'" class="form-field">
          <label for="alert-direction">Direction</label>
          <Dropdown
            id="alert-direction"
            v-model="form.direction"
            :options="directionOptions"
            option-label="label"
            option-value="value"
            placeholder="Above / Below"
            class="w-full"
            :class="{ 'p-invalid': formErrors.direction }"
          />
          <small v-if="formErrors.direction" class="field-error">
            {{ formErrors.direction }}
          </small>
        </div>

        <!-- Wyckoff Level Type (optional context) -->
        <div v-if="showWyckoffLevelType" class="form-field">
          <label for="alert-wyckoff">Wyckoff Level (optional)</label>
          <Dropdown
            id="alert-wyckoff"
            v-model="form.wyckoff_level_type"
            :options="wyckoffLevelOptions"
            option-label="label"
            option-value="value"
            placeholder="Select level type"
            class="w-full"
          />
        </div>

        <!-- Notes -->
        <div class="form-field form-field-full">
          <label for="alert-notes">Notes (optional)</label>
          <InputText
            id="alert-notes"
            v-model="form.notes"
            placeholder="e.g. Creek resistance at prior swing high"
            class="w-full"
            :maxlength="500"
          />
        </div>
      </div>

      <!-- Form Actions -->
      <div class="form-actions">
        <Button
          label="Create Alert"
          icon="pi pi-bell"
          :loading="store.isSaving"
          :disabled="store.isSaving"
          @click="handleCreate"
        />
        <Button
          label="Clear"
          severity="secondary"
          icon="pi pi-times"
          @click="resetForm"
        />
      </div>

      <!-- Feedback Messages -->
      <Message
        v-if="successMessage"
        severity="success"
        :closable="true"
        class="mt-3"
        @close="successMessage = ''"
      >
        {{ successMessage }}
      </Message>
      <Message
        v-if="store.error"
        severity="error"
        :closable="true"
        class="mt-3"
        @close="store.error = null"
      >
        {{ store.error }}
      </Message>
    </div>

    <!-- Active Alerts List -->
    <div class="alerts-list-section">
      <div class="list-header">
        <h3 class="list-title">
          Your Alerts
          <span class="count-badge">{{ store.totalCount }}</span>
        </h3>
        <div class="list-meta">
          <span class="active-count">{{ store.activeCount }} active</span>
        </div>
      </div>

      <!-- Loading State -->
      <div v-if="store.isLoading" class="loading-state">
        <i class="pi pi-spin pi-spinner"></i>
        <span>Loading alerts...</span>
      </div>

      <!-- Empty State -->
      <div v-else-if="store.alerts.length === 0" class="empty-state">
        <i class="pi pi-bell-slash empty-icon"></i>
        <p>No price alerts set. Create your first alert above.</p>
      </div>

      <!-- Alert Rows -->
      <div v-else class="alerts-list">
        <div
          v-for="alert in store.alerts"
          :key="alert.id"
          :class="['alert-row', { 'alert-row--inactive': !alert.is_active }]"
        >
          <!-- Left: Alert Info -->
          <div class="alert-info">
            <div class="alert-primary">
              <span class="alert-symbol">{{ alert.symbol }}</span>
              <span :class="['type-badge', `type-badge--${alert.alert_type}`]">
                {{ alertTypeLabel(alert.alert_type) }}
              </span>
              <span
                v-if="alert.is_active && !alert.triggered_at"
                class="status-badge status-badge--active"
              >
                Active
              </span>
              <span
                v-else-if="alert.triggered_at"
                class="status-badge status-badge--triggered"
              >
                Triggered
              </span>
              <span v-else class="status-badge status-badge--paused"
                >Paused</span
              >
            </div>

            <div class="alert-secondary">
              <span v-if="alert.price_level !== null" class="alert-detail">
                {{ directionLabel(alert.direction) }}
                <strong>${{ formatPrice(alert.price_level) }}</strong>
              </span>
              <span
                v-if="alert.wyckoff_level_type"
                class="alert-detail wyckoff-level"
              >
                {{ wyckoffLabel(alert.wyckoff_level_type) }}
              </span>
              <span v-if="alert.notes" class="alert-notes">
                {{ alert.notes }}
              </span>
            </div>
          </div>

          <!-- Right: Actions -->
          <div class="alert-actions">
            <Button
              :icon="alert.is_active ? 'pi pi-pause' : 'pi pi-play'"
              severity="secondary"
              size="small"
              :title="alert.is_active ? 'Pause alert' : 'Resume alert'"
              :loading="togglingId === alert.id"
              @click="handleToggle(alert)"
            />
            <Button
              icon="pi pi-trash"
              severity="danger"
              size="small"
              title="Delete alert"
              :loading="deletingId === alert.id"
              @click="handleDelete(alert.id)"
            />
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import Button from 'primevue/button'
import Dropdown from 'primevue/dropdown'
import InputText from 'primevue/inputtext'
import InputNumber from 'primevue/inputnumber'
import Message from 'primevue/message'
import { usePriceAlertsStore } from '@/stores/priceAlerts'
import type {
  AlertDirection,
  AlertType,
  PriceAlert,
  WyckoffLevelType,
} from '@/services/priceAlertService'

// -------------------------------------------------------------------------
// Store
// -------------------------------------------------------------------------
const store = usePriceAlertsStore()

// -------------------------------------------------------------------------
// Form state
// -------------------------------------------------------------------------
interface AlertForm {
  symbol: string
  alert_type: AlertType
  price_level: number | null
  direction: AlertDirection | null
  wyckoff_level_type: WyckoffLevelType | null
  notes: string
}

const defaultForm = (): AlertForm => ({
  symbol: '',
  alert_type: 'price_level',
  price_level: null,
  direction: null,
  wyckoff_level_type: null,
  notes: '',
})

const form = ref<AlertForm>(defaultForm())
const formErrors = ref<Partial<Record<keyof AlertForm, string>>>({})
const successMessage = ref('')
const togglingId = ref<string | null>(null)
const deletingId = ref<string | null>(null)

// -------------------------------------------------------------------------
// Dropdown options
// -------------------------------------------------------------------------
const alertTypeOptions = [
  {
    label: 'Price Level - Custom price crossing',
    value: 'price_level',
  },
  {
    label: 'Creek Breakout (SOS) - Price breaks above Creek/Ice resistance',
    value: 'creek',
  },
  {
    label: 'Ice Retest (LPS) - Price tests Ice from above',
    value: 'ice',
  },
  {
    label: 'Spring Alert (Phase C) - Price dips below Spring support',
    value: 'spring',
  },
  {
    label: 'Phase Change - Wyckoff phase changes for symbol',
    value: 'phase_change',
  },
]

const directionOptions = [
  { label: 'Above (breakout / upside crossing)', value: 'above' },
  { label: 'Below (breakdown / downside crossing)', value: 'below' },
]

const wyckoffLevelOptions = [
  { label: 'Creek (resistance above accumulation)', value: 'creek' },
  { label: 'Ice (support after distribution)', value: 'ice' },
  { label: 'Spring (below-support shakeout)', value: 'spring' },
  { label: 'Supply Zone', value: 'supply' },
  { label: 'Demand Zone', value: 'demand' },
]

// -------------------------------------------------------------------------
// Computed
// -------------------------------------------------------------------------
const showWyckoffLevelType = computed(() =>
  ['creek', 'ice', 'spring'].includes(form.value.alert_type)
)

const alertTypeHint = computed((): string => {
  const hints: Record<AlertType, string> = {
    price_level: 'Trigger when price crosses your custom level.',
    creek: 'SOS signal: price breaks above Creek/Ice resistance (Phase D).',
    ice: 'LPS signal: price retests Ice support from above (Phase E).',
    spring: 'Phase C: shakeout below support - look for low-volume test.',
    phase_change:
      'Alert when the detected Wyckoff phase changes for this symbol.',
  }
  const type = form.value.alert_type as AlertType
  return hints[type] ?? ''
})

// -------------------------------------------------------------------------
// Helpers
// -------------------------------------------------------------------------
function alertTypeLabel(type: AlertType): string {
  const labels: Record<AlertType, string> = {
    price_level: 'Price Level',
    creek: 'Creek (SOS)',
    ice: 'Ice (LPS)',
    spring: 'Spring',
    phase_change: 'Phase Change',
  }
  return labels[type] ?? type
}

function directionLabel(dir: AlertDirection | null): string {
  if (!dir) return ''
  return dir === 'above' ? 'Above' : 'Below'
}

function wyckoffLabel(level: WyckoffLevelType | null): string {
  if (!level) return ''
  const labels: Record<WyckoffLevelType, string> = {
    creek: 'Creek',
    ice: 'Ice',
    spring: 'Spring',
    supply: 'Supply Zone',
    demand: 'Demand Zone',
  }
  return labels[level] ?? level
}

function formatPrice(price: number | null): string {
  if (price === null) return '-'
  return price.toLocaleString('en-US', {
    minimumFractionDigits: 2,
    maximumFractionDigits: 4,
  })
}

// -------------------------------------------------------------------------
// Validation
// -------------------------------------------------------------------------
function validate(): boolean {
  const errors: Partial<Record<keyof AlertForm, string>> = {}

  if (!form.value.symbol.trim()) {
    errors.symbol = 'Symbol is required'
  }

  const needsPrice = form.value.alert_type !== 'phase_change'
  if (needsPrice && form.value.price_level === null) {
    errors.price_level = 'Price level is required for this alert type'
  }

  if (form.value.alert_type === 'price_level' && !form.value.direction) {
    errors.direction = 'Direction (above/below) is required'
  }

  formErrors.value = errors
  return Object.keys(errors).length === 0
}

// -------------------------------------------------------------------------
// Event handlers
// -------------------------------------------------------------------------
async function handleCreate() {
  if (!validate()) return

  const created = await store.createAlert({
    symbol: form.value.symbol,
    alert_type: form.value.alert_type,
    price_level: form.value.price_level,
    direction: form.value.direction,
    wyckoff_level_type: form.value.wyckoff_level_type ?? undefined,
    notes: form.value.notes || null,
  })

  if (created) {
    successMessage.value = `Alert created for ${
      created.symbol
    } (${alertTypeLabel(created.alert_type)})`
    resetForm()
    setTimeout(() => {
      successMessage.value = ''
    }, 4000)
  }
}

async function handleToggle(alert: PriceAlert) {
  togglingId.value = alert.id
  await store.toggleAlert(alert.id)
  togglingId.value = null
}

async function handleDelete(id: string) {
  deletingId.value = id
  await store.deleteAlert(id)
  deletingId.value = null
}

function resetForm() {
  form.value = defaultForm()
  formErrors.value = {}
}

// -------------------------------------------------------------------------
// Lifecycle
// -------------------------------------------------------------------------
onMounted(async () => {
  await store.fetchAlerts()
})
</script>

<style scoped>
.price-alert-manager {
  display: flex;
  flex-direction: column;
  gap: 28px;
  max-width: 900px;
}

/* Header */
.manager-header {
  margin-bottom: 4px;
}

.manager-title {
  font-size: 22px;
  font-weight: 700;
  color: #1e293b;
  margin: 0 0 6px 0;
}

.manager-subtitle {
  color: #64748b;
  font-size: 14px;
  margin: 0;
}

/* Form Card */
.alert-form-card {
  background: white;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  padding: 24px;
}

.form-title {
  font-size: 16px;
  font-weight: 600;
  color: #1e293b;
  margin: 0 0 20px 0;
}

.form-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 16px;
}

.form-field {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.form-field label {
  font-size: 13px;
  font-weight: 500;
  color: #475569;
}

.form-field-full {
  grid-column: 1 / -1;
}

.field-error {
  color: #ef4444;
  font-size: 12px;
}

.field-hint {
  color: #64748b;
  font-size: 12px;
  font-style: italic;
}

.form-actions {
  display: flex;
  gap: 12px;
  margin-top: 20px;
}

/* Alerts List */
.alerts-list-section {
  background: white;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  padding: 20px;
}

.list-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
}

.list-title {
  font-size: 16px;
  font-weight: 600;
  color: #1e293b;
  margin: 0;
  display: flex;
  align-items: center;
  gap: 8px;
}

.count-badge {
  background: #f1f5f9;
  color: #475569;
  font-size: 12px;
  font-weight: 600;
  padding: 2px 8px;
  border-radius: 12px;
}

.active-count {
  font-size: 13px;
  color: #16a34a;
  font-weight: 500;
}

/* Loading / Empty */
.loading-state {
  display: flex;
  align-items: center;
  gap: 10px;
  color: #64748b;
  padding: 32px;
  justify-content: center;
}

.empty-state {
  text-align: center;
  padding: 48px 20px;
  color: #94a3b8;
}

.empty-icon {
  font-size: 48px;
  margin-bottom: 12px;
  display: block;
  opacity: 0.5;
}

/* Alert Row */
.alerts-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.alert-row {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  background: #f8fafc;
  border: 1px solid #e2e8f0;
  border-radius: 6px;
  padding: 14px 16px;
  transition: opacity 0.2s;
}

.alert-row--inactive {
  opacity: 0.6;
}

.alert-info {
  flex: 1;
  min-width: 0;
}

.alert-primary {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
  margin-bottom: 6px;
}

.alert-symbol {
  font-size: 15px;
  font-weight: 700;
  color: #1e293b;
}

/* Alert Type Badges */
.type-badge {
  font-size: 11px;
  font-weight: 600;
  padding: 2px 8px;
  border-radius: 4px;
  text-transform: uppercase;
  letter-spacing: 0.04em;
}

.type-badge--price_level {
  background: #dbeafe;
  color: #1d4ed8;
}

.type-badge--creek {
  background: #d1fae5;
  color: #065f46;
}

.type-badge--ice {
  background: #e0f2fe;
  color: #0369a1;
}

.type-badge--spring {
  background: #fef9c3;
  color: #854d0e;
}

.type-badge--phase_change {
  background: #fce7f3;
  color: #9d174d;
}

/* Status Badges */
.status-badge {
  font-size: 11px;
  font-weight: 500;
  padding: 2px 8px;
  border-radius: 12px;
}

.status-badge--active {
  background: #dcfce7;
  color: #16a34a;
}

.status-badge--triggered {
  background: #e0f2fe;
  color: #0369a1;
}

.status-badge--paused {
  background: #f1f5f9;
  color: #64748b;
}

/* Alert secondary info */
.alert-secondary {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
}

.alert-detail {
  font-size: 13px;
  color: #475569;
}

.wyckoff-level {
  background: #f3f4f6;
  padding: 1px 6px;
  border-radius: 3px;
  font-size: 12px;
  color: #6b7280;
}

.alert-notes {
  font-size: 12px;
  color: #94a3b8;
  font-style: italic;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  max-width: 280px;
}

/* Row Actions */
.alert-actions {
  display: flex;
  gap: 8px;
  margin-left: 16px;
  flex-shrink: 0;
}
</style>
