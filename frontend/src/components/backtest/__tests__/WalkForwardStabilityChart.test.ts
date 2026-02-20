/**
 * WalkForwardStabilityChart Component Tests (Feature 10)
 *
 * Test Coverage:
 * - Renders empty state when no windows
 * - Renders bars for each window
 * - Green bars for profitable OOS windows (oos_return > 0)
 * - Red bars for unprofitable OOS windows (oos_return <= 0)
 * - Renders IS Sharpe overlay line
 * - Legend is present
 *
 * ParameterStabilityHeatmap Tests:
 * - Renders parameter rows
 * - "Stable" label when all windows have same value
 * - "Variable" label when values differ
 *
 * WalkForwardRobustnessPanel Tests:
 * - Displays profitable window count
 * - Displays worst OOS drawdown
 * - Displays IS/OOS ratio
 * - Overfitting warning shown when ratio > 2
 * - No overfitting warning when ratio <= 2
 */

import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import WalkForwardStabilityChart from '@/components/backtest/WalkForwardStabilityChart.vue'
import ParameterStabilityHeatmap from '@/components/backtest/ParameterStabilityHeatmap.vue'
import WalkForwardRobustnessPanel from '@/components/backtest/WalkForwardRobustnessPanel.vue'
import type {
  WalkForwardWindow,
  RobustnessScore,
} from '@/services/walkForwardStabilityService'

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function makeWindow(
  idx: number,
  oosReturn: number,
  isSharpe: number,
  oosSharpe: number
): WalkForwardWindow {
  return {
    window_index: idx,
    is_start: '2022-01-01',
    is_end: '2022-06-30',
    oos_start: '2022-07-01',
    oos_end: '2022-09-30',
    is_sharpe: isSharpe,
    oos_sharpe: oosSharpe,
    is_return: 0.12,
    oos_return: oosReturn,
    is_drawdown: 0.06,
    oos_drawdown: 0.1,
    optimal_params: { lookback_days: 126 },
  }
}

const sampleWindows: WalkForwardWindow[] = [
  makeWindow(1, 0.08, 2.0, 1.4), // profitable OOS
  makeWindow(2, -0.03, 2.1, 1.2), // unprofitable OOS
  makeWindow(3, 0.05, 1.9, 1.5), // profitable OOS
]

// ---------------------------------------------------------------------------
// WalkForwardStabilityChart
// ---------------------------------------------------------------------------

describe('WalkForwardStabilityChart', () => {
  it('shows empty state when windows is empty', () => {
    const wrapper = mount(WalkForwardStabilityChart, {
      props: { windows: [] },
    })
    expect(wrapper.text()).toContain('No walk-forward window data available')
  })

  it('renders the chart SVG when windows are provided', () => {
    const wrapper = mount(WalkForwardStabilityChart, {
      props: { windows: sampleWindows },
    })
    expect(wrapper.find('svg').exists()).toBe(true)
  })

  it('renders one bar rect per window', () => {
    const wrapper = mount(WalkForwardStabilityChart, {
      props: { windows: sampleWindows },
    })
    // Each bar is a <rect> inside the SVG
    const rects = wrapper.findAll('rect')
    expect(rects.length).toBe(sampleWindows.length)
  })

  it('uses green fill for profitable OOS windows', () => {
    const wrapper = mount(WalkForwardStabilityChart, {
      props: { windows: [makeWindow(1, 0.05, 2.0, 1.4)] },
    })
    const rect = wrapper.find('rect')
    expect(rect.attributes('fill')).toBe('#22c55e')
  })

  it('uses red fill for unprofitable OOS windows', () => {
    const wrapper = mount(WalkForwardStabilityChart, {
      props: { windows: [makeWindow(1, -0.03, 2.0, 0.8)] },
    })
    const rect = wrapper.find('rect')
    expect(rect.attributes('fill')).toBe('#ef4444')
  })

  it('renders the IS Sharpe polyline overlay', () => {
    const wrapper = mount(WalkForwardStabilityChart, {
      props: { windows: sampleWindows },
    })
    expect(wrapper.find('polyline').exists()).toBe(true)
  })

  it('renders a legend with OOS Profitable, OOS Unprofitable, IS Sharpe', () => {
    const wrapper = mount(WalkForwardStabilityChart, {
      props: { windows: sampleWindows },
    })
    expect(wrapper.text()).toContain('OOS Profitable')
    expect(wrapper.text()).toContain('OOS Unprofitable')
    expect(wrapper.text()).toContain('IS Sharpe')
  })

  it('renders window labels (W1, W2, W3)', () => {
    const wrapper = mount(WalkForwardStabilityChart, {
      props: { windows: sampleWindows },
    })
    expect(wrapper.text()).toContain('W1')
    expect(wrapper.text()).toContain('W2')
    expect(wrapper.text()).toContain('W3')
  })
})

// ---------------------------------------------------------------------------
// ParameterStabilityHeatmap
// ---------------------------------------------------------------------------

