/**
 * useBacktestData Composable (Story 12.6C Task 14 + Story 12.6D Task 17)
 *
 * Vue composable for fetching and managing backtest data from the API.
 * Provides methods for fetching results and downloading reports in various formats.
 *
 * Features:
 * - Fetch backtest results with loading/error states
 * - Fetch list of backtest results for list view (Story 12.6D)
 * - Download HTML, PDF, and CSV reports
 * - Automatic error handling and user-friendly messages
 * - Response caching to avoid redundant API calls
 *
 * Author: Story 12.6C Task 14, Story 12.6D Task 17
 */

import { ref, type Ref } from 'vue'
import axios from 'axios'
import type { BacktestResult, BacktestResultSummary } from '@/types/backtest'

const API_BASE_URL =
  import.meta.env.VITE_API_URL || 'http://localhost:8000/api/v1'

/**
 * Composable for managing backtest data and report downloads.
 *
 * @returns Object containing reactive state and methods for backtest data management
 *
 * @example
 * ```ts
 * const { backtestResult, loading, error, fetchBacktestResult } = useBacktestData()
 *
 * // Fetch backtest result
 * await fetchBacktestResult('abc-123-def-456')
 *
 * if (backtestResult.value) {
 *   console.log(backtestResult.value.summary.total_return_pct)
 * }
 * ```
 */
