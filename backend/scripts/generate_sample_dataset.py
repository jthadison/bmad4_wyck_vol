"""
Generate Sample Labeled Pattern Dataset (Story 12.2 Task 5)

Purpose:
--------
Generate a realistic sample dataset of 200+ labeled Wyckoff patterns
for detector accuracy validation. This simulates manual labeling by
creating patterns with appropriate Wyckoff campaign context, including
both valid patterns and failure cases.

Usage:
------
    python backend/scripts/generate_sample_dataset.py

Output:
-------
    backend/tests/datasets/staging/labeled_patterns_staging.json

Features:
---------
- 40+ patterns per type (SPRING, SOS, UTAD, LPS, FALSE_SPRING)
- Balanced across symbols (AAPL, MSFT, GOOGL, TSLA)
- 80% correctness=True, 20% correctness=False (failure cases)
- Comprehensive Wyckoff campaign context
- Realistic price/volume/spread ratios

Author: Story 12.2 Task 5
"""

import json
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from uuid import uuid4

# Note: LabeledPattern model validation will be done separately in tests


def generate_spring_patterns(count: int, symbols: list[str]) -> list[dict]:
    """Generate SPRING pattern samples with campaign context."""
    patterns = []
    base_date = datetime(2023, 1, 1, tzinfo=UTC)

    for i in range(count):
        symbol = symbols[i % len(symbols)]
        is_correct = i < (count * 0.8)  # 80% correct, 20% failure cases

        campaign_id = uuid4()
        pattern_date = base_date + timedelta(days=i * 5)

        # Vary base price by symbol
        base_prices = {"AAPL": 170, "MSFT": 380, "GOOGL": 140, "TSLA": 250}
        base_price = base_prices.get(symbol, 150)

        if is_correct:
            # Valid Spring in Phase C
            pattern = {
                "id": str(uuid4()),
                "symbol": symbol,
                "date": pattern_date.isoformat(),
                "pattern_type": "SPRING",
                "confidence": 80 + (i % 16),  # 80-95
                "correctness": True,
                "outcome_win": True,
                "phase": "C",
                "trading_range_id": f"TR_{symbol}_{pattern_date.year}_Q{(pattern_date.month-1)//3+1}",
                "entry_price": f"{base_price + i * 0.5:.2f}",
                "stop_loss": f"{base_price + i * 0.5 - 5:.2f}",
                "target_price": f"{base_price + i * 0.5 + 15:.2f}",
                "volume_ratio": str(Decimal("0.65")),
                "spread_ratio": str(Decimal("0.80")),
                "justification": "Valid Spring in Phase C with SC/AR prerequisites, low volume test below Creek level",
                "reviewer_verified": i % 5 == 0,  # 20% verified
                "campaign_id": str(campaign_id),
                "campaign_type": "ACCUMULATION",
                "campaign_phase": "C",
                "phase_position": "late Phase C" if i % 2 == 0 else "mid Phase C",
                "volume_characteristics": {"type": "diminishing", "ratio": 0.65},
                "spread_characteristics": {"type": "narrowing", "ratio": 0.80},
                "sr_test_result": "support held at Creek level",
                "preliminary_events": ["PS", "SC", "AR"],
                "subsequent_confirmation": True,
                "sequential_validity": True,
                "false_positive_reason": None,
                "created_at": datetime.now(UTC).isoformat(),
            }
        else:
            # Failure case - wrong phase or missing prerequisites
            failure_types = [
                {
                    "phase": "A",
                    "campaign_phase": "A",
                    "sequential_validity": False,
                    "false_positive_reason": "Spring detected in Phase A instead of Phase C",
                    "preliminary_events": [],
                },
                {
                    "phase": "C",
                    "campaign_phase": "C",
                    "sequential_validity": False,
                    "false_positive_reason": "Spring without prior SC/AR events (missing prerequisites)",
                    "preliminary_events": ["PS"],
                },
                {
                    "phase": "C",
                    "campaign_phase": "C",
                    "sequential_validity": False,
                    "false_positive_reason": "Spring without subsequent SOS confirmation (failed pattern)",
                    "preliminary_events": ["PS", "SC", "AR"],
                },
            ]
            failure_case = failure_types[i % len(failure_types)]

            pattern = {
                "id": str(uuid4()),
                "symbol": symbol,
                "date": pattern_date.isoformat(),
                "pattern_type": "SPRING",
                "confidence": 70 + (i % 11),  # Lower confidence for failures
                "correctness": False,
                "outcome_win": False,
                "phase": failure_case["phase"],
                "trading_range_id": f"TR_{symbol}_{pattern_date.year}_Q{(pattern_date.month-1)//3+1}",
                "entry_price": f"{base_price + i * 0.5:.2f}",
                "stop_loss": f"{base_price + i * 0.5 - 5:.2f}",
                "target_price": f"{base_price + i * 0.5 + 15:.2f}",
                "volume_ratio": str(Decimal("0.90")),  # Higher volume (not diminishing)
                "spread_ratio": str(Decimal("1.20")),  # Wider spread
                "justification": f"False positive: {failure_case['false_positive_reason']}",
                "reviewer_verified": False,
                "campaign_id": str(campaign_id),
                "campaign_type": "ACCUMULATION",
                "campaign_phase": failure_case["campaign_phase"],
                "phase_position": "early Phase C",
                "volume_characteristics": {"type": "normal", "ratio": 0.90},
                "spread_characteristics": {"type": "normal", "ratio": 1.20},
                "sr_test_result": "failed test",
                "preliminary_events": failure_case["preliminary_events"],
                "subsequent_confirmation": False,
                "sequential_validity": failure_case["sequential_validity"],
                "false_positive_reason": failure_case["false_positive_reason"],
                "created_at": datetime.now(UTC).isoformat(),
            }

        patterns.append(pattern)

    return patterns


