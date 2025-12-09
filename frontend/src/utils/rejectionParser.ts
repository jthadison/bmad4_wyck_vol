/**
 * Rejection Reason Parser Utility (Story 10.7)
 *
 * Purpose:
 * --------
 * Parses structured rejection reason strings from backend into displayable components.
 * Handles various rejection reason formats gracefully with fallback to raw string.
 *
 * Expected Format:
 * ----------------
 * "Primary Reason (Rule Type): Actual vs Threshold; Secondary Reason: Details; ..."
 *
 * Examples:
 * - "Volume Too High (Non-Negotiable Rule): 0.82x > 0.7x threshold"
 * - "Volume Too High (Non-Negotiable Rule): 0.82x > 0.7x threshold; Test not confirmed: 0 bars vs 3-15 required"
 * - "Phase Mismatch: Phase B, Spring requires Phase C"
 *
 * Integration:
 * ------------
 * - Story 10.7: Educational Rejection Detail View
 * - RejectionDetailDialog.vue component
 */

/**
 * Parsed primary rejection reason.
 */
export interface RejectionPrimary {
  /** Main reason (e.g., "Volume Too High") */
  reason: string
  /** Rule type (e.g., "Non-Negotiable Rule") */
  ruleType: string
  /** Actual value (e.g., "0.82x") */
  actualValue: string
  /** Threshold value (e.g., "0.7x") */
  thresholdValue: string
  /** Full comparison string (e.g., "0.82x > 0.7x threshold") */
  comparison: string
}

/**
 * Parsed secondary rejection issue.
 */
export interface RejectionSecondary {
  /** Secondary reason name */
  reason: string
  /** Details about the issue */
  details: string
}

/**
 * Complete parsed rejection reason.
 */
export interface RejectionReasonParsed {
  /** Primary rejection reason */
  primary: RejectionPrimary
  /** Array of secondary issues */
  secondary: RejectionSecondary[]
  /** Original raw rejection_reason string */
  raw: string
}

/**
 * Parse structured rejection reason string into displayable components.
 *
 * Handles various formats gracefully:
 * 1. Splits by ';' to separate primary and secondary reasons
 * 2. Extracts rule type from parentheses using regex: /\(([^)]+)\)/
 * 3. Extracts actual vs threshold using regex: /(\d+\.?\d*x?)\s*([><]=?)\s*(\d+\.?\d*x?)/
 * 4. Builds structured object
 * 5. Returns parsed result with fallback to raw string
 *
 * @param rejectionReason - Raw rejection reason string from backend
 * @returns Parsed rejection reason object
 *
 * @example
 * ```typescript
 * const parsed = parseRejectionReason(
 *   "Volume Too High (Non-Negotiable Rule): 0.82x > 0.7x threshold; Test not confirmed: 0 bars vs 3-15 required"
 * )
 * console.log(parsed.primary.reason)       // "Volume Too High"
 * console.log(parsed.primary.ruleType)     // "Non-Negotiable Rule"
 * console.log(parsed.primary.actualValue)  // "0.82x"
 * console.log(parsed.secondary.length)     // 1
 * console.log(parsed.secondary[0].reason)  // "Test not confirmed"
 * ```
 */
export function parseRejectionReason(
  rejectionReason: string
): RejectionReasonParsed {
  // Handle empty or null
  if (!rejectionReason || rejectionReason.trim() === '') {
    return {
      primary: {
        reason: 'Unknown rejection',
        ruleType: '',
        actualValue: '',
        thresholdValue: '',
        comparison: '',
      },
      secondary: [],
      raw: rejectionReason || '',
    }
  }

  // Split by ';' to separate primary and secondary reasons
  const parts = rejectionReason.split(';').map((s) => s.trim())
  const primaryPart = parts[0] || ''
  const secondaryParts = parts.slice(1)

  // Parse primary reason
  const primary = parsePrimaryReason(primaryPart)

  // Parse secondary reasons
  const secondary = secondaryParts
    .filter((s) => s.length > 0)
    .map(parseSecondaryReason)
    .filter((s): s is RejectionSecondary => s !== null)

  return {
    primary,
    secondary,
    raw: rejectionReason,
  }
}

/**
 * Parse primary rejection reason.
 *
 * Extracts:
 * - Reason name (before first colon or parenthesis)
 * - Rule type (from parentheses)
 * - Comparison (after colon)
 * - Actual and threshold values (from comparison)
 *
 * @param primaryPart - Primary rejection reason string
 * @returns Parsed primary reason
 */
