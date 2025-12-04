"""
Historical UTAD Dataset Builder for Backtesting (Story 9.1)

This script fetches historical UTAD patterns from the database and classifies
their outcomes (VALID/FALSE/NEUTRAL) based on post-pattern price action.

Usage:
    python build_utad_backtest_dataset.py --months 12 --output dataset.csv
"""

import argparse
import sys
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Literal

import pandas as pd

# Add backend to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))


def fetch_historical_utads(start_date: datetime, end_date: datetime) -> list[dict]:
    """
    Query database for historical UTAD patterns.

    In production, this would query the pattern_repository for all UTAD patterns
    in the specified date range. For MVP, we create sample data.

    Args:
        start_date: Start of historical period
        end_date: End of historical period

    Returns:
        List of pattern dictionaries
    """
    # In production, this would be:
    # patterns = await pattern_repository.fetch_patterns(
    #     pattern_type="UTAD",
    #     start_date=start_date,
    #     end_date=end_date,
    #     include_near_misses=True,
    # )

    print(f"Fetching historical UTAD patterns from {start_date.date()} to {end_date.date()}")
    print("Note: Using sample data for MVP. Production would query database.")

    # Generate sample UTAD patterns for demonstration
    sample_patterns = []
    base_date = start_date

    # Create diverse sample patterns across sessions
    sessions = ["OVERLAP", "LONDON", "NY", "ASIAN"]
    symbols = ["EUR/USD", "GBP/JPY", "USD/CHF", "EUR/GBP", "AUD/USD"]
    volume_ratios = [2.0, 2.1, 2.2, 2.3, 2.4, 2.5, 2.6, 2.7, 2.8]

    pattern_id = 1
    for _ in range(100):  # Generate 100 sample patterns
        pattern = {
            "pattern_id": f"UTAD_{pattern_id}",
            "symbol": symbols[pattern_id % len(symbols)],
            "timestamp": base_date + timedelta(days=(pattern_id % 365)),
            "volume_ratio": volume_ratios[pattern_id % len(volume_ratios)],
            "session": sessions[pattern_id % len(sessions)],
            "utad_high": Decimal("1.1000"),
            "range_high": Decimal("1.0950"),
            "range_low": Decimal("1.0800"),
        }
        sample_patterns.append(pattern)
        pattern_id += 1

    return sample_patterns


def fetch_post_pattern_prices(pattern: dict, weeks_after: int = 4) -> list[dict]:
    """
    Query price data for specified period after pattern.

    In production, this would query the OHLCV repository. For MVP, we simulate outcomes.

    Args:
        pattern: Pattern dictionary
        weeks_after: Number of weeks to fetch

    Returns:
        List of OHLCV bar dictionaries
    """
    # In production:
    # bars = await ohlcv_repository.fetch_bars(
    #     symbol=pattern.symbol,
    #     start_date=pattern.timestamp,
    #     end_date=pattern.timestamp + timedelta(weeks=weeks_after),
    # )

    # Simulate outcomes based on volume ratio (for demonstration)
    # Higher volume ratios more likely to be valid UTADs
    volume_ratio = float(pattern["volume_ratio"])
    utad_high = pattern["utad_high"]
    range_low = pattern["range_low"]
    range_height = pattern["range_high"] - pattern["range_low"]

    # Simulate price action
    bars = []
    current_date = pattern["timestamp"]

    # Determine outcome based on volume ratio
    # This simulates realistic patterns for backtesting
    if volume_ratio >= 2.5:
        # High volume - likely valid UTAD (60% chance of decline)
        outcome_type = "decline" if (hash(pattern["pattern_id"]) % 10) < 6 else "rally"
    elif volume_ratio >= 2.2:
        # Medium-high volume - moderate probability (50% chance)
        outcome_type = "decline" if (hash(pattern["pattern_id"]) % 10) < 5 else "rally"
    elif volume_ratio >= 2.0:
        # Lower volume - less reliable (30% chance of decline)
        outcome_type = "decline" if (hash(pattern["pattern_id"]) % 10) < 3 else "neutral"
    else:
        # Very low volume - likely false signal
        outcome_type = "rally" if (hash(pattern["pattern_id"]) % 10) < 7 else "neutral"

    # Generate bars based on outcome
    for day in range(weeks_after * 7):
        bar_date = current_date + timedelta(days=day)

        if outcome_type == "decline":
            # Price declines below 50% of range
            low = range_low - (range_height * Decimal("0.3"))
        elif outcome_type == "rally":
            # Price rallies back above UTAD high
            high = utad_high + (range_height * Decimal("0.1"))
            low = range_low
        else:
            # Price stays in range
            high = pattern["range_high"]
            low = range_low

        bars.append(
            {
                "timestamp": bar_date,
                "low": low if outcome_type == "decline" else range_low,
                "high": high if outcome_type == "rally" else pattern["range_high"],
            }
        )

    return bars


