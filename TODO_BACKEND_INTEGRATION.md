# TODO: Complete Backend Integration (P1-003)

## What's Done
- Added `volume_analysis: VolumeAnalysisSummary | None` field to BacktestResult model
- Imported VolumeAnalysisSummary from volume_logger

## What's Needed
1. In UnifiedBacktestEngine.__init__():
   - Instantiate VolumeLogger with appropriate max_entries

2. In UnifiedBacktestEngine bar processing loop:
   - Call volume_logger.validate_pattern_volume() for each signal
   - Call volume_logger.detect_volume_spike() for each bar
   - Call volume_logger.detect_volume_divergence() periodically

3. In UnifiedBacktestEngine result building:
   - Call volume_logger.get_summary()
   - Include in BacktestResult as volume_analysis=summary

## Files to Modify
- backend/src/backtesting/engine/backtest_engine.py (UnifiedBacktestEngine class)

## Testing
- Verify volume_analysis appears in API response
- Frontend VolumeAnalysisPanel should display data
- E2E test should validate full flow
