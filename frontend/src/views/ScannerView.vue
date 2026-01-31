<script setup lang="ts">
/**
 * ScannerView (Story 20.6)
 *
 * Main view for scanner control and watchlist management.
 * Combines ScannerControlWidget and WatchlistManager components.
 */

import ScannerControlWidget from '@/components/scanner/ScannerControlWidget.vue'
import WatchlistManager from '@/components/scanner/WatchlistManager.vue'
</script>

<template>
  <div class="scanner-view">
    <header class="page-header">
      <h1>Signal Scanner</h1>
      <p class="page-description">
        Configure and control the background scanner to detect Wyckoff patterns
      </p>
    </header>

    <div class="scanner-layout">
      <!-- Scanner Control Section -->
      <section class="control-section">
        <ScannerControlWidget />
      </section>

      <!-- Watchlist Management Section -->
      <section class="watchlist-section">
        <WatchlistManager />
      </section>
    </div>
  </div>
</template>

<style scoped>
.scanner-view {
  max-width: 1200px;
  margin: 0 auto;
  padding: 0 16px;
}

.page-header {
  margin-bottom: 24px;
}

.page-header h1 {
  font-size: 28px;
  font-weight: 700;
  color: var(--text-color, #f1f5f9);
  margin: 0 0 8px 0;
}

.page-description {
  font-size: 16px;
  color: var(--text-color-secondary, #94a3b8);
  margin: 0;
}

.scanner-layout {
  display: grid;
  grid-template-columns: 350px 1fr;
  gap: 24px;
  align-items: start;
}

.control-section {
  position: sticky;
  top: 24px;
}

/* Responsive layout */
@media (max-width: 900px) {
  .scanner-layout {
    grid-template-columns: 1fr;
  }

  .control-section {
    position: static;
  }
}
</style>
