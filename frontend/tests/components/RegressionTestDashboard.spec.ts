/**
 * Component tests for RegressionTestDashboard (Story 12.7 AC 10)
 *
 * Tests:
 * - Component rendering and initialization
 * - Test history loading and display
 * - Baseline loading and display
 * - Run test dialog and execution
 * - Establish baseline functionality
 * - Metric change calculations
 * - Error handling
 *
 * Author: Story 12.7 AC 10
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import RegressionTestDashboard from '@/components/RegressionTestDashboard.vue'

// Mock PrimeVue components
vi.mock('primevue/card', () => ({
  default: { name: 'Card', template: '<div class="p-card"><slot /></div>' },
}))

vi.mock('primevue/button', () => ({
  default: {
    name: 'Button',
    template: '<button @click="$attrs.onClick"><slot /></button>',
  },
}))

vi.mock('primevue/datatable', () => ({
  default: {
    name: 'DataTable',
    template: '<table><slot /></table>',
    props: ['value', 'paginator', 'rows', 'loading'],
  },
}))

vi.mock('primevue/column', () => ({
  default: {
    name: 'Column',
    template: '<td><slot /></td>',
    props: ['field', 'header', 'sortable'],
  },
}))

vi.mock('primevue/dialog', () => ({
  default: {
    name: 'Dialog',
    template: '<div v-if="visible" class="p-dialog"><slot /></div>',
    props: ['visible', 'header', 'modal'],
  },
}))

vi.mock('primevue/inputtext', () => ({
  default: {
    name: 'InputText',
    template:
      '<input :value="modelValue" @input="$emit(\'update:modelValue\', $event.target.value)" />',
    props: ['modelValue'],
  },
}))

vi.mock('primevue/calendar', () => ({
  default: {
    name: 'Calendar',
    template:
      '<input type="date" :value="modelValue" @input="$emit(\'update:modelValue\', $event.target.value)" />',
    props: ['modelValue', 'dateFormat'],
  },
}))

vi.mock('primevue/checkbox', () => ({
  default: {
    name: 'Checkbox',
    template:
      '<input type="checkbox" :checked="modelValue" @change="$emit(\'update:modelValue\', $event.target.checked)" />',
    props: ['modelValue', 'binary'],
  },
}))

vi.mock('primevue/message', () => ({
  default: {
    name: 'Message',
    template: '<div class="p-message"><slot /></div>',
    props: ['severity'],
  },
}))

vi.mock('primevue/usetoast', () => ({
  useToast: () => ({
    add: vi.fn(),
  }),
}))

// Mock fetch globally
global.fetch = vi.fn()

describe('RegressionTestDashboard', () => {
  let fetchMock: ReturnType<typeof vi.fn>

  beforeEach(() => {
    setActivePinia(createPinia())
    fetchMock = global.fetch as ReturnType<typeof vi.fn>
    fetchMock.mockClear()
  })

  afterEach(() => {
    vi.clearAllMocks()
  })

  const mockTestResult = {
    test_id: '550e8400-e29b-41d4-a716-446655440000',
    status: 'PASS',
    test_run_time: '2024-01-15T10:00:00',
    codebase_version: 'abc123',
    regression_detected: false,
    degraded_metrics: [],
    aggregate_metrics: {
      total_trades: 150,
      winning_trades: 95,
      losing_trades: 55,
      win_rate: 0.6333,
      average_r_multiple: 1.85,
      profit_factor: 2.45,
      max_drawdown: 0.12,
      sharpe_ratio: 1.75,
      total_return: 0.35,
    },
    per_symbol_results: {
      AAPL: {
        total_trades: 50,
        win_rate: 0.64,
        profit_factor: 2.5,
      },
    },
    execution_time_seconds: 45.5,
  }

  const mockBaseline = {
    baseline_id: '650e8400-e29b-41d4-a716-446655440001',
    test_id: '550e8400-e29b-41d4-a716-446655440000',
    codebase_version: 'abc123',
    established_at: '2024-01-15T10:00:00',
    baseline_metrics: {
      total_trades: 150,
      win_rate: 0.6333,
      average_r_multiple: 1.85,
      profit_factor: 2.45,
      max_drawdown: 0.12,
      sharpe_ratio: 1.75,
    },
  }

  describe('Component Rendering', () => {
    it('renders dashboard title', async () => {
      fetchMock.mockResolvedValueOnce({
        ok: true,
        json: async () => ({ tests: [] }),
      })

      const wrapper = mount(RegressionTestDashboard)
      await flushPromises()

      expect(wrapper.text()).toContain('Regression Test Dashboard')
    })

    it('renders all main sections', async () => {
      fetchMock
        .mockResolvedValueOnce({
          ok: true,
          json: async () => ({ tests: [mockTestResult] }),
        })
        .mockResolvedValueOnce({
          ok: true,
          json: async () => mockBaseline,
        })

      const wrapper = mount(RegressionTestDashboard)
      await flushPromises()

      expect(wrapper.text()).toContain('Current Baseline')
      expect(wrapper.text()).toContain('Latest Test Result')
      expect(wrapper.text()).toContain('Test History')
    })

    it('shows loading state initially', () => {
      fetchMock.mockImplementation(
        () =>
          new Promise((resolve) => {
            setTimeout(
              () =>
                resolve({
                  ok: true,
                  json: async () => ({ tests: [] }),
                }),
              100
            )
          })
      )

      const wrapper = mount(RegressionTestDashboard)

      // Loading should be true initially
      expect(wrapper.vm.loading).toBe(true)
    })
  })

  describe('Data Loading', () => {
    it('loads test history on mount', async () => {
      fetchMock.mockResolvedValueOnce({
        ok: true,
        json: async () => ({ tests: [mockTestResult] }),
      })

      const wrapper = mount(RegressionTestDashboard)
      await flushPromises()

      expect(fetchMock).toHaveBeenCalledWith(
        '/api/v1/regression/tests?limit=50'
      )
      expect(wrapper.vm.testHistory).toHaveLength(1)
      expect(wrapper.vm.testHistory[0].test_id).toBe(mockTestResult.test_id)
    })

    it('loads current baseline on mount', async () => {
      fetchMock
        .mockResolvedValueOnce({
          ok: true,
          json: async () => ({ tests: [mockTestResult] }),
        })
        .mockResolvedValueOnce({
          ok: true,
          json: async () => mockBaseline,
        })

      const wrapper = mount(RegressionTestDashboard)
      await flushPromises()

      expect(fetchMock).toHaveBeenCalledWith('/api/v1/regression/baseline')
      expect(wrapper.vm.currentBaseline).toEqual(mockBaseline)
    })

    it('sets latestTest from test history', async () => {
      fetchMock.mockResolvedValueOnce({
        ok: true,
        json: async () => ({ tests: [mockTestResult] }),
      })

      const wrapper = mount(RegressionTestDashboard)
      await flushPromises()

      expect(wrapper.vm.latestTest).toEqual(mockTestResult)
    })

    it('handles empty test history', async () => {
      fetchMock.mockResolvedValueOnce({
        ok: true,
        json: async () => ({ tests: [] }),
      })

      const wrapper = mount(RegressionTestDashboard)
      await flushPromises()

      expect(wrapper.vm.testHistory).toHaveLength(0)
      expect(wrapper.vm.latestTest).toBeNull()
    })

    it('handles baseline not found', async () => {
      fetchMock
        .mockResolvedValueOnce({
          ok: true,
          json: async () => ({ tests: [mockTestResult] }),
        })
        .mockResolvedValueOnce({
          ok: false,
          status: 404,
        })

      const wrapper = mount(RegressionTestDashboard)
      await flushPromises()

      expect(wrapper.vm.currentBaseline).toBeNull()
    })
  })

  describe('Metric Formatting', () => {
    it('formats percentages correctly', async () => {
      fetchMock.mockResolvedValueOnce({
        ok: true,
        json: async () => ({ tests: [mockTestResult] }),
      })

      const wrapper = mount(RegressionTestDashboard)
      await flushPromises()

      expect(wrapper.vm.formatPercent(0.6333)).toBe('63.33%')
      expect(wrapper.vm.formatPercent(0.12)).toBe('12.00%')
    })

    it('formats decimal values correctly', async () => {
      fetchMock.mockResolvedValueOnce({
        ok: true,
        json: async () => ({ tests: [mockTestResult] }),
      })

      const wrapper = mount(RegressionTestDashboard)
      await flushPromises()

      expect(wrapper.vm.formatDecimal(1.85)).toBe('1.85')
      expect(wrapper.vm.formatDecimal(2.45678)).toBe('2.46')
    })

    it('formats dates correctly', async () => {
      fetchMock.mockResolvedValueOnce({
        ok: true,
        json: async () => ({ tests: [mockTestResult] }),
      })

      const wrapper = mount(RegressionTestDashboard)
      await flushPromises()

      const result = wrapper.vm.formatDate('2024-01-15T10:00:00')
      expect(result).toContain('2024')
      expect(result).toContain('01')
      expect(result).toContain('15')
    })
  })

  describe('Metric Change Helper', () => {
    it('calculates metric change with degradation', async () => {
      fetchMock.mockResolvedValueOnce({
        ok: true,
        json: async () => ({ tests: [] }),
      })

      const wrapper = mount(RegressionTestDashboard)
      await flushPromises()

      const comparison = {
        metric_comparisons: {
          win_rate: {
            baseline_value: 0.65,
            current_value: 0.6,
            percent_change: -7.69,
            threshold: 5.0,
          },
        },
      }

      const change = wrapper.vm.getMetricChange('win_rate', comparison)

      expect(change).toBeDefined()
      expect(change.change).toBe(-7.69)
      expect(change.isNegative).toBe(true)
      expect(change.icon).toBe('pi-arrow-down')
      expect(change.color).toBe('text-red-500')
      expect(change.display).toBe('7.69%')
    })

    it('calculates metric change with improvement', async () => {
      fetchMock.mockResolvedValueOnce({
        ok: true,
        json: async () => ({ tests: [] }),
      })

      const wrapper = mount(RegressionTestDashboard)
      await flushPromises()

      const comparison = {
        metric_comparisons: {
          win_rate: {
            baseline_value: 0.6,
            current_value: 0.65,
            percent_change: 8.33,
            threshold: 5.0,
          },
        },
      }

      const change = wrapper.vm.getMetricChange('win_rate', comparison)

      expect(change).toBeDefined()
      expect(change.change).toBe(8.33)
      expect(change.isNegative).toBe(false)
      expect(change.icon).toBe('pi-arrow-up')
      expect(change.color).toBe('text-green-500')
      expect(change.display).toBe('8.33%')
    })

    it('returns null for missing metric', async () => {
      fetchMock.mockResolvedValueOnce({
        ok: true,
        json: async () => ({ tests: [] }),
      })

      const wrapper = mount(RegressionTestDashboard)
      await flushPromises()

      const comparison = {
        metric_comparisons: {},
      }

      const change = wrapper.vm.getMetricChange('win_rate', comparison)

      expect(change).toBeNull()
    })

    it('returns null for null comparison', async () => {
      fetchMock.mockResolvedValueOnce({
        ok: true,
        json: async () => ({ tests: [] }),
      })

      const wrapper = mount(RegressionTestDashboard)
      await flushPromises()

      const change = wrapper.vm.getMetricChange('win_rate', null)

      expect(change).toBeNull()
    })
  })

  describe('Run Test Dialog', () => {
    it('opens run dialog when button clicked', async () => {
      fetchMock.mockResolvedValueOnce({
        ok: true,
        json: async () => ({ tests: [] }),
      })

      const wrapper = mount(RegressionTestDashboard)
      await flushPromises()

      expect(wrapper.vm.showRunDialog).toBe(false)

      // Trigger openRunDialog
      wrapper.vm.openRunDialog()

      expect(wrapper.vm.showRunDialog).toBe(true)
    })

    it('has default test parameters', async () => {
      fetchMock.mockResolvedValueOnce({
        ok: true,
        json: async () => ({ tests: [] }),
      })

      const wrapper = mount(RegressionTestDashboard)
      await flushPromises()

      expect(wrapper.vm.runTestParams.symbols).toBe('AAPL,MSFT,GOOGL,TSLA,NVDA')
      expect(wrapper.vm.runTestParams.startDate).toBeDefined()
      expect(wrapper.vm.runTestParams.endDate).toBeDefined()
      expect(wrapper.vm.runTestParams.establishBaseline).toBe(false)
    })
  })

  describe('Run Test Execution', () => {
    it('runs test with correct parameters', async () => {
      fetchMock
        .mockResolvedValueOnce({
          ok: true,
          json: async () => ({ tests: [] }),
        })
        .mockResolvedValueOnce({
          ok: true,
          json: async () => mockTestResult,
        })
        .mockResolvedValueOnce({
          ok: true,
          json: async () => ({ tests: [mockTestResult] }),
        })

      const wrapper = mount(RegressionTestDashboard)
      await flushPromises()

      wrapper.vm.runTestParams.symbols = 'AAPL,MSFT'
      wrapper.vm.runTestParams.establishBaseline = true

      await wrapper.vm.runTest()
      await flushPromises()

      const postCall = fetchMock.mock.calls.find(
        (call) => call[0] === '/api/v1/regression/test'
      )
      expect(postCall).toBeDefined()
      expect(postCall[1].method).toBe('POST')

      const body = JSON.parse(postCall[1].body)
      expect(body.symbols).toEqual(['AAPL', 'MSFT'])
      expect(body.establish_baseline).toBe(true)
    })

    it('sets runningTest flag during execution', async () => {
      fetchMock
        .mockResolvedValueOnce({
          ok: true,
          json: async () => ({ tests: [] }),
        })
        .mockResolvedValueOnce(
          new Promise((resolve) => {
            setTimeout(
              () =>
                resolve({
                  ok: true,
                  json: async () => mockTestResult,
                }),
              100
            )
          })
        )

      const wrapper = mount(RegressionTestDashboard)
      await flushPromises()

      const runPromise = wrapper.vm.runTest()

      expect(wrapper.vm.runningTest).toBe(true)

      await runPromise
      await flushPromises()

      expect(wrapper.vm.runningTest).toBe(false)
    })

    it('closes dialog after successful test run', async () => {
      fetchMock
        .mockResolvedValueOnce({
          ok: true,
          json: async () => ({ tests: [] }),
        })
        .mockResolvedValueOnce({
          ok: true,
          json: async () => mockTestResult,
        })
        .mockResolvedValueOnce({
          ok: true,
          json: async () => ({ tests: [mockTestResult] }),
        })

      const wrapper = mount(RegressionTestDashboard)
      await flushPromises()

      wrapper.vm.showRunDialog = true

      await wrapper.vm.runTest()
      await flushPromises()

      expect(wrapper.vm.showRunDialog).toBe(false)
    })
  })

  describe('Establish Baseline', () => {
    it('establishes baseline with correct test_id', async () => {
      fetchMock
        .mockResolvedValueOnce({
          ok: true,
          json: async () => ({ tests: [mockTestResult] }),
        })
        .mockResolvedValueOnce({
          ok: true,
          json: async () => mockBaseline,
        })
        .mockResolvedValueOnce({
          ok: true,
          json: async () => mockBaseline,
        })

      const wrapper = mount(RegressionTestDashboard)
      await flushPromises()

      await wrapper.vm.establishBaseline()
      await flushPromises()

      const postCall = fetchMock.mock.calls.find(
        (call) => call[0] === '/api/v1/regression/baseline'
      )
      expect(postCall).toBeDefined()
      expect(postCall[1].method).toBe('POST')

      const body = JSON.parse(postCall[1].body)
      expect(body.test_id).toBe(mockTestResult.test_id)
    })

    it('sets establishingBaseline flag during execution', async () => {
      fetchMock
        .mockResolvedValueOnce({
          ok: true,
          json: async () => ({ tests: [mockTestResult] }),
        })
        .mockResolvedValueOnce(
          new Promise((resolve) => {
            setTimeout(
              () =>
                resolve({
                  ok: true,
                  json: async () => mockBaseline,
                }),
              100
            )
          })
        )

      const wrapper = mount(RegressionTestDashboard)
      await flushPromises()

      const baselinePromise = wrapper.vm.establishBaseline()

      expect(wrapper.vm.establishingBaseline).toBe(true)

      await baselinePromise
      await flushPromises()

      expect(wrapper.vm.establishingBaseline).toBe(false)
    })
  })

  describe('Error Handling', () => {
    it('handles test history load error', async () => {
      fetchMock.mockRejectedValueOnce(new Error('Network error'))

      const wrapper = mount(RegressionTestDashboard)
      await flushPromises()

      expect(wrapper.vm.testHistory).toHaveLength(0)
    })

    it('handles test run error', async () => {
      fetchMock
        .mockResolvedValueOnce({
          ok: true,
          json: async () => ({ tests: [] }),
        })
        .mockRejectedValueOnce(new Error('Test execution failed'))

      const wrapper = mount(RegressionTestDashboard)
      await flushPromises()

      await wrapper.vm.runTest()
      await flushPromises()

      expect(wrapper.vm.runningTest).toBe(false)
    })

    it('handles establish baseline error', async () => {
      fetchMock
        .mockResolvedValueOnce({
          ok: true,
          json: async () => ({ tests: [mockTestResult] }),
        })
        .mockRejectedValueOnce(new Error('Baseline creation failed'))

      const wrapper = mount(RegressionTestDashboard)
      await flushPromises()

      await wrapper.vm.establishBaseline()
      await flushPromises()

      expect(wrapper.vm.establishingBaseline).toBe(false)
    })
  })

  describe('Status Badge', () => {
    it('returns correct badge class for PASS', async () => {
      fetchMock.mockResolvedValueOnce({
        ok: true,
        json: async () => ({ tests: [] }),
      })

      const wrapper = mount(RegressionTestDashboard)
      await flushPromises()

      expect(wrapper.vm.getStatusBadgeClass('PASS')).toBe('badge-success')
    })

    it('returns correct badge class for FAIL', async () => {
      fetchMock.mockResolvedValueOnce({
        ok: true,
        json: async () => ({ tests: [] }),
      })

      const wrapper = mount(RegressionTestDashboard)
      await flushPromises()

      expect(wrapper.vm.getStatusBadgeClass('FAIL')).toBe('badge-danger')
    })

    it('returns correct badge class for BASELINE_NOT_SET', async () => {
      fetchMock.mockResolvedValueOnce({
        ok: true,
        json: async () => ({ tests: [] }),
      })

      const wrapper = mount(RegressionTestDashboard)
      await flushPromises()

      expect(wrapper.vm.getStatusBadgeClass('BASELINE_NOT_SET')).toBe(
        'badge-warning'
      )
    })
  })
})
