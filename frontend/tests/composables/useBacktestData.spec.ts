/**
 * Tests for useBacktestData Composable (Story 12.6C)
 *
 * Comprehensive tests for backtest data fetching, caching, and report downloads.
 * Tests cover loading states, error handling, cache behavior, and download functionality.
 *
 * Test Coverage:
 * - fetchBacktestResult(): loading states, success, error handling, cache behavior
 * - downloadHtmlReport(), downloadPdfReport(), downloadCsvTrades()
 * - Error messages for 404, 500, network errors
 * - Cache prevents redundant API calls
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import axios from 'axios'
import { useBacktestData } from '@/composables/useBacktestData'
import type { BacktestResult } from '@/types/backtest'

// Mock axios
vi.mock('axios')
const mockedAxios = vi.mocked(axios)

describe('useBacktestData', () => {
  // Mock backtest result data
  const mockBacktestResult: BacktestResult = {
    backtest_run_id: 'test-run-123',
    symbol: 'AAPL',
    timeframe: '1d',
    start_date: '2023-01-01T00:00:00Z',
    end_date: '2023-12-31T23:59:59Z',
    initial_capital: '100000.00',
    final_capital: '125000.00',
    config: { risk_per_trade: 0.02 },
    summary: {
      total_return_pct: '25.00',
      cagr: '25.00',
      sharpe_ratio: '2.50',
      sortino_ratio: '3.20',
      calmar_ratio: '4.10',
      max_drawdown_pct: '-15.50',
      total_trades: 50,
      winning_trades: 35,
      losing_trades: 15,
      win_rate: '0.70',
      total_pnl: '25000.00',
      gross_pnl: '26500.00',
      avg_win: '1200.00',
      avg_loss: '-400.00',
      avg_r_multiple: '2.50',
      profit_factor: '2.80',
      total_commission: '1200.00',
      total_slippage: '300.00',
      avg_commission_per_trade: '24.00',
      avg_slippage_per_trade: '6.00',
      longest_winning_streak: 8,
      longest_losing_streak: 3,
      total_campaigns_detected: 10,
      completed_campaigns: 7,
      failed_campaigns: 3,
      campaign_completion_rate: '0.70',
    },
    pattern_performance: [],
    monthly_returns: [],
    drawdown_periods: [],
    risk_metrics: {
      max_concurrent_positions: 5,
      avg_concurrent_positions: '3.20',
      max_portfolio_heat: '10.50',
      avg_portfolio_heat: '6.80',
      max_position_size_pct: '5.00',
      avg_position_size_pct: '3.50',
      max_capital_deployed_pct: '85.00',
      avg_capital_deployed_pct: '65.00',
    },
    campaign_performance: [],
    largest_winner: null,
    largest_loser: null,
    trades: [],
    equity_curve: [],
    created_at: '2024-01-01T10:00:00Z',
    execution_time_seconds: 45.3,
    total_bars_analyzed: 252,
  }

  beforeEach(() => {
    vi.clearAllMocks()
    // Mock successful axios get
    mockedAxios.get = vi.fn().mockResolvedValue({ data: mockBacktestResult })
    // Mock document methods for download tests
    document.createElement = vi.fn().mockReturnValue({
      href: '',
      download: '',
      click: vi.fn(),
    })
    document.body.appendChild = vi.fn()
    document.body.removeChild = vi.fn()
    window.URL.createObjectURL = vi.fn().mockReturnValue('blob:mock-url')
    window.URL.revokeObjectURL = vi.fn()
  })

  afterEach(() => {
    vi.resetAllMocks()
  })

  describe('fetchBacktestResult', () => {
    it('should fetch backtest result successfully', async () => {
      const { backtestResult, loading, error, fetchBacktestResult } =
        useBacktestData()

      expect(backtestResult.value).toBeNull()
      expect(loading.value).toBe(false)
      expect(error.value).toBeNull()

      await fetchBacktestResult('test-run-123')

      expect(loading.value).toBe(false)
      expect(error.value).toBeNull()
      expect(backtestResult.value).toEqual(mockBacktestResult)
      expect(mockedAxios.get).toHaveBeenCalledWith(
        'http://localhost:8000/api/v1/backtest/results/test-run-123'
      )
    })

    it('should set loading to true during fetch', async () => {
      const { loading, fetchBacktestResult } = useBacktestData()

      // Create a promise we can control
      let resolvePromise: (value: any) => void
      const controlledPromise = new Promise((resolve) => {
        resolvePromise = resolve
      })

      mockedAxios.get = vi.fn().mockReturnValue(controlledPromise)

      const fetchPromise = fetchBacktestResult('test-run-123')

      // Should be loading while promise is pending
      expect(loading.value).toBe(true)

      // Resolve the promise
      resolvePromise!({ data: mockBacktestResult })
      await fetchPromise

      // Should not be loading after promise resolves
      expect(loading.value).toBe(false)
    })

    it('should cache results and not make redundant API calls', async () => {
      const { backtestResult, fetchBacktestResult } = useBacktestData()

      // First fetch
      await fetchBacktestResult('test-run-123')
      expect(mockedAxios.get).toHaveBeenCalledTimes(1)
      expect(backtestResult.value).toEqual(mockBacktestResult)

      // Second fetch with same ID should use cache
      await fetchBacktestResult('test-run-123')
      expect(mockedAxios.get).toHaveBeenCalledTimes(1) // Still only 1 call
      expect(backtestResult.value).toEqual(mockBacktestResult)
    })

    it('should handle 404 error with specific message', async () => {
      mockedAxios.get = vi.fn().mockRejectedValue({
        isAxiosError: true,
        response: {
          status: 404,
        },
      })
      mockedAxios.isAxiosError = vi.fn().mockReturnValue(true)

      const { backtestResult, error, fetchBacktestResult } = useBacktestData()

      await expect(fetchBacktestResult('nonexistent-123')).rejects.toThrow()

      expect(backtestResult.value).toBeNull()
      expect(error.value).toBe('Backtest run nonexistent-123 not found')
    })

    it('should handle 500 server error with specific message', async () => {
      mockedAxios.get = vi.fn().mockRejectedValue({
        isAxiosError: true,
        response: {
          status: 500,
        },
      })
      mockedAxios.isAxiosError = vi.fn().mockReturnValue(true)

      const { error, fetchBacktestResult } = useBacktestData()

      await expect(fetchBacktestResult('test-run-123')).rejects.toThrow()

      expect(error.value).toBe('Server error while fetching backtest results')
    })

    it('should handle API error with detail message', async () => {
      mockedAxios.get = vi.fn().mockRejectedValue({
        isAxiosError: true,
        response: {
          status: 400,
          data: {
            detail: 'Invalid backtest run ID format',
          },
        },
      })
      mockedAxios.isAxiosError = vi.fn().mockReturnValue(true)

      const { error, fetchBacktestResult } = useBacktestData()

      await expect(fetchBacktestResult('bad-id')).rejects.toThrow()

      expect(error.value).toBe('Invalid backtest run ID format')
    })

    it('should handle network error', async () => {
      mockedAxios.get = vi.fn().mockRejectedValue({
        isAxiosError: true,
        message: 'Network Error',
      })
      mockedAxios.isAxiosError = vi.fn().mockReturnValue(true)

      const { error, fetchBacktestResult } = useBacktestData()

      await expect(fetchBacktestResult('test-run-123')).rejects.toThrow()

      expect(error.value).toBe('Failed to fetch backtest results')
    })

    it('should handle unexpected non-axios error', async () => {
      mockedAxios.get = vi.fn().mockRejectedValue(new Error('Unexpected error'))
      mockedAxios.isAxiosError = vi.fn().mockReturnValue(false)

      const { error, fetchBacktestResult } = useBacktestData()

      await expect(fetchBacktestResult('test-run-123')).rejects.toThrow()

      expect(error.value).toBe('An unexpected error occurred')
    })

    it('should reset error on successful fetch after previous error', async () => {
      const { error, fetchBacktestResult } = useBacktestData()

      // First fetch fails
      mockedAxios.get = vi.fn().mockRejectedValue({
        isAxiosError: true,
        response: { status: 500 },
      })
      mockedAxios.isAxiosError = vi.fn().mockReturnValue(true)

      await expect(fetchBacktestResult('test-run-123')).rejects.toThrow()
      expect(error.value).toBe('Server error while fetching backtest results')

      // Second fetch succeeds
      mockedAxios.get = vi.fn().mockResolvedValue({ data: mockBacktestResult })

      await fetchBacktestResult('test-run-456')
      expect(error.value).toBeNull()
    })
  })

  describe('downloadHtmlReport', () => {
    it('should download HTML report successfully', async () => {
      const mockBlob = new Blob(['<html>Report</html>'], { type: 'text/html' })
      mockedAxios.get = vi.fn().mockResolvedValue({ data: mockBlob })

      const { downloadHtmlReport } = useBacktestData()

      await downloadHtmlReport('test-run-123')

      expect(mockedAxios.get).toHaveBeenCalledWith(
        'http://localhost:8000/api/v1/backtest/results/test-run-123/report/html',
        { responseType: 'blob' }
      )
      expect(window.URL.createObjectURL).toHaveBeenCalled()
      expect(document.createElement).toHaveBeenCalledWith('a')
    })

    it('should set error on HTML download failure', async () => {
      mockedAxios.get = vi.fn().mockRejectedValue({
        isAxiosError: true,
        message: 'Download failed',
      })
      mockedAxios.isAxiosError = vi.fn().mockReturnValue(true)

      const { error, downloadHtmlReport } = useBacktestData()

      await expect(downloadHtmlReport('test-run-123')).rejects.toThrow()

      expect(error.value).toBe('Failed to download HTML report')
    })

    it('should create download link with correct filename', async () => {
      const mockBlob = new Blob(['<html>Report</html>'], { type: 'text/html' })
      mockedAxios.get = vi.fn().mockResolvedValue({ data: mockBlob })

      const mockLink = {
        href: '',
        download: '',
        click: vi.fn(),
      }
      document.createElement = vi.fn().mockReturnValue(mockLink)

      const { downloadHtmlReport } = useBacktestData()

      await downloadHtmlReport('test-run-123')

      expect(mockLink.download).toBe('backtest_test-run-123.html')
      expect(mockLink.click).toHaveBeenCalled()
    })
  })

  describe('downloadPdfReport', () => {
    it('should download PDF report successfully', async () => {
      const mockBlob = new Blob(['PDF content'], { type: 'application/pdf' })
      mockedAxios.get = vi.fn().mockResolvedValue({ data: mockBlob })

      const { downloadPdfReport } = useBacktestData()

      await downloadPdfReport('test-run-123')

      expect(mockedAxios.get).toHaveBeenCalledWith(
        'http://localhost:8000/api/v1/backtest/results/test-run-123/report/pdf',
        { responseType: 'blob' }
      )
      expect(window.URL.createObjectURL).toHaveBeenCalled()
      expect(document.createElement).toHaveBeenCalledWith('a')
    })

    it('should set error on PDF download failure', async () => {
      mockedAxios.get = vi.fn().mockRejectedValue({
        isAxiosError: true,
        message: 'Download failed',
      })
      mockedAxios.isAxiosError = vi.fn().mockReturnValue(true)

      const { error, downloadPdfReport } = useBacktestData()

      await expect(downloadPdfReport('test-run-123')).rejects.toThrow()

      expect(error.value).toBe('Failed to download PDF report')
    })

    it('should create download link with correct PDF filename', async () => {
      const mockBlob = new Blob(['PDF content'], { type: 'application/pdf' })
      mockedAxios.get = vi.fn().mockResolvedValue({ data: mockBlob })

      const mockLink = {
        href: '',
        download: '',
        click: vi.fn(),
      }
      document.createElement = vi.fn().mockReturnValue(mockLink)

      const { downloadPdfReport } = useBacktestData()

      await downloadPdfReport('test-run-456')

      expect(mockLink.download).toBe('backtest_test-run-456.pdf')
      expect(mockLink.click).toHaveBeenCalled()
    })
  })

  describe('downloadCsvTrades', () => {
    it('should download CSV trades successfully', async () => {
      const mockBlob = new Blob(['trade_id,symbol,pnl\n1,AAPL,100'], {
        type: 'text/csv',
      })
      mockedAxios.get = vi.fn().mockResolvedValue({ data: mockBlob })

      const { downloadCsvTrades } = useBacktestData()

      await downloadCsvTrades('test-run-123')

      expect(mockedAxios.get).toHaveBeenCalledWith(
        'http://localhost:8000/api/v1/backtest/results/test-run-123/trades/csv',
        { responseType: 'blob' }
      )
      expect(window.URL.createObjectURL).toHaveBeenCalled()
      expect(document.createElement).toHaveBeenCalledWith('a')
    })

    it('should set error on CSV download failure', async () => {
      mockedAxios.get = vi.fn().mockRejectedValue({
        isAxiosError: true,
        message: 'Download failed',
      })
      mockedAxios.isAxiosError = vi.fn().mockReturnValue(true)

      const { error, downloadCsvTrades } = useBacktestData()

      await expect(downloadCsvTrades('test-run-123')).rejects.toThrow()

      expect(error.value).toBe('Failed to download CSV trade list')
    })

    it('should create download link with correct CSV filename', async () => {
      const mockBlob = new Blob(['trade_id,symbol,pnl\n1,AAPL,100'], {
        type: 'text/csv',
      })
      mockedAxios.get = vi.fn().mockResolvedValue({ data: mockBlob })

      const mockLink = {
        href: '',
        download: '',
        click: vi.fn(),
      }
      document.createElement = vi.fn().mockReturnValue(mockLink)

      const { downloadCsvTrades } = useBacktestData()

      await downloadCsvTrades('test-run-789')

      expect(mockLink.download).toBe('backtest_trades_test-run-789.csv')
      expect(mockLink.click).toHaveBeenCalled()
    })

    it('should clean up blob URL after download', async () => {
      const mockBlob = new Blob(['CSV data'], { type: 'text/csv' })
      mockedAxios.get = vi.fn().mockResolvedValue({ data: mockBlob })

      const { downloadCsvTrades } = useBacktestData()

      await downloadCsvTrades('test-run-123')

      expect(window.URL.revokeObjectURL).toHaveBeenCalledWith('blob:mock-url')
    })
  })

  describe('reactive state', () => {
    it('should expose correct reactive properties', () => {
      const { backtestResult, loading, error } = useBacktestData()

      expect(backtestResult.value).toBeNull()
      expect(loading.value).toBe(false)
      expect(error.value).toBeNull()
    })

    it('should expose all required methods', () => {
      const composable = useBacktestData()

      expect(composable).toHaveProperty('fetchBacktestResult')
      expect(composable).toHaveProperty('downloadHtmlReport')
      expect(composable).toHaveProperty('downloadPdfReport')
      expect(composable).toHaveProperty('downloadCsvTrades')
      expect(typeof composable.fetchBacktestResult).toBe('function')
      expect(typeof composable.downloadHtmlReport).toBe('function')
      expect(typeof composable.downloadPdfReport).toBe('function')
      expect(typeof composable.downloadCsvTrades).toBe('function')
    })
  })
})
