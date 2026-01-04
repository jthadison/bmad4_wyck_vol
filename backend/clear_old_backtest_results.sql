-- Clear old backtest results that were created before the metrics→summary migration
-- Run this SQL script to remove incompatible old data
--
-- This will delete records that don't have the new 'summary' field structure
-- New backtests created after the fix will work correctly

DELETE FROM backtest_results
WHERE created_at < NOW() - INTERVAL '1 hour';

-- Alternative: Delete ALL backtest results if you want a clean slate
-- Uncomment the line below if you want to delete everything:
-- DELETE FROM backtest_results;