describe('ParameterStabilityHeatmap', () => {
  it('shows empty state when parameterStability is empty', () => {
    const wrapper = mount(ParameterStabilityHeatmap, {
      props: { parameterStability: {}, windowCount: 3 },
    })
    expect(wrapper.text()).toContain('No parameter stability data available')
  })

  it('renders a row for each parameter', () => {
    const wrapper = mount(ParameterStabilityHeatmap, {
      props: {
        parameterStability: {
          lookback: [20, 20, 20],
          threshold: [0.02, 0.025, 0.02],
        },
        windowCount: 3,
      },
    })
    expect(wrapper.text()).toContain('lookback')
    expect(wrapper.text()).toContain('threshold')
  })

  it('labels row as "Stable" when all window values are identical', () => {
    const wrapper = mount(ParameterStabilityHeatmap, {
      props: {
        parameterStability: { lookback: [20, 20, 20] },
        windowCount: 3,
      },
    })
    expect(wrapper.text()).toContain('Stable')
  })

  it('labels row as "Variable" when window values differ', () => {
    const wrapper = mount(ParameterStabilityHeatmap, {
      props: {
        parameterStability: { threshold: [0.02, 0.025, 0.015] },
        windowCount: 3,
      },
    })
    expect(wrapper.text()).toContain('Variable')
  })

  it('renders window column headers', () => {
    const wrapper = mount(ParameterStabilityHeatmap, {
      props: {
        parameterStability: { lookback: [20, 15] },
        windowCount: 2,
      },
    })
    expect(wrapper.text()).toContain('W1')
    expect(wrapper.text()).toContain('W2')
  })
})

// ---------------------------------------------------------------------------
// WalkForwardRobustnessPanel
// ---------------------------------------------------------------------------

function makeScore(
  profitableWindowPct: number,
  worstOosDd: number,
  isOosRatio: number
): RobustnessScore {
  return {
    profitable_window_pct: profitableWindowPct,
    worst_oos_drawdown: worstOosDd,
    avg_is_oos_sharpe_ratio: isOosRatio,
  }
}

describe('WalkForwardRobustnessPanel', () => {
  it('displays profitable window count and total', () => {
    const wrapper = mount(WalkForwardRobustnessPanel, {
      props: {
        robustnessScore: makeScore(0.6667, 0.12, 1.4),
        windows: sampleWindows, // 3 windows
      },
    })
    expect(wrapper.text()).toContain('3') // total windows
    expect(wrapper.text()).toContain('Profitable Windows')
  })

  it('displays worst OOS drawdown formatted as percentage', () => {
    const wrapper = mount(WalkForwardRobustnessPanel, {
      props: {
        robustnessScore: makeScore(0.8, 0.15, 1.3),
        windows: sampleWindows,
      },
    })
    // 0.15 * 100 = 15.0%
    expect(wrapper.text()).toContain('15.0')
    expect(wrapper.text()).toContain('Worst OOS Drawdown')
  })

  it('displays IS/OOS Sharpe ratio', () => {
    const wrapper = mount(WalkForwardRobustnessPanel, {
      props: {
        robustnessScore: makeScore(0.8, 0.1, 1.45),
        windows: sampleWindows,
      },
    })
    expect(wrapper.text()).toContain('1.45')
    expect(wrapper.text()).toContain('IS/OOS Sharpe Ratio')
  })

  it('shows overfitting warning when IS/OOS ratio > 2', () => {
    const wrapper = mount(WalkForwardRobustnessPanel, {
      props: {
        robustnessScore: makeScore(0.7, 0.12, 2.5),
        windows: sampleWindows,
      },
    })
    expect(wrapper.text()).toContain('Possible Overfitting Detected')
  })

  it('does NOT show overfitting warning when IS/OOS ratio <= 2', () => {
    const wrapper = mount(WalkForwardRobustnessPanel, {
      props: {
        robustnessScore: makeScore(0.8, 0.1, 1.4),
        windows: sampleWindows,
      },
    })
    expect(wrapper.text()).not.toContain('Possible Overfitting Detected')
  })

  it('shows "Acceptable" label when ratio <= 1.5', () => {
    const wrapper = mount(WalkForwardRobustnessPanel, {
      props: {
        robustnessScore: makeScore(0.8, 0.1, 1.5),
        windows: sampleWindows,
      },
    })
    expect(wrapper.text()).toContain('Acceptable')
  })

  it('shows "Overfit" label when ratio > 2', () => {
    const wrapper = mount(WalkForwardRobustnessPanel, {
      props: {
        robustnessScore: makeScore(0.5, 0.2, 2.8),
        windows: sampleWindows,
      },
    })
    expect(wrapper.text()).toContain('Overfit')
  })

  it('renders robustness score meter bar', () => {
    const wrapper = mount(WalkForwardRobustnessPanel, {
      props: {
        robustnessScore: makeScore(0.8, 0.08, 1.3),
        windows: sampleWindows,
      },
    })
    // Meter bar has role="progressbar"
    expect(wrapper.find('[role="progressbar"]').exists()).toBe(true)
  })
})
