<template>
  <div class="backtest-view">
    <div class="header">
      <h1 class="text-3xl font-bold">Backtesting</h1>
      <p class="text-gray-400">
        Test your trading strategies against historical market data
      </p>
    </div>

    <!-- Configuration Form -->
    <div class="config-section">
      <h2 class="text-2xl font-semibold mb-4">Backtest Configuration</h2>

      <div class="config-form">
        <div class="form-grid">
          <!-- Symbol Selection -->
          <div class="form-field">
            <label for="symbol" class="form-label">Symbol</label>
            <input
              id="symbol"
              v-model="config.symbol"
              type="text"
              placeholder="AAPL"
              class="form-input"
            />
            <small class="form-help">
              Stock symbol to backtest (e.g., AAPL, TSLA, SPY)
            </small>
          </div>

          <!-- Timeframe Selection -->
          <div class="form-field">
            <label for="timeframe" class="form-label">Timeframe</label>
            <select
              id="timeframe"
              v-model="config.timeframe"
              class="form-input"
            >
              <option value="1d">Daily (1d)</option>
              <option value="4h">4-Hour (4h)</option>
              <option value="1h">1-Hour (1h)</option>
              <option value="30m">30-Minute (30m)</option>
              <option value="15m">15-Minute (15m)</option>
            </select>
            <small class="form-help">Bar timeframe for analysis</small>
          </div>

          <!-- Lookback Days -->
          <div class="form-field">
            <label for="days" class="form-label">Lookback Days</label>
            <input
              id="days"
              v-model.number="config.days"
              type="number"
              min="30"
              max="730"
              class="form-input"
            />
            <small class="form-help">
              Number of days to backtest (30-730)
            </small>
          </div>

          <!-- Initial Capital -->
          <div class="form-field">
            <label for="initial-capital" class="form-label"
              >Initial Capital</label
            >
            <input
              id="initial-capital"
              v-model.number="config.initial_capital"
              type="number"
              min="10000"
              step="1000"
              class="form-input"
            />
            <small class="form-help">Starting capital ($)</small>
          </div>

          <!-- Max Position Size -->
          <div class="form-field">
            <label for="max-position-size" class="form-label"
              >Max Position Size (%)</label
            >
            <input
              id="max-position-size"
              v-model.number="config.max_position_size"
              type="number"
              min="1"
              max="100"
              step="1"
              class="form-input"
            />
            <small class="form-help">
              Maximum position size as % of capital (1-100)
            </small>
          </div>

          <!-- Commission Per Trade -->
          <div class="form-field">
            <label for="commission" class="form-label"
              >Commission Per Trade ($)</label
            >
            <input
              id="commission"
              v-model.number="config.commission_per_trade"
              type="number"
              min="0"
              step="0.5"
              class="form-input"
            />
            <small class="form-help">Trading commission per trade</small>
          </div>
        </div>

        <!-- Advanced Options (Collapsed) -->
        <div class="advanced-section">
          <button
            type="button"
            class="advanced-toggle"
            @click="showAdvanced = !showAdvanced"
          >
            <i
              :class="
                showAdvanced ? 'pi pi-chevron-down' : 'pi pi-chevron-right'
              "
            ></i>
            Advanced Options
          </button>

          <div v-if="showAdvanced" class="advanced-options">
            <div class="form-grid">
              <div class="form-field">
                <label for="slippage" class="form-label">Slippage (%)</label>
                <input
                  id="slippage"
                  v-model.number="config.slippage_pct"
                  type="number"
                  min="0"
                  max="5"
                  step="0.1"
                  class="form-input"
                />
                <small class="form-help">Expected slippage percentage</small>
              </div>

              <div class="form-field">
                <label for="max-heat" class="form-label"
                  >Max Portfolio Heat (%)</label
                >
                <input
                  id="max-heat"
                  v-model.number="config.max_portfolio_heat"
                  type="number"
                  min="1"
                  max="50"
                  step="1"
                  class="form-input"
                />
                <small class="form-help">
                  Maximum total risk exposure (1-50%)
                </small>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- Backtest Preview Component -->
    <div class="preview-section">
      <BacktestPreview
        :proposed-config="proposedConfig"
        :days="config.days"
        :symbol="config.symbol"
        :timeframe="config.timeframe"
      />
    </div>

    <!-- Quick Links to Results -->
    <div class="quick-links">
      <h3 class="text-xl font-semibold mb-3">Previous Results</h3>
      <router-link to="/backtest/results" class="view-results-link">
        <i class="pi pi-history"></i>
        View All Backtest Results
      </router-link>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import BacktestPreview from '@/components/configuration/BacktestPreview.vue'

