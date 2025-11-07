"""
Integration tests for SOS validator with historical false breakout data.

Tests AC 9: Historical false breakouts correctly rejected or flagged.

This module validates that the SOS validator correctly identifies known false
breakouts from historical market data.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from uuid import uuid4

import pytest

from src.models.ohlcv import OHLCVBar
from src.pattern_engine.validators.sos_validator import SOSValidator


# -------------------------------------------------------------------------
# Fixtures
# -------------------------------------------------------------------------


@pytest.fixture
def validator() -> SOSValidator:
    """Fixture for SOSValidator instance."""
    return SOSValidator()


@pytest.fixture
def false_breakout_fixtures() -> list[dict]:
    """
    Load false breakout fixtures from JSON file.

    Returns list of dictionaries with historical false breakout data.
    """
    fixtures_path = Path(__file__).parent.parent.parent / "fixtures" / "false_breakouts.json"
    with open(fixtures_path, "r") as f:
        return json.load(f)


def create_bar_from_fixture(fixture_data: dict) -> OHLCVBar:
    """
    Create OHLCVBar from fixture data.

    Parameters:
    -----------
    fixture_data: dict
        Fixture data from false_breakouts.json

    Returns:
    --------
    OHLCVBar
        Constructed bar from fixture data
    """
    return OHLCVBar(
        id=uuid4(),
        symbol=fixture_data["symbol"],
        timeframe="1d",
        timestamp=datetime.fromisoformat(fixture_data["timestamp"].replace("Z", "+00:00")),
        open=Decimal(fixture_data["open"]),
        high=Decimal(fixture_data["high"]),
        low=Decimal(fixture_data["low"]),
        close=Decimal(fixture_data["close"]),
        volume=int(fixture_data["volume"]),
        spread=Decimal(fixture_data["spread"]),
        volume_ratio=Decimal(fixture_data["volume_ratio"]),
        spread_ratio=Decimal(fixture_data["spread_ratio"]),
    )


# -------------------------------------------------------------------------
# Task 12: Integration test with historical false breakouts (AC 9)
# -------------------------------------------------------------------------


def test_historical_false_breakouts_rejected(
    validator: SOSValidator, false_breakout_fixtures: list[dict]
) -> None:
    """
    Test AC 9: Known false breakouts from historical data correctly rejected or flagged.

    This test validates that the SOS validator correctly identifies patterns
    associated with historical false breakouts:
    - Low volume (<1.5x) breakouts should be REJECTED
    - High volume with narrow spread should be flagged as SUSPICIOUS
    - Low volume + narrow spread should be flagged as SUSPICIOUS
    """
    correlation_id = "integration-test-false-breakouts"

    rejections = []
    suspicions = []
    passes = []

    for fixture_data in false_breakout_fixtures:
        bar = create_bar_from_fixture(fixture_data)
        volume_ratio = Decimal(fixture_data["volume_ratio"])
        spread_ratio = Decimal(fixture_data["spread_ratio"])

        # First check volume validation
        volume_valid, volume_rejection = validator.validate_sos_volume(
            bar, volume_ratio, correlation_id
        )

        if not volume_valid:
            # AC 9: Low-volume false breakouts should be rejected
            rejections.append({
                "symbol": fixture_data["symbol"],
                "description": fixture_data["description"],
                "volume_ratio": volume_ratio,
                "spread_ratio": spread_ratio,
                "rejection_reason": volume_rejection,
            })
            assert "insufficient confirmation" in volume_rejection
            assert "FR12" in volume_rejection
            continue

        # If volume passes, check combined validation
        is_valid, warning, result = validator.validate_sos_breakout(
            bar, volume_ratio, spread_ratio, correlation_id
        )

        if result.get("quality") in ["suspicious", "acceptable_with_warning"]:
            # AC 9: Patterns with warning signs should be flagged
            suspicions.append({
                "symbol": fixture_data["symbol"],
                "description": fixture_data["description"],
                "volume_ratio": volume_ratio,
                "spread_ratio": spread_ratio,
                "quality": result["quality"],
                "confidence_impact": result["confidence_impact"],
                "warnings": result["warnings"],
            })
        else:
            passes.append({
                "symbol": fixture_data["symbol"],
                "description": fixture_data["description"],
                "volume_ratio": volume_ratio,
                "spread_ratio": spread_ratio,
                "quality": result["quality"],
            })

    # Assertions: Verify validator correctly identified problem patterns
    print("\n=== Historical False Breakout Analysis ===")
    print(f"Total fixtures: {len(false_breakout_fixtures)}")
    print(f"Rejected (volume < 1.5x): {len(rejections)}")
    print(f"Flagged as suspicious: {len(suspicions)}")
    print(f"Passed validation: {len(passes)}")

    # Print details
    if rejections:
        print("\n--- Rejected (FR12 Enforcement) ---")
        for rejection in rejections:
            print(f"  {rejection['symbol']}: {rejection['description']}")
            print(
                f"    Volume: {rejection['volume_ratio']}x, "
                f"Spread: {rejection['spread_ratio']}x"
            )
            print(f"    Reason: {rejection['rejection_reason']}")

    if suspicions:
        print("\n--- Flagged as Suspicious ---")
        for suspicion in suspicions:
            print(f"  {suspicion['symbol']}: {suspicion['description']}")
            print(
                f"    Volume: {suspicion['volume_ratio']}x, "
                f"Spread: {suspicion['spread_ratio']}x"
            )
            print(
                f"    Quality: {suspicion['quality']}, "
                f"Confidence: {suspicion['confidence_impact']}"
            )
            print(f"    Warnings: {suspicion['warnings']}")

    if passes:
        print("\n--- Passed Validation (but historically failed) ---")
        for passed in passes:
            print(f"  {passed['symbol']}: {passed['description']}")
            print(
                f"    Volume: {passed['volume_ratio']}x, "
                f"Spread: {passed['spread_ratio']}x"
            )
            print(f"    Quality: {passed['quality']}")

    # AC 9: Most false breakouts should be either rejected or flagged
    total_caught = len(rejections) + len(suspicions)
    catch_rate = total_caught / len(false_breakout_fixtures) * 100

    print("\n=== Summary ===")
    print(f"Catch rate: {catch_rate:.1f}% ({total_caught}/{len(false_breakout_fixtures)})")

    # We expect at least 80% of false breakouts to be caught (rejected or flagged)
    assert catch_rate >= 80.0, (
        f"Validator should catch at least 80% of false breakouts, got {catch_rate:.1f}%"
    )


def test_specific_false_breakout_aapl_low_volume(validator: SOSValidator) -> None:
    """
    Test specific case: AAPL false breakout with low volume (1.2x).

    This should be REJECTED per FR12.
    """
    # Arrange: AAPL 2023-03-15 - low volume breakout
    bar = OHLCVBar(
        id=uuid4(),
        symbol="AAPL",
        timeframe="1d",
        timestamp=datetime(2023, 3, 15, 0, 0, 0, tzinfo=UTC),
        open=Decimal("150.00"),
        high=Decimal("152.50"),
        low=Decimal("149.80"),
        close=Decimal("151.00"),
        volume=45000000,
        spread=Decimal("2.70"),
        volume_ratio=Decimal("1.2"),
        spread_ratio=Decimal("1.1"),
    )

    # Act
    is_valid, rejection_reason = validator.validate_sos_volume(
        bar, bar.volume_ratio, "test-aapl-false-breakout"
    )

    # Assert: Should be rejected (volume < 1.5x)
    assert is_valid is False, "AAPL low-volume false breakout should be rejected"
    assert rejection_reason is not None
    assert "1.2" in rejection_reason or "1.20" in rejection_reason
    assert "insufficient confirmation" in rejection_reason
    assert "FR12" in rejection_reason


def test_specific_false_breakout_tsla_narrow_spread(validator: SOSValidator) -> None:
    """
    Test specific case: TSLA head-fake with narrow spread (0.9x).

    Volume passes (1.8x) but narrow spread should flag as SUSPICIOUS.
    """
    # Arrange: TSLA 2023-06-22 - narrow spread despite moderate volume
    bar = OHLCVBar(
        id=uuid4(),
        symbol="TSLA",
        timeframe="1d",
        timestamp=datetime(2023, 6, 22, 0, 0, 0, tzinfo=UTC),
        open=Decimal("260.00"),
        high=Decimal("265.00"),
        low=Decimal("259.50"),
        close=Decimal("264.00"),
        volume=95000000,
        spread=Decimal("5.50"),
        volume_ratio=Decimal("1.8"),
        spread_ratio=Decimal("0.9"),
    )

    # Act
    is_valid, warning, result = validator.validate_sos_breakout(
        bar, bar.volume_ratio, bar.spread_ratio, "test-tsla-false-breakout"
    )

    # Assert: Should pass volume but be flagged as suspicious
    assert is_valid is True, "Should pass volume validation (1.8x > 1.5x)"
    assert result["quality"] == "suspicious", (
        "Narrow spread (0.9x) should flag as suspicious"
    )
    assert warning is not None
    assert "absorption" in warning.lower() or "contraction" in warning.lower()


def test_specific_false_breakout_spy_low_volume_narrow_spread(
    validator: SOSValidator,
) -> None:
    """
    Test specific case: SPY with low volume (1.3x) + narrow spread (1.0x).

    This should be REJECTED due to volume < 1.5x.
    """
    # Arrange: SPY 2023-08-10 - low volume + narrow spread
    bar = OHLCVBar(
        id=uuid4(),
        symbol="SPY",
        timeframe="1d",
        timestamp=datetime(2023, 8, 10, 0, 0, 0, tzinfo=UTC),
        open=Decimal("445.00"),
        high=Decimal("447.50"),
        low=Decimal("444.80"),
        close=Decimal("446.00"),
        volume=42000000,
        spread=Decimal("2.70"),
        volume_ratio=Decimal("1.3"),
        spread_ratio=Decimal("1.0"),
    )

    # Act
    is_valid, rejection_reason = validator.validate_sos_volume(
        bar, bar.volume_ratio, "test-spy-false-breakout"
    )

    # Assert: Should be rejected (volume < 1.5x)
    assert is_valid is False, "SPY low-volume false breakout should be rejected"
    assert rejection_reason is not None
    assert "insufficient confirmation" in rejection_reason
    assert "FR12" in rejection_reason


def test_specific_false_breakout_nvda_distribution_trap(validator: SOSValidator) -> None:
    """
    Test specific case: NVDA with high volume (2.3x) but narrow spread (1.1x).

    This is a CRITICAL pattern: high volume with narrow spread suggests
    distribution/absorption at resistance. Should be flagged as SUSPICIOUS
    per REVISED logic in Task 5/8.
    """
    # Arrange: NVDA 2023-09-05 - high volume but narrow spread (distribution trap)
    bar = OHLCVBar(
        id=uuid4(),
        symbol="NVDA",
        timeframe="1d",
        timestamp=datetime(2023, 9, 5, 0, 0, 0, tzinfo=UTC),
        open=Decimal("480.00"),
        high=Decimal("485.00"),
        low=Decimal("479.00"),
        close=Decimal("483.00"),
        volume=280000000,
        spread=Decimal("6.00"),
        volume_ratio=Decimal("2.3"),
        spread_ratio=Decimal("1.1"),
    )

    # Act
    is_valid, warning, result = validator.validate_sos_breakout(
        bar, bar.volume_ratio, bar.spread_ratio, "test-nvda-distribution-trap"
    )

    # Assert: Should pass volume but be flagged with warning (REVISED logic)
    assert is_valid is True, "Should pass volume validation (2.3x > 1.5x)"
    # CRITICAL: High volume (2.3x) with narrow spread (1.1x) should be flagged
    assert result["quality"] in ["suspicious", "acceptable_with_warning"], (
        "High volume with narrow spread should be flagged (REVISED)"
    )
    assert result["confidence_impact"] in ["low", "low_moderate", "moderate_reduced"], (
        "Confidence should be reduced for narrow spread despite high volume"
    )
    assert warning is not None, "Should have warning about narrow spread"


def test_specific_false_breakout_msft_weak_breakout(validator: SOSValidator) -> None:
    """
    Test specific case: MSFT barely met minimum requirements (1.5x, 1.2x).

    This should PASS validation but with "acceptable" quality (not excellent).
    Demonstrates that validator correctly allows breakouts meeting minimum
    requirements, but doesn't give them high confidence.
    """
    # Arrange: MSFT 2023-10-18 - barely met minimum requirements
    bar = OHLCVBar(
        id=uuid4(),
        symbol="MSFT",
        timeframe="1d",
        timestamp=datetime(2023, 10, 18, 0, 0, 0, tzinfo=UTC),
        open=Decimal("330.00"),
        high=Decimal("333.00"),
        low=Decimal("329.50"),
        close=Decimal("332.00"),
        volume=18000000,
        spread=Decimal("3.50"),
        volume_ratio=Decimal("1.5"),
        spread_ratio=Decimal("1.2"),
    )

    # Act
    is_valid, warning, result = validator.validate_sos_breakout(
        bar, bar.volume_ratio, bar.spread_ratio, "test-msft-weak-breakout"
    )

    # Assert: Should pass validation (meets minimum requirements)
    assert is_valid is True, "Should pass validation (meets minimum requirements)"
    assert result["quality"] == "acceptable", (
        "Barely meeting minimums should be 'acceptable' quality"
    )
    assert result["confidence_impact"] == "standard", (
        "Confidence should be standard (not high)"
    )
    # Note: This demonstrates that validator allows breakouts meeting minimums,
    # but Story 6.5 (confidence scoring) will give them lower confidence scores
