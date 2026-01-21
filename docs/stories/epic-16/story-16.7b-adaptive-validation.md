# Story 16.7b: Adaptive Validation Rules & Regime Statistics

## Story Overview

**Story ID**: STORY-16.7b
**Epic**: Epic 16 - Advanced Analytics & Integration
**Status**: Ready for Review
**Priority**: Low
**Story Points**: 4
**Estimated Hours**: 4-5 hours

## User Story

**As a** Performance Analyst
**I want** adaptive validation rules based on market regime
**So that** campaign signals remain accurate across trending, ranging, and volatile markets

## Business Context

Wyckoff methodology works best in range-bound accumulation/distribution zones. In strong trending or high-volatility markets, false signals increase. Adapting validation rules based on market regime improves signal accuracy across all conditions.

**Value Proposition**: Maintain 95%+ signal accuracy across all market conditions by adapting detection rules.

## Acceptance Criteria

### Functional Requirements

1. **Adaptive Validation Rules**
   - [x] RANGING: Standard validation (no changes)
   - [x] TRENDING: Increase quality threshold (0.7 → 0.8)
   - [x] HIGH_VOLATILITY: Increase volume requirements (+20%)
   - [x] LOW_VOLATILITY: Relax volume requirements (-10%)

2. **Integration with Campaign Detector**
   - [x] Regime-aware validation in `IntradayCampaignDetector`
   - [x] Apply adaptive thresholds to pattern detection
   - [x] Log regime adjustments in campaign metadata

3. **Regime Statistics**
   - [x] Success rate by market regime
   - [x] Win rate analysis per regime
   - [x] Optimal entry regimes identified
   - [x] Regime transition warnings

4. **Reporting API**
   - [x] `get_regime_performance_report()` returns success metrics by regime
   - [x] Filter campaigns by regime
   - [x] Export regime statistics to JSON/CSV

### Technical Requirements

5. **Implementation**
   - [x] `_get_quality_threshold(regime)` method
   - [x] `_get_volume_multiplier(regime)` method
   - [x] Regime-aware campaign validation
   - [x] `RegimePerformanceAnalyzer` class

6. **Test Coverage**
   - [x] Test adaptive thresholds for all regimes
   - [x] Test regime performance statistics
   - [x] Maintain 85%+ coverage

### Non-Functional Requirements

7. **Performance**
   - [x] No significant overhead from adaptive rules
   - [x] Regime statistics cached for 1 hour

## Technical Design

```python
class IntradayCampaignDetector:
    """Campaign detector with regime-aware validation."""

    def _get_quality_threshold(self, regime: MarketRegime) -> float:
        """Get adaptive quality threshold based on regime."""
        if regime == MarketRegime.RANGING:
            return 0.7
        elif regime in [MarketRegime.TRENDING_UP, MarketRegime.TRENDING_DOWN]:
            return 0.8  # Higher bar in trending markets
        elif regime == MarketRegime.HIGH_VOLATILITY:
            return 0.75
        return 0.7

    def _get_volume_multiplier(self, regime: MarketRegime) -> float:
        """Get volume requirement multiplier based on regime."""
        if regime == MarketRegime.HIGH_VOLATILITY:
            return 1.2  # +20% volume required
        elif regime == MarketRegime.LOW_VOLATILITY:
            return 0.9  # -10% volume required
        return 1.0  # Standard

class RegimePerformanceAnalyzer:
    """Analyze campaign success by market regime."""

    def get_regime_statistics(self) -> Dict[MarketRegime, dict]:
        """Calculate win rate, avg R-multiple by regime."""
        stats = {}
        for regime in MarketRegime:
            campaigns = self._get_campaigns_by_regime(regime)
            stats[regime] = {
                "total_campaigns": len(campaigns),
                "win_rate": self._calculate_win_rate(campaigns),
                "avg_r_multiple": self._calculate_avg_r(campaigns),
            }
        return stats
```

## Dependencies

**Requires**: Story 16.7a (Market Regime Detection)

## Definition of Done

- [x] Adaptive validation rules working
- [x] Regime-aware campaign detection operational
- [x] Regime performance statistics available
- [x] All tests passing
- [ ] Code reviewed

---

## Dev Agent Record

### Agent Model Used
claude-opus-4-5-20251101

### File List

**New Files:**
- `backend/src/backtesting/regime_performance_analyzer.py` - RegimePerformanceAnalyzer class for regime statistics
- `backend/tests/backtesting/test_regime_adaptive_validation.py` - Unit tests for Story 16.7b (35 tests)

**Modified Files:**
- `backend/src/models/market_context.py` - Added LOW_VOLATILITY to MarketRegime enum
- `backend/src/backtesting/intraday_campaign_detector.py` - Added adaptive validation methods and regime tracking
- `backend/src/backtesting/__init__.py` - Export RegimePerformanceAnalyzer

### Change Log

1. **MarketRegime Enum Extension**
   - Added `LOW_VOLATILITY` enum value for low volatility market conditions

2. **IntradayCampaignDetector Enhancements**
   - Added `REGIME_QUALITY_THRESHOLDS` constant mapping regimes to quality thresholds
   - Added `REGIME_VOLUME_MULTIPLIERS` constant mapping regimes to volume multipliers
   - Added `REGIME_STATS_CACHE_TTL_SECONDS` constant (1 hour cache)
   - Added `market_regime`, `regime_quality_threshold`, `regime_volume_multiplier` fields to Campaign dataclass
   - Added `_get_quality_threshold(regime)` method for adaptive quality thresholds
   - Added `_get_volume_multiplier(regime)` method for adaptive volume requirements
   - Added `set_campaign_regime(campaign, regime)` method to apply regime thresholds
   - Updated `add_pattern()` to accept `market_regime` parameter
   - Updated logging and event metadata to include regime information

3. **RegimePerformanceAnalyzer Class**
   - Analyzes campaign performance by market regime
   - `get_regime_statistics()` - Returns win rate, R-multiple, success rate by regime
   - `get_optimal_regime()` - Identifies best performing regime
   - `get_regime_transition_warning()` - Warns on regime transitions
   - `get_regime_performance_report()` - Comprehensive report generation
   - `export_to_json()` and `export_to_csv()` - Export statistics
   - `filter_campaigns_by_regime()` - Filter campaigns by regime
   - 1-hour cache TTL for statistics

### Test Results
- 35 new tests passing for Story 16.7b
- 76 existing intraday campaign tests passing (no regressions)

---

**Created**: 2026-01-18
**Split From**: Story 16.7
**Author**: AI Product Owner
**Implemented**: 2026-01-21
**Developer**: James (Dev Agent)