function parsePrimaryReason(primaryPart: string): RejectionPrimary {
  // Extract rule type from parentheses: /\(([^)]+)\)/
  const ruleTypeMatch = primaryPart.match(/\(([^)]+)\)/)
  const ruleType = ruleTypeMatch ? ruleTypeMatch[1] : ''

  // Extract reason (before parentheses or colon)
  let reason = primaryPart
  if (ruleTypeMatch) {
    // Remove rule type parentheses
    reason = primaryPart.substring(0, ruleTypeMatch.index).trim()
  }
  // Split by colon to separate reason from comparison
  const colonIndex = reason.indexOf(':')
  if (colonIndex > 0) {
    reason = reason.substring(0, colonIndex).trim()
  }

  // Extract comparison (after colon)
  const comparisonMatch = primaryPart.match(/:\s*(.+)$/)
  const comparison = comparisonMatch ? comparisonMatch[1].trim() : ''

  // Extract actual and threshold values from comparison
  // Pattern: /(\d+\.?\d*x?)\s*([><]=?)\s*(\d+\.?\d*x?)/
  const valuesMatch = comparison.match(
    /(\d+\.?\d*x?)\s*([><]=?)\s*(\d+\.?\d*x?)/
  )
  let actualValue = ''
  let thresholdValue = ''

  if (valuesMatch) {
    actualValue = valuesMatch[1]
    thresholdValue = valuesMatch[3]
  } else {
    // Try to extract just numbers from comparison
    const numbers = comparison.match(/\d+\.?\d*x?/g)
    if (numbers && numbers.length >= 2) {
      actualValue = numbers[0]
      thresholdValue = numbers[1]
    }
  }

  return {
    reason,
    ruleType,
    actualValue,
    thresholdValue,
    comparison,
  }
}

/**
 * Parse secondary rejection issue.
 *
 * Extracts reason name and details from "Reason: Details" format.
 *
 * @param secondaryPart - Secondary rejection reason string
 * @returns Parsed secondary reason or null if invalid
 */
function parseSecondaryReason(
  secondaryPart: string
): RejectionSecondary | null {
  // Split by first colon
  const colonIndex = secondaryPart.indexOf(':')
  if (colonIndex <= 0) {
    // No colon found, treat entire string as reason
    return {
      reason: secondaryPart.trim(),
      details: '',
    }
  }

  const reason = secondaryPart.substring(0, colonIndex).trim()
  const details = secondaryPart.substring(colonIndex + 1).trim()

  return {
    reason,
    details,
  }
}

/**
 * Get volume threshold for pattern type.
 *
 * Returns the Wyckoff phase-specific volume threshold for a pattern type.
 *
 * @param patternType - Pattern type (SPRING, UTAD, SOS, LPS, SC, AR, ST)
 * @returns Volume threshold ratio (e.g., 0.7 for Spring)
 */
export function getVolumeThreshold(patternType: string): number {
  const thresholds: Record<string, number> = {
    // Phase A patterns (Stopping Action)
    SC: 1.5, // Selling Climax: HIGH volume (panic selling)
    AR: 1.3, // Automatic Rally: HIGH volume (institutional buying)
    ST: 0.8, // Secondary Test: LOW volume (exhaustion confirmed)

    // Phase C patterns (Testing)
    SPRING: 0.7, // Spring: LOW volume (no selling pressure)

    // Phase D patterns (Markup Beginning)
    SOS: 1.3, // Sign of Strength: HIGH volume (breakout commitment)
    LPS: 0.8, // Last Point of Support: LOW volume (selling reduced)

    // Phase E patterns (Distribution)
    UTAD: 0.7, // Upthrust: LOW volume (weak demand)
  }

  return thresholds[patternType.toUpperCase()] || 1.0
}

/**
 * Get volume requirement type for pattern.
 *
 * Determines if pattern requires high or low volume based on Wyckoff principles.
 *
 * @param patternType - Pattern type (SPRING, UTAD, SOS, LPS, SC, AR, ST)
 * @returns 'high' or 'low'
 */
export function getVolumeRequirement(patternType: string): 'high' | 'low' {
  const highVolumePatterns = ['SC', 'AR', 'SOS']
  return highVolumePatterns.includes(patternType.toUpperCase()) ? 'high' : 'low'
}
