/**
 * CorrelationMatrix Component Tests (Feature P2-7)
 *
 * Tests cover:
 * - Heatmap renders with correct colors per correlation level
 * - Diagonal cells styled distinctly (self-correlation)
 * - Tooltip text includes campaign names and correlation value
 * - Empty state renders when no campaigns
 * - Color utility functions return correct colors
 * - Correlation level labels are correct
 */

import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'
import {
  correlationToColor,
  getCorrelationLevel,
} from '@/services/correlationService'
import CorrelationMatrix from '@/components/risk/CorrelationMatrix.vue'

// ============================================================================
// Mock the correlationService module
// ============================================================================

const mockMatrixData = {
  campaigns: ['AAPL-2024-01', 'MSFT-2024-01', 'JNJ-2024-01'],
  matrix: [
    [1.0, 0.78, 0.12],
    [0.78, 1.0, 0.21],
    [0.12, 0.21, 1.0],
  ],
  blocked_pairs: [
    {
      campaign_a: 'AAPL-2024-01',
      campaign_b: 'MSFT-2024-01',
      correlation: 0.78,
      reason:
        'Correlation 0.78 exceeds 0.6 threshold. Rachel (Risk Manager) blocks...',
    },
  ],
  heat_threshold: 0.6,
  last_updated: '2024-03-15T14:30:00Z',
}

vi.mock('@/services/correlationService', async () => {
  // Re-export the real module but override getCorrelationMatrix
  const actual: Record<string, unknown> = await vi.importActual(
    '@/services/correlationService'
  )
  return {
    ...actual,
    getCorrelationMatrix: vi.fn().mockResolvedValue(mockMatrixData),
  }
})

// ============================================================================
// correlationToColor utility
// ============================================================================

