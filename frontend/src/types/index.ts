/**
 * Campaign Performance Tracking Types and Utilities
 *
 * Story 9.6 - Frontend TypeScript interfaces and decimal arithmetic helpers
 */

// Export all campaign performance types
export type {
  PositionMetrics,
  CampaignMetrics,
  PnLPoint,
  PnLCurve,
  AggregatedMetrics,
  MetricsFilter,
} from "./campaign-performance";

export { WinLossStatus } from "./campaign-performance";

// Export all decimal utility functions
export {
  toBig,
  fromBig,
  formatDecimal,
  formatPercent,
  formatR,
  formatCurrency,
  calculatePercentChange,
  calculateR,
  sumDecimals,
  averageDecimals,
  compareDecimals,
  isPositive,
  isNegative,
  isZero,
  abs,
  minDecimal,
  maxDecimal,
} from "./decimal-utils";
