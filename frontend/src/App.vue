<template>
  <div id="app" class="min-h-screen bg-gray-900 text-gray-100">
    <!-- System Status Widget (Persistent) -->
    <SystemStatusWidget />

    <!-- Navigation -->
    <nav class="bg-gray-800 border-b border-gray-700">
      <div class="container mx-auto px-4">
        <div class="flex items-center justify-between h-16">
          <div class="flex items-center space-x-8">
            <h1 class="text-xl font-bold text-blue-400">BMAD Wyckoff</h1>
            <div class="flex space-x-4">
              <router-link
                to="/"
                class="px-3 py-2 rounded-md text-sm font-medium hover:bg-gray-700 transition-colors"
                active-class="bg-gray-700 text-blue-400"
              >
                Dashboard
              </router-link>
              <router-link
                to="/backtest"
                class="px-3 py-2 rounded-md text-sm font-medium hover:bg-gray-700 transition-colors"
                active-class="bg-gray-700 text-blue-400"
              >
                Backtest
              </router-link>
              <router-link
                to="/settings"
                class="px-3 py-2 rounded-md text-sm font-medium hover:bg-gray-700 transition-colors"
                active-class="bg-gray-700 text-blue-400"
              >
                Settings
              </router-link>
            </div>
          </div>
        </div>
      </div>
    </nav>

    <!-- Main Content -->
    <main class="container mx-auto px-4 py-8">
      <router-view />
    </main>
  </div>
</template>

<script setup lang="ts">
import SystemStatusWidget from '@/components/SystemStatusWidget.vue'
</script>