def classify_utad_outcome(
    pattern: dict, price_bars: list[dict]
) -> Literal["VALID", "FALSE", "NEUTRAL"]:
    """
    Classify UTAD pattern outcome based on post-pattern price action.

    Classification Rules:
    - VALID: Price declined ≥50% of range within 4 weeks (distribution confirmed)
    - FALSE: Price rallied back above UTAD high within 4 weeks (distribution failed)
    - NEUTRAL: Price stayed within range (inconclusive)

    Args:
        pattern: Pattern dictionary
        price_bars: List of OHLCV bars after pattern

    Returns:
        Outcome classification
    """
    utad_high = pattern["utad_high"]
    range_high = pattern["range_high"]
    range_low = pattern["range_low"]
    range_height = range_high - range_low

    # Calculate 50% decline target
    decline_target = utad_high - (Decimal("0.5") * range_height)

    # Check price action
    for bar in price_bars:
        # Check for valid distribution (50% decline)
        if bar["low"] < decline_target:
            return "VALID"

        # Check for failed distribution (rally above UTAD high)
        if bar["high"] > utad_high:
            return "FALSE"

    # Price stayed within range
    return "NEUTRAL"


def save_dataset(patterns: list[dict], outcomes: list[str], output_path: Path) -> None:
    """
    Save dataset with pattern information and outcomes to CSV.

    Args:
        patterns: List of pattern dictionaries
        outcomes: List of outcome classifications
        output_path: Output file path
    """
    # Build DataFrame
    records = []
    for pattern, outcome in zip(patterns, outcomes, strict=False):
        records.append(
            {
                "pattern_id": pattern["pattern_id"],
                "symbol": pattern["symbol"],
                "timestamp": pattern["timestamp"],
                "volume_ratio": float(pattern["volume_ratio"]),
                "session": pattern["session"],
                "outcome": outcome,
            }
        )

    df = pd.DataFrame(records)

    # Create output directory
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Save to CSV
    df.to_csv(output_path, index=False)
    print(f"\n✓ Saved {len(df)} patterns to {output_path}")

    # Print summary statistics
    print("\nDataset Summary:")
    print(f"  Total patterns: {len(df)}")
    print(f"  VALID outcomes: {(df['outcome'] == 'VALID').sum()}")
    print(f"  FALSE outcomes: {(df['outcome'] == 'FALSE').sum()}")
    print(f"  NEUTRAL outcomes: {(df['outcome'] == 'NEUTRAL').sum()}")
    print("\nSession distribution:")
    print(df["session"].value_counts().to_string())


def main():
    """Main entry point for CLI."""
    parser = argparse.ArgumentParser(
        description="Build historical UTAD backtest dataset with outcomes"
    )
    parser.add_argument(
        "--months",
        type=int,
        default=12,
        help="Number of months of historical data (default: 12)",
    )
    parser.add_argument(
        "--output",
        type=str,
        default="docs/analysis/utad_backtest_dataset.csv",
        help="Output CSV file path",
    )
    parser.add_argument(
        "--weeks-after",
        type=int,
        default=4,
        help="Weeks after pattern to analyze outcomes (default: 4)",
    )

    args = parser.parse_args()

    # Calculate date range
    end_date = datetime.now(UTC)
    start_date = end_date - timedelta(days=args.months * 30)

    print("=" * 60)
    print("UTAD Backtest Dataset Builder (Story 9.1)")
    print("=" * 60)

    # Fetch historical patterns
    patterns = fetch_historical_utads(start_date, end_date)
    print(f"\nFound {len(patterns)} historical UTAD patterns")

    # Filter patterns with sufficient post-pattern data
    min_date = datetime.now(UTC) - timedelta(weeks=args.weeks_after)
    patterns = [p for p in patterns if p["timestamp"] < min_date]
    print(
        f"Filtered to {len(patterns)} patterns with {args.weeks_after}+ weeks of post-pattern data"
    )

    # Classify outcomes
    print(f"\nClassifying outcomes ({args.weeks_after} weeks post-pattern)...")
    outcomes = []

    for i, pattern in enumerate(patterns):
        if (i + 1) % 20 == 0:
            print(f"  Processed {i + 1}/{len(patterns)} patterns...")

        # Fetch post-pattern prices
        price_bars = fetch_post_pattern_prices(pattern, args.weeks_after)

        # Classify outcome
        outcome = classify_utad_outcome(pattern, price_bars)
        outcomes.append(outcome)

    print(f"  Processed {len(patterns)}/{len(patterns)} patterns... ✓")

    # Save dataset
    output_path = Path(args.output)
    save_dataset(patterns, outcomes, output_path)

    print("\n" + "=" * 60)
    print("Dataset build complete!")
    print("=" * 60)


if __name__ == "__main__":
    main()
