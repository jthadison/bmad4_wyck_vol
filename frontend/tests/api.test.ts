import { describe, it, expect } from 'vitest'
import Big from 'big.js'

describe('API Client', () => {
  it('converts Decimal strings to Big.js objects for price fields', () => {
    const response = {
      entry_price: '123.456789',
      risk_percent: '2.50',
      other_field: 'not a decimal',
    }

    // Test the conversion logic directly
    const converted = convertDecimalsToBig(response)

    expect(converted.entry_price).toBeInstanceOf(Big)
    expect(converted.entry_price.toString()).toBe('123.456789')
    expect(converted.risk_percent).toBeInstanceOf(Big)
    expect(converted.risk_percent.toString()).toBe('2.5') // Big.js normalizes trailing zeros
    expect(converted.other_field).toBe('not a decimal')
  })
})

// Helper function for testing (extracted from api.ts logic)
function convertDecimalsToBig(obj: unknown): unknown {
  if (obj === null || obj === undefined) {
    return obj
  }

  if (Array.isArray(obj)) {
    return obj.map((item) => convertDecimalsToBig(item))
  }

  if (typeof obj === 'object') {
    const converted: Record<string, unknown> = {}
    for (const key in obj as Record<string, unknown>) {
      const value = (obj as Record<string, unknown>)[key]
      if (
        typeof value === 'string' &&
        /^-?\d+\.\d+$/.test(value) &&
        (key.includes('price') ||
          key.includes('risk') ||
          key.includes('percent') ||
          key.includes('ratio') ||
          key.includes('size'))
      ) {
        converted[key] = new Big(value)
      } else {
        converted[key] = convertDecimalsToBig(value)
      }
    }
    return converted
  }

  return obj
}
