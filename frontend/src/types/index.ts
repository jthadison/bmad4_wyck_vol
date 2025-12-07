/**
 * Campaign Performance Tracking Types and Utilities
 *
 * Story 9.6 - Frontend TypeScript interfaces and decimal arithmetic helpers
 * Story 9.7 - Campaign Manager types for unified campaign management
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

// Export all campaign manager types (Story 9.7)
export type {
  EntryDetails,
  Campaign,
  AllocationPlan,
  CampaignStatusResponse,
  PatternType,
  WyckoffPhase,
  CampaignStatus,
} from "./campaign-manager";

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
