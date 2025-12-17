/**
 * Tooltip Configuration (Story 11.8a - Task 16)
 *
 * Centralized tooltip content for metrics and Wyckoff concepts.
 * Used with PrimeVue Tooltip directive throughout the application.
 */

export interface TooltipContent {
  text: string
  html?: string
}

/**
 * Tooltip content map for common metrics and concepts
 */
export const tooltipContent: Record<string, TooltipContent> = {
  // Performance Metrics
  winRate: {
    text: 'Win Rate',
    html: '<strong>Win Rate</strong><br/>Percentage of winning trades out of total closed trades. A higher win rate indicates more profitable outcomes.',
  },
  rMultiple: {
    text: 'R-Multiple',
    html: '<strong>R-Multiple</strong><br/>Ratio of profit/loss to initial risk. R-Multiple of 2.0 means you gained twice your initial risk. This is the primary Wyckoff performance metric.',
  },
  portfolioHeat: {
    text: 'Portfolio Heat',
    html: '<strong>Portfolio Heat</strong><br/>Total risk exposure across all open positions as a percentage of portfolio value. System warns at 6% and blocks new signals at 8%.',
  },
  confidenceScore: {
    text: 'Confidence Score',
    html: '<strong>Confidence Score</strong><br/>120-point scoring system evaluating pattern quality: Volume (40pts), Penetration (35pts), Recovery (25pts), plus Creek (+10pts) and Volume Trend (+10pts) bonuses. Signals ≥70% are high-confidence.',
  },
  maxDrawdown: {
    text: 'Max Drawdown',
    html: '<strong>Maximum Drawdown</strong><br/>Largest peak-to-trough decline in portfolio value. Measures worst-case scenario risk during losing streaks.',
  },
  sharpeRatio: {
    text: 'Sharpe Ratio',
    html: '<strong>Sharpe Ratio</strong><br/>Risk-adjusted return metric. Values above 1.0 are good, above 2.0 are excellent. Measures excess return per unit of risk.',
  },

  // Wyckoff Levels
  creek: {
    text: 'Creek',
    html: '<strong>Creek</strong><br/>Support level penetration in a Spring pattern. Price must break below support (Creek) by 0.5-2.0% and recover to confirm accumulation. Wyckoff reference point for stop placement.',
  },
  ice: {
    text: 'Ice',
    html: '<strong>Ice</strong><br/>Deep support violation exceeding 2.0% below the trading range. Indicates a failed Spring pattern and potential genuine breakdown. System rejects Springs with Ice violations.',
  },
  jump: {
    text: 'Jump',
    html: '<strong>Jump</strong><br/>Price spike above resistance during markup phase. Indicates strong demand and continuation of uptrend. Used to identify Sign of Strength (SOS) patterns.',
  },

  // Wyckoff Patterns
  spring: {
    text: 'Spring',
    html: '<strong>Spring</strong><br/>Phase C pattern testing support. Price breaks below Creek, shakes out weak hands, then recovers strongly on declining volume. Signals accumulation complete and markup imminent.',
  },
  utad: {
    text: 'UTAD',
    html: '<strong>Upthrust After Distribution (UTAD)</strong><br/>Phase C pattern testing resistance. Price breaks above resistance, attracts buyers, then fails on high volume. Signals distribution complete and markdown imminent.',
  },
  sos: {
    text: 'SOS',
    html: '<strong>Sign of Strength (SOS)</strong><br/>Phase D breakout confirming markup trend. High volume breakout above trading range resistance. First entry opportunity in new uptrend.',
  },
  lps: {
    text: 'LPS',
    html: '<strong>Last Point of Support (LPS)</strong><br/>Phase D throwback to prior resistance (now support). Low volume pullback offering second entry. Wyckoff professionals build positions across multiple LPS entries.',
  },

  // Wyckoff Phases
  phaseA: {
    text: 'Phase A',
    html: '<strong>Phase A: Stopping the Prior Trend</strong><br/>Preliminary Support (PS), Selling Climax (SC), Automatic Rally (AR), and Secondary Test (ST). Downtrend exhaustion and first signs of demand.',
  },
  phaseB: {
    text: 'Phase B',
    html: '<strong>Phase B: Building the Cause</strong><br/>Horizontal trading range with declining volume. Composite Operator accumulates position. Duration determines magnitude of future markup (Wyckoff Law of Cause and Effect).',
  },
  phaseC: {
    text: 'Phase C',
    html: '<strong>Phase C: The Test</strong><br/>Spring or UTAD tests range boundary. Final shakeout before trend. High-probability entry point.',
  },
  phaseD: {
    text: 'Phase D',
    html: '<strong>Phase D: Trend Emergence</strong><br/>SOS breakout and LPS entries. Professional markup phase. Multiple entry opportunities as trend develops.',
  },
  phaseE: {
    text: 'Phase E',
    html: '<strong>Phase E: Trend Confirmation</strong><br/>Public participation, high volume, parabolic moves. Distribution begins. Wyckoff professionals exit positions.',
  },

  // Risk Management
  structuralStop: {
    text: 'Structural Stop',
    html: '<strong>Structural Stop</strong><br/>Stop-loss placed at Wyckoff reference point (Creek, SC, PS). Invalidates pattern if hit. Typically 1-3% below entry.',
  },
  positionSize: {
    text: 'Position Size',
    html: '<strong>Position Size</strong><br/>Number of shares/contracts calculated to risk 1% of portfolio value. Scales automatically with account size and volatility.',
  },
  campaignRisk: {
    text: 'Campaign Risk',
    html: '<strong>Campaign Risk</strong><br/>Total risk across correlated positions in a symbol. Limited to 3% of portfolio (50% of 6% portfolio heat limit). Prevents over-concentration.',
  },

  // Volume Spread Analysis
  volumeRatio: {
    text: 'Volume Ratio',
    html: '<strong>Volume Ratio</strong><br/>Current volume divided by 20-bar average. Spring requires <1.0x (low volume), SOS requires >1.5x (high volume). Effort vs. Result analysis.',
  },
  spreadRatio: {
    text: 'Spread Ratio',
    html: '<strong>Spread Ratio</strong><br/>Bar range divided by Average True Range (ATR). Wide spread (>1.2x) with low volume = no supply. Narrow spread (<0.8x) with high volume = absorption.',
  },
  ultraHighVolume: {
    text: 'Ultra-High Volume',
    html: '<strong>Ultra-High Volume</strong><br/>Volume exceeding 2.0x average. Indicates institutional activity, climactic action, or professional accumulation/distribution.',
  },
}

/**
 * Get tooltip configuration for PrimeVue Tooltip directive
 */
export function getTooltipConfig(key: string): {
  value: string
  escape: boolean
  class?: string
} {
  const content = tooltipContent[key]

  if (!content) {
    console.warn(`Tooltip content not found for key: ${key}`)
    return {
      value: key,
      escape: true,
    }
  }

  return {
    value: content.html || content.text,
    escape: !content.html, // Don't escape if HTML content provided
    class: 'help-tooltip',
  }
}

/**
 * Helper to extract plain text from tooltip (for accessibility)
 */
export function getTooltipText(key: string): string {
  const content = tooltipContent[key]
  return content?.text || key
}
