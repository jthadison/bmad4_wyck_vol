<template>
  <div class="empty-state">
    <i class="pi pi-chart-line empty-icon"></i>
    <h3>{{ title }}</h3>
    <p>{{ message }}</p>
    <slot name="action"></slot>
  </div>
</template>

<script setup lang="ts">
/**
 * Empty State Component for Campaign Tracker (Story 11.4 Task 11)
 *
 * Displays when no campaigns match the current filters or when no campaigns exist.
 */

interface Props {
  title?: string
  message?: string
}

withDefaults(defineProps<Props>(), {
  title: 'No Active Campaigns',
  message:
    'There are no active campaigns to display. Campaigns will appear here once the system detects Wyckoff accumulation patterns and generates entry signals.',
})
</script>

<style scoped>
.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 4rem 2rem;
  text-align: center;
  color: var(--text-color-secondary);
}

.empty-icon {
  font-size: 4rem;
  color: var(--gray-400);
  margin-bottom: 1.5rem;
}

.empty-state h3 {
  margin: 0 0 0.5rem 0;
  color: var(--text-color);
  font-size: 1.5rem;
}

.empty-state p {
  margin: 0 0 1.5rem 0;
  max-width: 500px;
  line-height: 1.6;
}
</style>