def generate_sos_patterns(count: int, symbols: list[str]) -> list[dict]:
    """Generate SOS (Sign of Strength) pattern samples."""
    patterns = []
    base_date = datetime(2023, 3, 1, tzinfo=UTC)

    for i in range(count):
        symbol = symbols[i % len(symbols)]
        is_correct = i < (count * 0.8)

        campaign_id = uuid4()
        pattern_date = base_date + timedelta(days=i * 5)

        base_prices = {"AAPL": 175, "MSFT": 385, "GOOGL": 145, "TSLA": 255}
        base_price = base_prices.get(symbol, 155)

        if is_correct:
            # Valid SOS in Phase D
            pattern = {
                "id": str(uuid4()),
                "symbol": symbol,
                "date": pattern_date.isoformat(),
                "pattern_type": "SOS",
                "confidence": 82 + (i % 14),
                "correctness": True,
                "outcome_win": True,
                "phase": "D",
                "trading_range_id": f"TR_{symbol}_{pattern_date.year}_Q{(pattern_date.month-1)//3+1}",
                "entry_price": f"{base_price + i * 0.6:.2f}",
                "stop_loss": f"{base_price + i * 0.6 - 8:.2f}",
                "target_price": f"{base_price + i * 0.6 + 20:.2f}",
                "volume_ratio": str(Decimal("1.80")),  # >1.5x volume
                "spread_ratio": str(Decimal("1.40")),
                "justification": "Valid SOS breakout in Phase D with high volume above Ice level",
                "reviewer_verified": i % 5 == 0,
                "campaign_id": str(campaign_id),
                "campaign_type": "ACCUMULATION",
                "campaign_phase": "D",
                "phase_position": "early Phase D" if i % 2 == 0 else "mid Phase D",
                "volume_characteristics": {"type": "climactic", "ratio": 1.80},
                "spread_characteristics": {"type": "widening", "ratio": 1.40},
                "sr_test_result": "resistance broken at Ice level",
                "preliminary_events": ["PS", "SC", "AR", "SPRING"],
                "subsequent_confirmation": True,
                "sequential_validity": True,
                "false_positive_reason": None,
                "created_at": datetime.now(UTC).isoformat(),
            }
        else:
            # Failure case - insufficient volume or wrong phase
            pattern = {
                "id": str(uuid4()),
                "symbol": symbol,
                "date": pattern_date.isoformat(),
                "pattern_type": "SOS",
                "confidence": 72,
                "correctness": False,
                "outcome_win": False,
                "phase": "D",
                "trading_range_id": f"TR_{symbol}_{pattern_date.year}_Q{(pattern_date.month-1)//3+1}",
                "entry_price": f"{base_price + i * 0.6:.2f}",
                "stop_loss": f"{base_price + i * 0.6 - 8:.2f}",
                "target_price": f"{base_price + i * 0.6 + 20:.2f}",
                "volume_ratio": str(Decimal("1.20")),  # <1.5x (insufficient)
                "spread_ratio": str(Decimal("1.10")),
                "justification": "False positive: SOS with insufficient volume (<1.5x threshold)",
                "reviewer_verified": False,
                "campaign_id": str(campaign_id),
                "campaign_type": "ACCUMULATION",
                "campaign_phase": "D",
                "phase_position": "early Phase D",
                "volume_characteristics": {"type": "normal", "ratio": 1.20},
                "spread_characteristics": {"type": "normal", "ratio": 1.10},
                "sr_test_result": "weak breakout",
                "preliminary_events": ["PS", "SC", "AR"],
                "subsequent_confirmation": False,
                "sequential_validity": False,
                "false_positive_reason": "SOS with volume <1.5x threshold (binary rejection)",
                "created_at": datetime.now(UTC).isoformat(),
            }

        patterns.append(pattern)

    return patterns