// Configuration state
const config = ref({
  symbol: 'AAPL',
  timeframe: '1d',
  days: 90,
  initial_capital: 100000,
  max_position_size: 10,
  commission_per_trade: 1.0,
  slippage_pct: 0.1,
  max_portfolio_heat: 15,
})

const showAdvanced = ref(false)

// Proposed config for backtest preview
const proposedConfig = computed(() => ({
  initial_capital: config.value.initial_capital,
  max_position_size_pct: config.value.max_position_size / 100,
  commission_per_trade: config.value.commission_per_trade,
  slippage_pct: config.value.slippage_pct / 100,
  max_portfolio_heat_pct: config.value.max_portfolio_heat / 100,
  // Add any other risk/pattern detection configs here
  enable_spring_detection: true,
  enable_sos_detection: true,
  enable_lps_detection: true,
  min_pattern_confidence: 70,
}))
</script>

<style scoped>
.backtest-view {
  max-width: 1400px;
  margin: 0 auto;
  padding: 2rem;
}

.header {
  margin-bottom: 2rem;
}

.header h1 {
  margin-bottom: 0.5rem;
}

.header p {
  font-size: 1.125rem;
}

.config-section {
  background: var(--surface-card);
  border-radius: 8px;
  padding: 2rem;
  margin-bottom: 2rem;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
}

.config-section h2 {
  color: var(--text-color);
  margin-bottom: 1.5rem;
}

.config-form .form-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
  gap: 1.5rem;
  margin-bottom: 1.5rem;
}

.config-form .form-field {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.config-form .form-field .form-label {
  font-weight: 600;
  color: var(--text-color);
  font-size: 0.875rem;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.config-form .form-field .form-input {
  padding: 0.75rem;
  border: 1px solid var(--surface-border);
  border-radius: 6px;
  background: var(--surface-ground);
  color: var(--text-color);
  font-size: 1rem;
  transition: all 0.2s;
}

.config-form .form-field .form-input:focus {
  outline: none;
  border-color: var(--primary-color);
  box-shadow: 0 0 0 3px rgba(var(--primary-color-rgb), 0.1);
}

.config-form .form-field .form-input::placeholder {
  color: var(--text-color-secondary);
}

.config-form .form-field .form-help {
  font-size: 0.875rem;
  color: var(--text-color-secondary);
}

.advanced-section {
  margin-top: 1.5rem;
  padding-top: 1.5rem;
  border-top: 1px solid var(--surface-border);
}

.advanced-section .advanced-toggle {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  background: none;
  border: none;
  color: var(--primary-color);
  font-weight: 600;
  cursor: pointer;
  padding: 0.5rem 0;
  font-size: 1rem;
  transition: opacity 0.2s;
}

.advanced-section .advanced-toggle:hover {
  opacity: 0.8;
}

.advanced-section .advanced-toggle i {
  font-size: 0.875rem;
}

.advanced-section .advanced-options {
  margin-top: 1.5rem;
}

.preview-section {
  margin-bottom: 2rem;
}

.quick-links {
  background: var(--surface-card);
  border-radius: 8px;
  padding: 1.5rem 2rem;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
}

.quick-links h3 {
  color: var(--text-color);
}

.quick-links .view-results-link {
  display: inline-flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.75rem 1.5rem;
  background: var(--primary-color);
  color: white;
  text-decoration: none;
  border-radius: 6px;
  font-weight: 600;
  transition: all 0.2s;
}

.quick-links .view-results-link:hover {
  background: var(--primary-color-dark, var(--primary-color));
  transform: translateY(-1px);
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
}

.quick-links .view-results-link i {
  font-size: 1.125rem;
}

@media (max-width: 768px) {
  .backtest-view {
    padding: 1rem;
  }

  .config-section,
  .quick-links {
    padding: 1.5rem;
  }

  .config-form .form-grid {
    grid-template-columns: 1fr;
  }
}
</style>
