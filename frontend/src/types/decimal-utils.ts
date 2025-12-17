/**
 * Decimal Arithmetic Utilities for Campaign Performance Calculations
 *
 * Provides type-safe wrappers around Big.js for working with decimal
 * values returned from the backend API. All decimal fields are serialized
 * as strings to preserve precision (NUMERIC(18,8) → "123.45678900").
 *
 * Story 9.6 - Campaign Performance Tracking
 */

import Big from 'big.js'

// Configure Big.js defaults
// Precision: 8 decimal places to match NUMERIC(18,8) backend precision
Big.DP = 8 // Decimal places
Big.RM = Big.roundHalfUp // Rounding mode (banker's rounding)

/**
 * Convert string decimal to Big.js instance for calculations
 *
 * @param value - Decimal value as string (e.g., "123.45678900")
 * @returns Big.js instance for arithmetic operations
 *
 * @example
 * const price = toBig("150.50000000")
 * const profit = price.minus("100.00000000")
 */
export function toBig(value: string | null | undefined): Big {
  if (value === null || value === undefined || value === '') {
    return new Big(0)
  }
  return new Big(value)
}

/**
 * Convert Big.js instance back to string with 8 decimal places
 *
 * @param value - Big.js instance
 * @returns Formatted string with 8 decimal places
 *
 * @example
 * const result = new Big("150.5").plus("10.25")
 * const formatted = fromBig(result) // "160.75000000"
 */
export function fromBig(value: Big): string {
  return value.toFixed(8)
}

/**
 * Format decimal string for display (remove trailing zeros)
 *
 * @param value - Decimal value as string
 * @param maxDecimals - Maximum decimal places to show (default: 2)
 * @returns Formatted string for UI display
 *
 * @example
 * formatDecimal("150.50000000", 2) // "150.50"
 * formatDecimal("0.00012300", 6)   // "0.000123"
 */
export function formatDecimal(
  value: string | null | undefined,
  maxDecimals = 2
): string {
  if (value === null || value === undefined || value === '') {
    return '0.00'
  }

  const big = toBig(value)
  return big.toFixed(maxDecimals)
}

/**
 * Format decimal as percentage (e.g., "15.50" → "15.50%")
 *
 * @param value - Decimal value as string
 * @param decimals - Decimal places to show (default: 2)
 * @returns Formatted percentage string
 *
 * @example
 * formatPercent("15.50000000", 2) // "15.50%"
 * formatPercent("0.75000000", 2)  // "0.75%"
 */
export function formatPercent(
  value: string | null | undefined,
  decimals = 2
): string {
  if (value === null || value === undefined || value === '') {
    return '0.00%'
  }

  const big = toBig(value)
  return `${big.toFixed(decimals)}%`
}

/**
 * Format R-multiple value (e.g., "2.5000" → "2.50R")
 *
 * @param value - R-multiple as string
 * @param decimals - Decimal places to show (default: 2)
 * @returns Formatted R-multiple string
 *
 * @example
 * formatR("2.50000000", 2)  // "2.50R"
 * formatR("-0.80000000", 2) // "-0.80R"
 */
export function formatR(
  value: string | null | undefined,
  decimals = 2
): string {
  if (value === null || value === undefined || value === '') {
    return '0.00R'
  }

  const big = toBig(value)
  return `${big.toFixed(decimals)}R`
}

/**
 * Format currency value with symbol (e.g., "1250.50" → "$1,250.50")
 *
 * @param value - Decimal value as string
 * @param symbol - Currency symbol (default: "$")
 * @param decimals - Decimal places to show (default: 2)
 * @returns Formatted currency string
 *
 * @example
 * formatCurrency("1250.50000000", "$", 2) // "$1,250.50"
 * formatCurrency("100.00000000", "€", 2)  // "€100.00"
 */
export function formatCurrency(
  value: string | null | undefined,
  symbol = '$',
  decimals = 2
): string {
  if (value === null || value === undefined || value === '') {
    return `${symbol}0.00`
  }

  const big = toBig(value)
  const formatted = big.toFixed(decimals)

  // Add thousands separators
  const parts = formatted.split('.')
  parts[0] = parts[0].replace(/\B(?=(\d{3})+(?!\d))/g, ',')

  return `${symbol}${parts.join('.')}`
}

/**
 * Calculate percentage change between two decimal values
 *
 * Formula: ((new_value - old_value) / old_value) × 100
 *
 * @param oldValue - Original value as string
 * @param newValue - New value as string
 * @returns Percentage change as string
 *
 * @example
 * calculatePercentChange("100.00", "150.00") // "50.00000000" (50% increase)
 * calculatePercentChange("150.00", "100.00") // "-33.33333333" (33% decrease)
 */
export function calculatePercentChange(
  oldValue: string | null | undefined,
  newValue: string | null | undefined
): string {
  const old = toBig(oldValue)
  const newVal = toBig(newValue)

  if (old.eq(0)) {
    return '0.00000000'
  }

  const change = newVal.minus(old).div(old).times(100)
  return change.toFixed(8)
}