def generate_utad_patterns(count: int, symbols: list[str]) -> list[dict]:
    """Generate UTAD (Upthrust After Distribution) pattern samples."""
    patterns = []
    base_date = datetime(2023, 6, 1, tzinfo=UTC)

    for i in range(count):
        symbol = symbols[i % len(symbols)]
        is_correct = i < (count * 0.8)

        campaign_id = uuid4()
        pattern_date = base_date + timedelta(days=i * 5)

        base_prices = {"AAPL": 180, "MSFT": 390, "GOOGL": 150, "TSLA": 260}
        base_price = base_prices.get(symbol, 160)

        if is_correct:
            # Valid UTAD in Distribution phase
            pattern = {
                "id": str(uuid4()),
                "symbol": symbol,
                "date": pattern_date.isoformat(),
                "pattern_type": "UTAD",
                "confidence": 78 + (i % 18),
                "correctness": True,
                "outcome_win": True,  # Win = target hit (downside for distribution)
                "phase": "C",
                "trading_range_id": f"TR_{symbol}_{pattern_date.year}_Q{(pattern_date.month-1)//3+1}",
                "entry_price": f"{base_price + i * 0.4:.2f}",
                "stop_loss": f"{base_price + i * 0.4 + 6:.2f}",
                "target_price": f"{base_price + i * 0.4 - 18:.2f}",
                "volume_ratio": str(Decimal("1.60")),
                "spread_ratio": str(Decimal("1.30")),
                "justification": "Valid UTAD in Distribution Phase C with high volume above Ice",
                "reviewer_verified": i % 5 == 0,
                "campaign_id": str(campaign_id),
                "campaign_type": "DISTRIBUTION",
                "campaign_phase": "C",
                "phase_position": "late Phase C" if i % 2 == 0 else "mid Phase C",
                "volume_characteristics": {"type": "climactic", "ratio": 1.60},
                "spread_characteristics": {"type": "widening", "ratio": 1.30},
                "sr_test_result": "false breakout above resistance",
                "preliminary_events": ["PSY", "BC", "AR"],
                "subsequent_confirmation": True,
                "sequential_validity": True,
                "false_positive_reason": None,
                "created_at": datetime.now(UTC).isoformat(),
            }
        else:
            # Failure case - UTAD in Accumulation campaign (wrong campaign type)
            pattern = {
                "id": str(uuid4()),
                "symbol": symbol,
                "date": pattern_date.isoformat(),
                "pattern_type": "UTAD",
                "confidence": 71,
                "correctness": False,
                "outcome_win": False,
                "phase": "C",
                "trading_range_id": f"TR_{symbol}_{pattern_date.year}_Q{(pattern_date.month-1)//3+1}",
                "entry_price": f"{base_price + i * 0.4:.2f}",
                "stop_loss": f"{base_price + i * 0.4 + 6:.2f}",
                "target_price": f"{base_price + i * 0.4 - 18:.2f}",
                "volume_ratio": str(Decimal("1.50")),
                "spread_ratio": str(Decimal("1.20")),
                "justification": "False positive: UTAD detected during Accumulation campaign",
                "reviewer_verified": False,
                "campaign_id": str(campaign_id),
                "campaign_type": "ACCUMULATION",  # WRONG campaign type
                "campaign_phase": "C",
                "phase_position": "mid Phase C",
                "volume_characteristics": {"type": "normal", "ratio": 1.50},
                "spread_characteristics": {"type": "normal", "ratio": 1.20},
                "sr_test_result": "test failed",
                "preliminary_events": ["PS", "SC"],
                "subsequent_confirmation": False,
                "sequential_validity": False,
                "false_positive_reason": "UTAD detected during Accumulation (should only occur in Distribution)",
                "created_at": datetime.now(UTC).isoformat(),
            }

        patterns.append(pattern)

    return patterns