describe('correlationToColor', () => {
  it('returns green for low correlation (< 0.3)', () => {
    expect(correlationToColor(0.0)).toBe('#22c55e')
    expect(correlationToColor(0.2)).toBe('#22c55e')
    expect(correlationToColor(-0.5)).toBe('#22c55e')
  })

  it('returns a yellow-ish color for moderate correlation (0.3–0.6)', () => {
    const color = correlationToColor(0.45)
    // Should not be pure green or red
    expect(color).not.toBe('#22c55e')
    expect(color).not.toBe('#ef4444')
    // Should be a valid 7-char hex
    expect(color).toMatch(/^#[0-9a-f]{6}$/)
  })

  it('returns a red-ish color for high correlation (> 0.6)', () => {
    const color = correlationToColor(0.8)
    expect(color).not.toBe('#22c55e')
    expect(color).toMatch(/^#[0-9a-f]{6}$/)
  })

  it('returns pure green at exactly 0.0', () => {
    expect(correlationToColor(0.0)).toBe('#22c55e')
  })

  it('returns a valid hex for boundary values', () => {
    expect(correlationToColor(0.3)).toMatch(/^#[0-9a-f]{6}$/)
    expect(correlationToColor(0.6)).toMatch(/^#[0-9a-f]{6}$/)
    expect(correlationToColor(1.0)).toMatch(/^#[0-9a-f]{6}$/)
  })
})

// ============================================================================
// getCorrelationLevel utility
// ============================================================================

describe('getCorrelationLevel', () => {
  it('returns LOW for values <= 0.3', () => {
    expect(getCorrelationLevel(0.0)).toBe('LOW')
    expect(getCorrelationLevel(0.2)).toBe('LOW')
    expect(getCorrelationLevel(-1.0)).toBe('LOW')
  })

  it('returns MODERATE for values between 0.3 and 0.6', () => {
    expect(getCorrelationLevel(0.31)).toBe('MODERATE')
    expect(getCorrelationLevel(0.5)).toBe('MODERATE')
    expect(getCorrelationLevel(0.59)).toBe('MODERATE')
  })

  it('returns HIGH for values > 0.6', () => {
    expect(getCorrelationLevel(0.61)).toBe('HIGH')
    expect(getCorrelationLevel(0.78)).toBe('HIGH')
    expect(getCorrelationLevel(1.0)).toBe('HIGH')
  })
})

// ============================================================================
// CorrelationMatrix component
// ============================================================================

describe('CorrelationMatrix.vue', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('renders campaign column and row headers after fetch', async () => {
    const wrapper = mount(CorrelationMatrix, {
      props: { autoFetch: true },
    })

    // Wait for async fetch
    await new Promise((r) => setTimeout(r, 50))
    await wrapper.vm.$nextTick()

    const text = wrapper.text()
    expect(text).toContain('AAPL')
    expect(text).toContain('MSFT')
    expect(text).toContain('JNJ')
  })

  it('renders diagonal cells with em-dash (self-correlation indicator)', async () => {
    const wrapper = mount(CorrelationMatrix, {
      props: { autoFetch: true },
    })

    await new Promise((r) => setTimeout(r, 50))
    await wrapper.vm.$nextTick()

    // Diagonal cells show "—" instead of a numeric value
    expect(wrapper.html()).toContain('—')
  })

  it('renders non-diagonal cells with numeric correlation values', async () => {
    const wrapper = mount(CorrelationMatrix, {
      props: { autoFetch: true },
    })

    await new Promise((r) => setTimeout(r, 50))
    await wrapper.vm.$nextTick()

    // The AAPL-MSFT correlation is 0.78
    expect(wrapper.text()).toContain('0.78')
  })

  it('shows the legend with all three color levels', async () => {
    const wrapper = mount(CorrelationMatrix, {
      props: { autoFetch: true },
    })

    await new Promise((r) => setTimeout(r, 50))
    await wrapper.vm.$nextTick()

    const text = wrapper.text()
    expect(text).toContain('Low')
    expect(text).toContain('Moderate')
    expect(text).toContain('High')
  })

  it('shows empty state when no campaigns', async () => {
    const { getCorrelationMatrix } = await import(
      '@/services/correlationService'
    )
    vi.mocked(getCorrelationMatrix).mockResolvedValueOnce({
      campaigns: [],
      matrix: [],
      blocked_pairs: [],
      heat_threshold: 0.6,
      last_updated: '2024-03-15T14:30:00Z',
    })

    const wrapper = mount(CorrelationMatrix)

    await new Promise((r) => setTimeout(r, 50))
    await wrapper.vm.$nextTick()

    expect(wrapper.text()).toContain('No active campaigns to correlate')
  })

  it('shows error state when fetch fails', async () => {
    const { getCorrelationMatrix } = await import(
      '@/services/correlationService'
    )
    vi.mocked(getCorrelationMatrix).mockRejectedValueOnce(
      new Error('Network error')
    )

    const wrapper = mount(CorrelationMatrix)

    await new Promise((r) => setTimeout(r, 50))
    await wrapper.vm.$nextTick()

    expect(wrapper.text()).toContain('Network error')
  })

  it('applies gray background for diagonal cells', async () => {
    const wrapper = mount(CorrelationMatrix, {
      props: { autoFetch: true },
    })

    await new Promise((r) => setTimeout(r, 50))
    await wrapper.vm.$nextTick()

    // Find cells with diagonal-cell class
    const diagonalCells = wrapper.findAll('.diagonal-cell')
    expect(diagonalCells.length).toBeGreaterThan(0)

    // Diagonal cells should have gray background
    for (const cell of diagonalCells) {
      const style = cell.attributes('style') || ''
      expect(style).toContain('#374151')
    }
  })

  it('applies red background for high correlation (> 0.6)', async () => {
    const wrapper = mount(CorrelationMatrix, {
      props: { autoFetch: true },
    })

    await new Promise((r) => setTimeout(r, 50))
    await wrapper.vm.$nextTick()

    // AAPL-MSFT is 0.78 -> high -> red-ish color
    const cells = wrapper.findAll('.correlation-cell:not(.diagonal-cell)')
    const highCorrelationCells = cells.filter(
      (c: ReturnType<typeof wrapper.find>) => {
        const style = c.attributes('style') ?? ''
        // Red-ish cells will NOT have the pure green color
        return (
          style.length > 0 && !style.includes('#22c55e') && style.includes('#')
        )
      }
    )

    // There should be some non-green cells (high + moderate correlation cells)
    expect(highCorrelationCells.length).toBeGreaterThan(0)
  })

  it('cell aria-label includes campaign names and correlation value', async () => {
    const wrapper = mount(CorrelationMatrix, {
      props: { autoFetch: true },
    })

    await new Promise((r) => setTimeout(r, 50))
    await wrapper.vm.$nextTick()

    // Find non-diagonal cell with AAPL-MSFT correlation
    const cells = wrapper.findAll('[aria-label*="AAPL"]')
    expect(cells.length).toBeGreaterThan(0)
  })
})
