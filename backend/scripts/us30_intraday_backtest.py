"""
US30 Intraday Backtest - 1h and 15m Timeframes

Purpose:
--------
Test US30 (Dow Jones Industrial Average, I:DJI on Polygon.io) on intraday timeframes
to validate Phase 1 fixes:
1. Symbol mapping: US30 -> I:DJI
2. Decimal precision: Price quantization to 8 decimal places
3. Pattern detection on index data

Timeframes:
-----------
- 1h: 60-day lookback
- 15m: 30-day lookback

Expected Results:
-----------------
- Non-zero bars fetched from Polygon.io (symbol mapping working)
- Signals generated without Decimal precision errors
- Pattern detection on index prices (~40,000 level)
"""

import asyncio
import sys
from datetime import datetime, timedelta
from pathlib import Path

# Add backend to path
backend_path = Path(__file__).parent.parent
sys.path.insert(0, str(backend_path))

from src.backtesting.engine.wyckoff_detector import WyckoffSignalDetector
from src.market_data.adapters.polygon_adapter import PolygonAdapter
from src.models.ohlcv import OHLCVBar


async def fetch_us30_data(timeframe: str, days: int) -> list[OHLCVBar]:
    """Fetch US30 bars from Polygon.io with symbol mapping."""
    adapter = PolygonAdapter()

    # Symbol mapping should convert US30 -> I:DJI
    mapped_symbol = adapter._format_symbol("US30", None)
    print(f"   Symbol mapping: US30 -> {mapped_symbol}")

    end_date = datetime.now()
    start_date = end_date - timedelta(days=days)

    bars = await adapter.fetch_historical_bars(
        symbol="US30",  # User-facing symbol
        timeframe=timeframe,
        start_date=start_date,
        end_date=end_date,
    )

    return bars


async def run_us30_backtest(timeframe: str, days: int):
    """Run backtest on US30 for given timeframe."""
    print(f"\n{'='*80}")
    print(f"US30 {timeframe.upper()} Timeframe Backtest ({days} days)")
    print(f"{'='*80}")

    # Fetch data
    print("\n1. Fetching data from Polygon.io...")
    try:
        bars = await fetch_us30_data(timeframe, days)
        print(f"   [OK] Fetched {len(bars)} bars")

        if bars:
            print(f"   Price range: ${bars[0].close:,.2f} - ${bars[-1].close:,.2f}")
            print(f"   Date range: {bars[0].timestamp.date()} to {bars[-1].timestamp.date()}")
    except Exception as e:
        print(f"   [ERROR] Fetch error: {e}")
        return

    if not bars:
        print("   [WARNING] No bars returned - cannot proceed with backtest")
        return

    # Run pattern detection
    print("\n2. Running Wyckoff pattern detection...")
    detector = WyckoffSignalDetector(
        min_range_bars=30 if timeframe == "1h" else 50, volume_lookback=20, cooldown_bars=5
    )

    signals = []
    errors = []

    for i in range(len(bars)):
        try:
            signal = detector.detect(bars, i)
            if signal:
                signals.append(signal)
                # Verify decimal precision
                entry_decimals = abs(signal.entry_price.as_tuple().exponent)
                stop_decimals = abs(signal.stop_loss.as_tuple().exponent)
                target_decimals = abs(signal.primary_target.as_tuple().exponent)

                if any(d > 8 for d in [entry_decimals, stop_decimals, target_decimals]):
                    print(f"   [WARNING] Signal at index {i} has >8 decimals!")
        except Exception as e:
            errors.append((i, str(e)))

    print("   [OK] Analysis complete")
    print(f"   Bars analyzed: {len(bars)}")
    print(f"   Signals detected: {len(signals)}")
    print(f"   Errors encountered: {len(errors)}")

    # Report results
    print("\n3. Results:")
    print(f"   {'-'*76}")

    if signals:
        print("   Pattern Types:")
        from collections import Counter

        pattern_counts = Counter(s.pattern_type for s in signals)
        for pattern, count in pattern_counts.items():
            print(f"     - {pattern}: {count}")

        print("\n   Sample Signal (first detected):")
        s = signals[0]
        print(f"     Entry: ${s.entry_price:,.2f}")
        print(f"     Stop: ${s.stop_loss:,.2f}")
        print(f"     Target: ${s.primary_target:,.2f}")
        print(f"     R-multiple: {s.r_multiple}")
        print(f"     Pattern: {s.pattern_type}")
    else:
        print(f"   [INFO] No signals detected in {len(bars)} bars")
        print("      This may be expected for intraday Wyckoff patterns")

    if errors:
        print("\n   [WARNING] Errors encountered:")
        for idx, err in errors[:3]:
            print(f"     Bar {idx}: {err}")
        if len(errors) > 3:
            print(f"     ... and {len(errors) - 3} more")

    print(f"\n{'='*80}\n")


async def main():
    """Run US30 backtests on both timeframes."""
    print("\n" + "=" * 80)
    print("US30 INTRADAY BACKTEST - PHASE 1 VALIDATION")
    print("=" * 80)
    print("\nTesting:")
    print("  1. Symbol mapping: US30 -> I:DJI (Polygon.io)")
    print("  2. Decimal precision: All prices quantized to <=8 decimals")
    print("  3. Pattern detection: Wyckoff patterns on index data")

    # Test 1h timeframe
    await run_us30_backtest("1h", days=60)

    # Test 15m timeframe
    await run_us30_backtest("15m", days=30)

    print("US30 intraday backtest complete!")
    print("\nValidation:")
    print("  - If bars were fetched: Symbol mapping works [PASS]")
    print("  - If no decimal errors: Precision fix works [PASS]")
    print("  - Signal count is informational (intraday patterns are rare)")


if __name__ == "__main__":
    asyncio.run(main())
