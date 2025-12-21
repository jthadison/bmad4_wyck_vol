"""
Pattern Labeling Tool (Story 12.2 Task 5)

Purpose:
--------
Interactive tool for manually labeling Wyckoff patterns in historical OHLCV data.
Allows users to mark pattern type, date, justification, and comprehensive Wyckoff
campaign context including prerequisites, confirmation, and failure reasons.

Usage:
------
    python backend/scripts/label_patterns.py --symbol AAPL --start-date 2020-01-01

Features:
---------
- Load OHLCV data from database or CSV
- Display patterns for visual inspection
- Validate entries against LabeledPattern Pydantic model
- Save incrementally to prevent data loss (JSON staging format)
- Export to Parquet for final dataset

Author: Story 12.2 Task 5 Subtask 5.1
"""

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

# Add backend/src to Python path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from models.backtest import LabeledPattern


def create_labeled_pattern_interactive() -> dict[str, Any]:
    """
    Interactively create a labeled pattern through CLI prompts.

    Returns:
        Dictionary of labeled pattern data (can be validated with LabeledPattern)
    """
    print("\n" + "=" * 80)
    print("LABELED PATTERN CREATION")
    print("=" * 80)

    # Core fields
    pattern_data = {}
    pattern_data["id"] = str(uuid4())
    pattern_data["symbol"] = input("Symbol (e.g., AAPL): ").strip().upper()
    date_str = input("Pattern date (YYYY-MM-DD HH:MM:SS UTC): ").strip()
    pattern_data["date"] = datetime.fromisoformat(date_str).replace(tzinfo=UTC).isoformat()

    print("\nPattern Types: SPRING, SOS, UTAD, LPS, FALSE_SPRING")
    pattern_data["pattern_type"] = input("Pattern type: ").strip().upper()

    pattern_data["confidence"] = int(input("Confidence (70-95): ").strip())
    pattern_data["correctness"] = input("Correctness (true/false): ").strip().lower() == "true"
    pattern_data["outcome_win"] = input("Outcome win (true/false): ").strip().lower() == "true"

    # Wyckoff context
    print("\nWyckoff Phase: A, B, C, D, E")
    pattern_data["phase"] = input("Phase: ").strip().upper()
    pattern_data["trading_range_id"] = input("Trading range ID: ").strip()

    # Trade parameters
    pattern_data["entry_price"] = input("Entry price: ").strip()
    pattern_data["stop_loss"] = input("Stop loss: ").strip()
    pattern_data["target_price"] = input("Target price: ").strip()
    pattern_data["volume_ratio"] = input("Volume ratio (e.g., 0.65): ").strip()
    pattern_data["spread_ratio"] = input("Spread ratio (e.g., 0.80): ").strip()

    # Documentation
    pattern_data["justification"] = input("Justification: ").strip()
    pattern_data["reviewer_verified"] = False

    # Wyckoff Campaign Context
    print("\n" + "-" * 80)
    print("WYCKOFF CAMPAIGN CONTEXT (CRITICAL)")
    print("-" * 80)

    campaign_id_str = input("Campaign ID (UUID, or leave blank to generate): ").strip()
    pattern_data["campaign_id"] = campaign_id_str if campaign_id_str else str(uuid4())

    print("Campaign Type: ACCUMULATION, DISTRIBUTION")
    pattern_data["campaign_type"] = input("Campaign type: ").strip().upper()

    print("Campaign Phase: A, B, C, D, E")
    pattern_data["campaign_phase"] = input("Campaign phase: ").strip().upper()

    pattern_data["phase_position"] = input(
        "Phase position (e.g., early Phase C, late Phase C): "
    ).strip()

    # Volume characteristics (JSON)
    vol_type = input("Volume type (climactic/diminishing/normal): ").strip()
    vol_ratio = input("Volume ratio: ").strip()
    pattern_data["volume_characteristics"] = {"type": vol_type, "ratio": float(vol_ratio)}

    # Spread characteristics (JSON)
    spread_type = input("Spread type (narrowing/widening/normal): ").strip()
    spread_ratio_val = input("Spread ratio: ").strip()
    pattern_data["spread_characteristics"] = {
        "type": spread_type,
        "ratio": float(spread_ratio_val),
    }

    pattern_data["sr_test_result"] = input(
        "S/R test result (e.g., support held, resistance broken): "
    ).strip()

    # Preliminary events (list)
    prelim_events = input("Preliminary events (comma-separated, e.g., PS,SC,AR): ").strip()
    pattern_data["preliminary_events"] = (
        [e.strip() for e in prelim_events.split(",")] if prelim_events else []
    )

    pattern_data["subsequent_confirmation"] = (
        input("Subsequent confirmation (true/false): ").strip().lower() == "true"
    )
    pattern_data["sequential_validity"] = (
        input("Sequential validity (true/false): ").strip().lower() == "true"
    )

    # False positive reason (optional)
    if not pattern_data["correctness"]:
        pattern_data["false_positive_reason"] = input(
            "False positive reason (e.g., wrong phase, no campaign): "
        ).strip()
    else:
        pattern_data["false_positive_reason"] = None

    # Timestamp
    pattern_data["created_at"] = datetime.now(UTC).isoformat()

    return pattern_data


