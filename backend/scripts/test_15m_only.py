"""Quick test - 15m timeframe only"""
import asyncio
import sys
from pathlib import Path

backend_path = Path(__file__).parent.parent
sys.path.insert(0, str(backend_path))

from eurusd_multi_timeframe_backtest import EURUSDMultiTimeframeBacktest


async def main():
    backtest = EURUSDMultiTimeframeBacktest()

    # Test only 15m timeframe
    tf_code = "15m"
    tf_config = backtest.TIMEFRAMES[tf_code]

    print(f"Testing {tf_code} timeframe only...")
    result = await backtest.run_single_timeframe(tf_code, tf_config)

    # Print results
    backtest._print_timeframe_summary(tf_code, result)

    print(f"\n\n[SUCCESS] Backtest completed with {len(result.trades)} trades")


if __name__ == "__main__":
    asyncio.run(main())