def generate_lps_patterns(count: int, symbols: list[str]) -> list[dict]:
    """Generate LPS (Last Point of Support) pattern samples."""
    patterns = []
    base_date = datetime(2023, 9, 1, tzinfo=UTC)

    for i in range(count):
        symbol = symbols[i % len(symbols)]
        is_correct = i < (count * 0.8)

        campaign_id = uuid4()
        pattern_date = base_date + timedelta(days=i * 5)

        base_prices = {"AAPL": 185, "MSFT": 395, "GOOGL": 155, "TSLA": 265}
        base_price = base_prices.get(symbol, 165)

        if is_correct:
            # Valid LPS within 10 bars of SOS
            pattern = {
                "id": str(uuid4()),
                "symbol": symbol,
                "date": pattern_date.isoformat(),
                "pattern_type": "LPS",
                "confidence": 81 + (i % 15),
                "correctness": True,
                "outcome_win": True,
                "phase": "D",
                "trading_range_id": f"TR_{symbol}_{pattern_date.year}_Q{(pattern_date.month-1)//3+1}",
                "entry_price": f"{base_price + i * 0.7:.2f}",
                "stop_loss": f"{base_price + i * 0.7 - 7:.2f}",
                "target_price": f"{base_price + i * 0.7 + 22:.2f}",
                "volume_ratio": str(Decimal("0.90")),
                "spread_ratio": str(Decimal("0.85")),
                "justification": "Valid LPS within 10 bars of SOS, held above Ice level",
                "reviewer_verified": i % 5 == 0,
                "campaign_id": str(campaign_id),
                "campaign_type": "ACCUMULATION",
                "campaign_phase": "D",
                "phase_position": "mid Phase D",
                "volume_characteristics": {"type": "diminishing", "ratio": 0.90},
                "spread_characteristics": {"type": "narrowing", "ratio": 0.85},
                "sr_test_result": "support held above Ice level",
                "preliminary_events": ["PS", "SC", "AR", "SPRING", "SOS"],
                "subsequent_confirmation": True,
                "sequential_validity": True,
                "false_positive_reason": None,
                "created_at": datetime.now(UTC).isoformat(),
            }
        else:
            # Failure case - LPS without prior SOS
            pattern = {
                "id": str(uuid4()),
                "symbol": symbol,
                "date": pattern_date.isoformat(),
                "pattern_type": "LPS",
                "confidence": 70,
                "correctness": False,
                "outcome_win": False,
                "phase": "D",
                "trading_range_id": f"TR_{symbol}_{pattern_date.year}_Q{(pattern_date.month-1)//3+1}",
                "entry_price": f"{base_price + i * 0.7:.2f}",
                "stop_loss": f"{base_price + i * 0.7 - 7:.2f}",
                "target_price": f"{base_price + i * 0.7 + 22:.2f}",
                "volume_ratio": str(Decimal("1.00")),
                "spread_ratio": str(Decimal("1.00")),
                "justification": "False positive: LPS without prior SOS event",
                "reviewer_verified": False,
                "campaign_id": str(campaign_id),
                "campaign_type": "ACCUMULATION",
                "campaign_phase": "D",
                "phase_position": "early Phase D",
                "volume_characteristics": {"type": "normal", "ratio": 1.00},
                "spread_characteristics": {"type": "normal", "ratio": 1.00},
                "sr_test_result": "test failed",
                "preliminary_events": ["PS", "SC", "AR"],  # Missing SOS
                "subsequent_confirmation": False,
                "sequential_validity": False,
                "false_positive_reason": "LPS without prior SOS event (incorrect sequence)",
                "created_at": datetime.now(UTC).isoformat(),
            }

        patterns.append(pattern)

    return patterns