def save_labeled_patterns_to_staging(patterns: list[dict[str, Any]], staging_file: Path) -> None:
    """
    Save labeled patterns to JSON staging file (incremental save).

    Args:
        patterns: List of pattern dictionaries
        staging_file: Path to JSON staging file
    """
    staging_file.parent.mkdir(parents=True, exist_ok=True)

    with open(staging_file, "w") as f:
        json.dump(patterns, f, indent=2, default=str)

    print(f"\n✅ Saved {len(patterns)} patterns to {staging_file}")


def load_labeled_patterns_from_staging(staging_file: Path) -> list[dict[str, Any]]:
    """
    Load labeled patterns from JSON staging file.

    Args:
        staging_file: Path to JSON staging file

    Returns:
        List of pattern dictionaries
    """
    if not staging_file.exists():
        return []

    with open(staging_file) as f:
        return json.load(f)


def validate_pattern(pattern_data: dict[str, Any]) -> bool:
    """
    Validate pattern data against LabeledPattern Pydantic model.

    Args:
        pattern_data: Pattern dictionary

    Returns:
        True if valid, False otherwise
    """
    try:
        LabeledPattern(**pattern_data)
        print("✅ Pattern data is valid!")
        return True
    except Exception as e:
        print(f"❌ Validation error: {e}")
        return False


def main():
    """Main labeling workflow."""
    parser = argparse.ArgumentParser(description="Label Wyckoff patterns for dataset creation")
    parser.add_argument("--symbol", type=str, default="AAPL", help="Symbol to label")
    parser.add_argument(
        "--staging-file",
        type=Path,
        default=Path("backend/tests/datasets/staging/labeled_patterns_staging.json"),
        help="Staging file path",
    )
    args = parser.parse_args()

    print("\n" + "=" * 80)
    print("WYCKOFF PATTERN LABELING TOOL (Story 12.2)")
    print("=" * 80)
    print(f"\nSymbol: {args.symbol}")
    print(f"Staging file: {args.staging_file}")

    # Load existing patterns
    patterns = load_labeled_patterns_from_staging(args.staging_file)
    print(f"\nExisting patterns in staging: {len(patterns)}")

    while True:
        print("\n" + "-" * 80)
        print("Options:")
        print("  1. Add new labeled pattern")
        print("  2. View existing patterns")
        print("  3. Save and exit")
        print("  4. Exit without saving")
        choice = input("\nChoice: ").strip()

        if choice == "1":
            pattern_data = create_labeled_pattern_interactive()
            if validate_pattern(pattern_data):
                patterns.append(pattern_data)
                print(f"\n✅ Added pattern! Total patterns: {len(patterns)}")

                # Auto-save every 5 patterns
                if len(patterns) % 5 == 0:
                    save_labeled_patterns_to_staging(patterns, args.staging_file)

        elif choice == "2":
            print(f"\n{len(patterns)} patterns in staging:")
            for i, p in enumerate(patterns, 1):
                print(
                    f"  {i}. {p['symbol']} - {p['pattern_type']} - "
                    f"{p['date']} - Correct: {p['correctness']}"
                )

        elif choice == "3":
            save_labeled_patterns_to_staging(patterns, args.staging_file)
            print("\n✅ Saved and exiting. Goodbye!")
            break

        elif choice == "4":
            print("\n❌ Exiting without saving. Goodbye!")
            break


if __name__ == "__main__":
    main()