export function useBacktestData() {
  // Reactive state for single result
  const backtestResult: Ref<BacktestResult | null> = ref(null)
  const loading: Ref<boolean> = ref(false)
  const error: Ref<string | null> = ref(null)

  // Reactive state for results list (Story 12.6D Task 17)
  const backtestResultsList: Ref<BacktestResultSummary[]> = ref([])
  const listLoading: Ref<boolean> = ref(false)
  const listError: Ref<string | null> = ref(null)

  // Cache for fetched results (keyed by backtest_run_id)
  const cache = new Map<string, BacktestResult>()

  /**
   * Fetch backtest result from API.
   *
   * @param backtestRunId - UUID of the backtest run to fetch
   * @throws Error if fetch fails or API returns error
   *
   * @example
   * ```ts
   * try {
   *   await fetchBacktestResult('abc-123-def-456')
   * } catch (err) {
   *   console.error('Failed to load backtest:', err)
   * }
   * ```
   */
  async function fetchBacktestResult(backtestRunId: string): Promise<void> {
    // Check cache first
    if (cache.has(backtestRunId)) {
      backtestResult.value = cache.get(backtestRunId)!
      return
    }

    loading.value = true
    error.value = null

    try {
      const response = await axios.get<BacktestResult>(
        `${API_BASE_URL}/backtest/results/${backtestRunId}`
      )

      backtestResult.value = response.data
      cache.set(backtestRunId, response.data) // Cache the result
    } catch (err) {
      if (axios.isAxiosError(err)) {
        if (err.response?.status === 404) {
          error.value = `Backtest run ${backtestRunId} not found`
        } else if (err.response?.status === 500) {
          error.value = 'Server error while fetching backtest results'
        } else {
          error.value =
            err.response?.data?.detail || 'Failed to fetch backtest results'
        }
      } else {
        error.value = 'An unexpected error occurred'
      }
      backtestResult.value = null
      throw err
    } finally {
      loading.value = false
    }
  }

  /**
   * Download HTML report for a backtest run.
   * Triggers browser download of HTML file.
   *
   * @param backtestRunId - UUID of the backtest run
   *
   * @example
   * ```ts
   * await downloadHtmlReport('abc-123-def-456')
   * ```
   */
  async function downloadHtmlReport(backtestRunId: string): Promise<void> {
    try {
      const response = await axios.get(
        `${API_BASE_URL}/backtest/results/${backtestRunId}/report/html`,
        {
          responseType: 'blob',
        }
      )

      // Create blob and trigger download
      const blob = new Blob([response.data], { type: 'text/html' })
      const url = window.URL.createObjectURL(blob)
      const link = document.createElement('a')
      link.href = url
      link.download = `backtest_${backtestRunId}.html`
      document.body.appendChild(link)
      link.click()
      document.body.removeChild(link)
      window.URL.revokeObjectURL(url)
    } catch (err) {
      if (axios.isAxiosError(err)) {
        error.value = 'Failed to download HTML report'
      }
      throw err
    }
  }

  /**
   * Download PDF report for a backtest run.
   * Triggers browser download of PDF file.
   *
   * @param backtestRunId - UUID of the backtest run
   *
   * @example
   * ```ts
   * await downloadPdfReport('abc-123-def-456')
   * ```
   */
  async function downloadPdfReport(backtestRunId: string): Promise<void> {
    try {
      const response = await axios.get(
        `${API_BASE_URL}/backtest/results/${backtestRunId}/report/pdf`,
        {
          responseType: 'blob',
        }
      )

      // Create blob and trigger download
      const blob = new Blob([response.data], { type: 'application/pdf' })
      const url = window.URL.createObjectURL(blob)
      const link = document.createElement('a')
      link.href = url
      link.download = `backtest_${backtestRunId}.pdf`
      document.body.appendChild(link)
      link.click()
      document.body.removeChild(link)
      window.URL.revokeObjectURL(url)
    } catch (err) {
      if (axios.isAxiosError(err)) {
        error.value = 'Failed to download PDF report'
      }
      throw err
    }
  }

  /**
   * Download CSV trade list for a backtest run.
   * Triggers browser download of CSV file.
   *
   * @param backtestRunId - UUID of the backtest run
   *
   * @example
   * ```ts
   * await downloadCsvTrades('abc-123-def-456')
   * ```
   */
  async function downloadCsvTrades(backtestRunId: string): Promise<void> {
    try {
      const response = await axios.get(
        `${API_BASE_URL}/backtest/results/${backtestRunId}/trades/csv`,
        {
          responseType: 'blob',
        }
      )

      // Create blob and trigger download
      const blob = new Blob([response.data], { type: 'text/csv' })
      const url = window.URL.createObjectURL(blob)
      const link = document.createElement('a')
      link.href = url
      link.download = `backtest_trades_${backtestRunId}.csv`
      document.body.appendChild(link)
      link.click()
      document.body.removeChild(link)
      window.URL.revokeObjectURL(url)
    } catch (err) {
      if (axios.isAxiosError(err)) {
        error.value = 'Failed to download CSV trade list'
      }
      throw err
    }
  }

  /**
   * Fetch list of backtest results (summary format for list view).
   * Story 12.6D Task 17 - Subtask 17.3
   *
   * Uses ?format=summary query parameter to exclude large arrays (equity_curve, trades)
   * for performance optimization.
   *
   * @example
   * ```ts
   * await fetchBacktestResultsList()
   * if (backtestResultsList.value.length > 0) {
   *   console.log('Found', backtestResultsList.value.length, 'backtest results')
   * }
   * ```
   */
  async function fetchBacktestResultsList(): Promise<void> {
    listLoading.value = true
    listError.value = null

    try {
      const response = await axios.get<BacktestResultSummary[]>(
        `${API_BASE_URL}/backtest/results`,
        {
          params: {
            format: 'summary', // Exclude equity_curve and trades arrays
          },
        }
      )

      backtestResultsList.value = response.data
    } catch (err) {
      if (axios.isAxiosError(err)) {
        if (err.response?.status === 500) {
          listError.value = 'Server error while fetching backtest results list'
        } else {
          listError.value =
            err.response?.data?.detail ||
            'Failed to fetch backtest results list'
        }
      } else {
        listError.value = 'An unexpected error occurred'
      }
      backtestResultsList.value = []
      throw err
    } finally {
      listLoading.value = false
    }
  }

  return {
    // Reactive state (single result)
    backtestResult,
    loading,
    error,

    // Reactive state (results list) - Story 12.6D
    backtestResultsList,
    listLoading,
    listError,

    // Methods
    fetchBacktestResult,
    fetchBacktestResultsList, // Story 12.6D Task 17
    downloadHtmlReport,
    downloadPdfReport,
    downloadCsvTrades,
  }
}
