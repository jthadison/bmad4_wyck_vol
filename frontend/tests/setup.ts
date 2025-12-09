/**
 * Vitest Test Setup (Story 10.8)
 *
 * Configures global test environment including PrimeVue plugin setup.
 */

import { config } from '@vue/test-utils'
import PrimeVue from 'primevue/config'

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
