<script setup lang="ts">
/**
 * Audit Trail Admin View (Task #2)
 *
 * Page-level wrapper for the correlation override audit trail dashboard.
 * Route: /admin/audit-trail
 */

import CorrelationOverrideAuditLog from '@/components/audit/CorrelationOverrideAuditLog.vue'
</script>

<template>
  <div class="audit-trail-view">
    <CorrelationOverrideAuditLog />
  </div>
</template>

<style scoped>
.audit-trail-view {
  @apply max-w-7xl mx-auto py-6 px-4;
}
</style>
