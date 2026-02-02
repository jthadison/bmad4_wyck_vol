/**
 * Vitest Test Setup (Story 10.8)
 *
 * Configures global test environment including PrimeVue plugin setup
 * and global API mocking to prevent ECONNREFUSED errors.
 */

import { config } from '@vue/test-utils'
import PrimeVue from 'primevue/config'
import { vi } from 'vitest'

// Configure PrimeVue plugin for all tests
config.global.plugins = [PrimeVue]

// Mock $primevue config object
config.global.mocks = {
  $primevue: {
    config: {
      ripple: false,
      inputStyle: 'filled',
      locale: {
        firstDayOfWeek: 0,
        dayNames: [
          'Sunday',
          'Monday',
          'Tuesday',
          'Wednesday',
          'Thursday',
          'Friday',
          'Saturday',
        ],
        dayNamesShort: ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'],
        dayNamesMin: ['Su', 'Mo', 'Tu', 'We', 'Th', 'Fr', 'Sa'],
        monthNames: [
          'January',
          'February',
          'March',
          'April',
          'May',
          'June',
          'July',
          'August',
          'September',
          'October',
          'November',
          'December',
        ],
        monthNamesShort: [
          'Jan',
          'Feb',
          'Mar',
          'Apr',
          'May',
          'Jun',
          'Jul',
          'Aug',
          'Sep',
          'Oct',
          'Nov',
          'Dec',
        ],
        today: 'Today',
        clear: 'Clear',
      },
    },
  },
}

// ============================================================================
// Global API Mocking (Issue #335)
// ============================================================================

/**
 * Mock the API client globally to prevent real HTTP requests in tests.
 * Individual tests can override these mocks as needed.
 */
vi.mock('@/services/api', () => ({
  apiClient: {
    get: vi.fn().mockResolvedValue(null),
    post: vi.fn().mockResolvedValue(null),
    put: vi.fn().mockResolvedValue(null),
    patch: vi.fn().mockResolvedValue(null),
    delete: vi.fn().mockResolvedValue(null),
  },
}))