def generate_false_spring_patterns(count: int, symbols: list[str]) -> list[dict]:
    """Generate FALSE_SPRING pattern samples (high-volume breakdown)."""
    patterns = []
    base_date = datetime(2023, 11, 1, tzinfo=UTC)

    for i in range(count):
        symbol = symbols[i % len(symbols)]
        is_correct = i < (count * 0.8)

        campaign_id = uuid4()
        pattern_date = base_date + timedelta(days=i * 5)

        base_prices = {"AAPL": 190, "MSFT": 400, "GOOGL": 160, "TSLA": 270}
        base_price = base_prices.get(symbol, 170)

        # FALSE_SPRING is an intentional failure pattern (high-volume breakdown)
        pattern = {
            "id": str(uuid4()),
            "symbol": symbol,
            "date": pattern_date.isoformat(),
            "pattern_type": "FALSE_SPRING",
            "confidence": 75 + (i % 11),
            "correctness": is_correct,  # Some are correctly identified as false springs
            "outcome_win": False,  # FALSE_SPRING leads to losses
            "phase": "C",
            "trading_range_id": f"TR_{symbol}_{pattern_date.year}_Q{(pattern_date.month-1)//3+1}",
            "entry_price": f"{base_price + i * 0.3:.2f}",
            "stop_loss": f"{base_price + i * 0.3 - 4:.2f}",
            "target_price": f"{base_price + i * 0.3 + 12:.2f}",
            "volume_ratio": str(Decimal("1.80")),  # HIGH volume (not diminishing)
            "spread_ratio": str(Decimal("1.50")),
            "justification": "False Spring with high volume breakdown (failed accumulation test)",
            "reviewer_verified": i % 5 == 0,
            "campaign_id": str(campaign_id),
            "campaign_type": "ACCUMULATION",
            "campaign_phase": "C",
            "phase_position": "late Phase C",
            "volume_characteristics": {"type": "climactic", "ratio": 1.80},
            "spread_characteristics": {"type": "widening", "ratio": 1.50},
            "sr_test_result": "support failed (breakdown)",
            "preliminary_events": ["PS", "SC", "AR"],
            "subsequent_confirmation": False,
            "sequential_validity": True if is_correct else False,
            "false_positive_reason": None
            if is_correct
            else "Misclassified as valid Spring (high volume indicates failure)",
            "created_at": datetime.now(UTC).isoformat(),
        }

        patterns.append(pattern)

    return patterns


def main():
    """Generate complete labeled pattern dataset."""
    print("=" * 80)
    print("GENERATING LABELED PATTERN DATASET (Story 12.2)")
    print("=" * 80)

    symbols = ["AAPL", "MSFT", "GOOGL", "TSLA"]

    all_patterns = []

    # Generate 50 patterns per type (total 250 patterns)
    print("\nGenerating SPRING patterns...")
    all_patterns.extend(generate_spring_patterns(50, symbols))

    print("Generating SOS patterns...")
    all_patterns.extend(generate_sos_patterns(50, symbols))

    print("Generating UTAD patterns...")
    all_patterns.extend(generate_utad_patterns(50, symbols))

    print("Generating LPS patterns...")
    all_patterns.extend(generate_lps_patterns(50, symbols))

    print("Generating FALSE_SPRING patterns...")
    all_patterns.extend(generate_false_spring_patterns(50, symbols))

    print(f"\n[OK] Generated {len(all_patterns)} total patterns")

    # Count by type
    from collections import Counter

    pattern_counts = Counter(p["pattern_type"] for p in all_patterns)
    print("\nPattern distribution:")
    for pattern_type, count in pattern_counts.items():
        print(f"  {pattern_type}: {count}")

    # Count correctness
    correct_count = sum(1 for p in all_patterns if p["correctness"])
    print("\nCorrectness distribution:")
    print(f"  Correct: {correct_count} ({correct_count/len(all_patterns)*100:.1f}%)")
    print(
        f"  Incorrect: {len(all_patterns)-correct_count} ({(len(all_patterns)-correct_count)/len(all_patterns)*100:.1f}%)"
    )

    # Save to staging file
    staging_dir = Path("backend/tests/datasets/staging")
    staging_dir.mkdir(parents=True, exist_ok=True)
    staging_file = staging_dir / "labeled_patterns_staging.json"

    with open(staging_file, "w") as f:
        json.dump(all_patterns, f, indent=2, default=str)

    print(f"\n[OK] Saved dataset to {staging_file}")
    print(f"File size: {staging_file.stat().st_size / 1024:.1f} KB")

    print("\n[OK] Dataset generation complete!")
    print("Note: Pattern validation against Pydantic model will be done in unit tests")


if __name__ == "__main__":
    main()