/**
 * Calculate R-multiple from entry, exit, and stop prices
 *
 * Formula: (exit_price - entry_price) / (entry_price - stop_loss)
 *
 * @param entryPrice - Entry fill price
 * @param exitPrice - Exit fill price
 * @param stopLoss - Stop loss price
 * @returns R-multiple as string
 *
 * @example
 * calculateR("100.00", "110.00", "98.00") // "5.00000000" (5R profit)
 * calculateR("100.00", "99.00", "98.00")  // "-0.50000000" (-0.5R loss)
 */
export function calculateR(
  entryPrice: string | null | undefined,
  exitPrice: string | null | undefined,
  stopLoss: string | null | undefined
): string {
  const entry = toBig(entryPrice)
  const exit = toBig(exitPrice)
  const stop = toBig(stopLoss)

  const risk = entry.minus(stop)

  if (risk.lte(0)) {
    throw new Error('Stop loss must be below entry price for long positions')
  }

  const profit = exit.minus(entry)
  const rMultiple = profit.div(risk)

  return rMultiple.toFixed(4) // R-multiple uses 4 decimal places
}

/**
 * Sum an array of decimal strings
 *
 * @param values - Array of decimal strings
 * @returns Sum as string
 *
 * @example
 * sumDecimals(["10.50", "20.25", "5.00"]) // "35.75000000"
 */
export function sumDecimals(values: (string | null | undefined)[]): string {
  let sum = new Big(0)

  for (const value of values) {
    if (value !== null && value !== undefined && value !== '') {
      sum = sum.plus(value)
    }
  }

  return sum.toFixed(8)
}

/**
 * Calculate average of decimal strings
 *
 * @param values - Array of decimal strings
 * @returns Average as string
 *
 * @example
 * averageDecimals(["10.00", "20.00", "30.00"]) // "20.00000000"
 */
export function averageDecimals(values: (string | null | undefined)[]): string {
  const filtered = values.filter(
    (v) => v !== null && v !== undefined && v !== ''
  )

  if (filtered.length === 0) {
    return '0.00000000'
  }

  const sum = sumDecimals(filtered)
  const avg = toBig(sum).div(filtered.length)

  return avg.toFixed(8)
}

/**
 * Compare two decimal strings
 *
 * @param a - First decimal string
 * @param b - Second decimal string
 * @returns -1 if a < b, 0 if a == b, 1 if a > b
 *
 * @example
 * compareDecimals("10.50", "20.00") // -1
 * compareDecimals("20.00", "20.00") // 0
 * compareDecimals("30.00", "20.00") // 1
 */
export function compareDecimals(
  a: string | null | undefined,
  b: string | null | undefined
): -1 | 0 | 1 {
  const bigA = toBig(a)
  const bigB = toBig(b)

  if (bigA.lt(bigB)) return -1
  if (bigA.gt(bigB)) return 1
  return 0
}

/**
 * Check if decimal value is positive
 *
 * @param value - Decimal string
 * @returns True if value > 0
 */
export function isPositive(value: string | null | undefined): boolean {
  return toBig(value).gt(0)
}

/**
 * Check if decimal value is negative
 *
 * @param value - Decimal string
 * @returns True if value < 0
 */
export function isNegative(value: string | null | undefined): boolean {
  return toBig(value).lt(0)
}

/**
 * Check if decimal value is zero
 *
 * @param value - Decimal string
 * @returns True if value == 0
 */
export function isZero(value: string | null | undefined): boolean {
  return toBig(value).eq(0)
}

/**
 * Get absolute value of decimal
 *
 * @param value - Decimal string
 * @returns Absolute value as string
 *
 * @example
 * abs("-10.50") // "10.50000000"
 * abs("10.50")  // "10.50000000"
 */
export function abs(value: string | null | undefined): string {
  return toBig(value).abs().toFixed(8)
}

/**
 * Get minimum value from array of decimal strings
 *
 * @param values - Array of decimal strings
 * @returns Minimum value as string
 *
 * @example
 * minDecimal(["10.50", "5.25", "20.00"]) // "5.25000000"
 */
export function minDecimal(values: (string | null | undefined)[]): string {
  const filtered = values.filter(
    (v) => v !== null && v !== undefined && v !== ''
  )

  if (filtered.length === 0) {
    return '0.00000000'
  }

  let min = toBig(filtered[0])

  for (let i = 1; i < filtered.length; i++) {
    const current = toBig(filtered[i])
    if (current.lt(min)) {
      min = current
    }
  }

  return min.toFixed(8)
}

/**
 * Get maximum value from array of decimal strings
 *
 * @param values - Array of decimal strings
 * @returns Maximum value as string
 *
 * @example
 * maxDecimal(["10.50", "5.25", "20.00"]) // "20.00000000"
 */
export function maxDecimal(values: (string | null | undefined)[]): string {
  const filtered = values.filter(
    (v) => v !== null && v !== undefined && v !== ''
  )

  if (filtered.length === 0) {
    return '0.00000000'
  }

  let max = toBig(filtered[0])

  for (let i = 1; i < filtered.length; i++) {
    const current = toBig(filtered[i])
    if (current.gt(max)) {
      max = current
    }
  }

  return max.toFixed(8)
}
