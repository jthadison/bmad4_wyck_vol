/**
 * Unit tests for rejectionParser utility (Story 10.7)
 *
 * Tests parsing of structured rejection reason strings into displayable components.
 */

import { describe, it, expect } from 'vitest'
import {
  parseRejectionReason,
  getVolumeThreshold,
  getVolumeRequirement,
  type RejectionReasonParsed,
} from '@/utils/rejectionParser'

describe('parseRejectionReason', () => {
  it('should parse primary reason with rule type and comparison', () => {
    const input =
      'Volume Too High (Non-Negotiable Rule): 0.82x > 0.7x threshold'
    const result = parseRejectionReason(input)

    expect(result.primary.reason).toBe('Volume Too High')
    expect(result.primary.ruleType).toBe('Non-Negotiable Rule')
    expect(result.primary.actualValue).toBe('0.82x')
    expect(result.primary.thresholdValue).toBe('0.7x')
    expect(result.primary.comparison).toBe('0.82x > 0.7x threshold')
    expect(result.secondary).toHaveLength(0)
    expect(result.raw).toBe(input)
  })

  it('should parse primary and secondary reasons', () => {
    const input =
      'Volume Too High (Non-Negotiable Rule): 0.82x > 0.7x threshold; Test not confirmed: 0 bars vs 3-15 required'
    const result = parseRejectionReason(input)

    expect(result.primary.reason).toBe('Volume Too High')
    expect(result.secondary).toHaveLength(1)
    expect(result.secondary[0].reason).toBe('Test not confirmed')
    expect(result.secondary[0].details).toBe('0 bars vs 3-15 required')
  })

  it('should parse multiple secondary reasons', () => {
    const input =
      'Volume Too High: 0.82x > 0.7x; Test not confirmed: 0 bars; Phase mismatch: Phase B vs Phase C'
    const result = parseRejectionReason(input)

    expect(result.secondary).toHaveLength(2)
    expect(result.secondary[0].reason).toBe('Test not confirmed')
    expect(result.secondary[1].reason).toBe('Phase mismatch')
  })

  it('should handle rejection without rule type', () => {
    const input = 'Phase Mismatch: Phase B, Spring requires Phase C'
    const result = parseRejectionReason(input)

    expect(result.primary.reason).toBe('Phase Mismatch')
    expect(result.primary.ruleType).toBe('')
    expect(result.primary.comparison).toBe('Phase B, Spring requires Phase C')
  })

  it('should handle empty rejection reason', () => {
    const result = parseRejectionReason('')

    expect(result.primary.reason).toBe('Unknown rejection')
    expect(result.primary.ruleType).toBe('')
    expect(result.secondary).toHaveLength(0)
  })

  it('should handle null rejection reason', () => {
    const result = parseRejectionReason(null as unknown)

    expect(result.primary.reason).toBe('Unknown rejection')
  })

  it('should handle malformed rejection reason gracefully', () => {
    const input = 'Random text without structure'
    const result = parseRejectionReason(input)

    expect(result.primary.reason).toBe('Random text without structure')
    expect(result.raw).toBe(input)
  })

  it('should extract actual and threshold values with decimals', () => {
    const input = 'Volume Low: 0.45x < 0.7x threshold'
    const result = parseRejectionReason(input)

    expect(result.primary.actualValue).toBe('0.45x')
    expect(result.primary.thresholdValue).toBe('0.7x')
  })

  it('should extract actual and threshold values with >= operator', () => {
    const input = 'Volume High: 1.5x >= 1.3x threshold'
    const result = parseRejectionReason(input)

    expect(result.primary.actualValue).toBe('1.5x')
    expect(result.primary.thresholdValue).toBe('1.3x')
  })

  it('should handle secondary reason without details', () => {
    const input = 'Primary Reason: Details; Secondary Reason'
    const result = parseRejectionReason(input)

    expect(result.secondary).toHaveLength(1)
    expect(result.secondary[0].reason).toBe('Secondary Reason')
    expect(result.secondary[0].details).toBe('')
  })
})

describe('getVolumeThreshold', () => {
  it('should return 0.7 for SPRING', () => {
    expect(getVolumeThreshold('SPRING')).toBe(0.7)
  })

  it('should return 0.7 for UTAD', () => {
    expect(getVolumeThreshold('UTAD')).toBe(0.7)
  })

  it('should return 1.3 for SOS', () => {
    expect(getVolumeThreshold('SOS')).toBe(1.3)
  })

  it('should return 0.8 for LPS', () => {
    expect(getVolumeThreshold('LPS')).toBe(0.8)
  })

  it('should return 1.5 for SC (Selling Climax)', () => {
    expect(getVolumeThreshold('SC')).toBe(1.5)
  })

  it('should return 1.3 for AR (Automatic Rally)', () => {
    expect(getVolumeThreshold('AR')).toBe(1.3)
  })

  it('should return 0.8 for ST (Secondary Test)', () => {
    expect(getVolumeThreshold('ST')).toBe(0.8)
  })

  it('should be case-insensitive', () => {
    expect(getVolumeThreshold('spring')).toBe(0.7)
    expect(getVolumeThreshold('Spring')).toBe(0.7)
  })

  it('should return default 1.0 for unknown pattern', () => {
    expect(getVolumeThreshold('UNKNOWN')).toBe(1.0)
  })
})

describe('getVolumeRequirement', () => {
  it('should return "low" for SPRING', () => {
    expect(getVolumeRequirement('SPRING')).toBe('low')
  })

  it('should return "low" for UTAD', () => {
    expect(getVolumeRequirement('UTAD')).toBe('low')
  })

  it('should return "high" for SOS', () => {
    expect(getVolumeRequirement('SOS')).toBe('high')
  })

  it('should return "low" for LPS', () => {
    expect(getVolumeRequirement('LPS')).toBe('low')
  })

  it('should return "high" for SC (Selling Climax)', () => {
    expect(getVolumeRequirement('SC')).toBe('high')
  })

  it('should return "high" for AR (Automatic Rally)', () => {
    expect(getVolumeRequirement('AR')).toBe('high')
  })

  it('should return "low" for ST (Secondary Test)', () => {
    expect(getVolumeRequirement('ST')).toBe('low')
  })

  it('should be case-insensitive', () => {
    expect(getVolumeRequirement('sos')).toBe('high')
    expect(getVolumeRequirement('SOS')).toBe('high')
  })

  it('should return "low" for unknown pattern (default)', () => {
    expect(getVolumeRequirement('UNKNOWN')).toBe('low')
  })
})
