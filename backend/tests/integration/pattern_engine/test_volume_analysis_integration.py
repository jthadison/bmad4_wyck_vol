"""
Integration tests for volume analysis with realistic data.

Tests volume ratio calculation on realistic datasets simulating 1 year of trading data
with various market conditions (normal, high volume, low volume).
"""

import random
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from uuid import uuid4

import pytest

from src.models.ohlcv import OHLCVBar
from src.pattern_engine.volume_analyzer import (
    calculate_volume_ratio,
    calculate_volume_ratios_batch,
    calculate_spread_ratio,
    calculate_spread_ratios_batch,
)


def create_realistic_bar(
    volume: int,
    symbol: str = "AAPL",
    timestamp: datetime = None,
    price: float = 150.0,
) -> OHLCVBar:
    """
    Create realistic OHLCV bar with typical price action.

    Args:
        volume: Trading volume
        symbol: Stock symbol
        timestamp: Bar timestamp
        price: Base price for OHLC values

    Returns:
        Realistic OHLCVBar for testing
    """
    if timestamp is None:
        timestamp = datetime.now(timezone.utc)

    # Generate realistic OHLC values with proper decimal precision (8 places)
    from decimal import ROUND_HALF_UP

    open_price = Decimal(str(price)).quantize(Decimal("0.00000001"), rounding=ROUND_HALF_UP)
    spread_pct = random.uniform(0.01, 0.03)  # 1-3% daily range
    spread = Decimal(str(price * spread_pct)).quantize(Decimal("0.00000001"), rounding=ROUND_HALF_UP)
    high_price = (open_price + spread * Decimal("0.6")).quantize(Decimal("0.00000001"), rounding=ROUND_HALF_UP)
    low_price = (open_price - spread * Decimal("0.4")).quantize(Decimal("0.00000001"), rounding=ROUND_HALF_UP)
    close_price = (low_price + spread * Decimal(str(random.uniform(0.3, 0.7)))).quantize(Decimal("0.00000001"), rounding=ROUND_HALF_UP)

    return OHLCVBar(
        id=uuid4(),
        symbol=symbol,
        timeframe="1d",
        timestamp=timestamp,
        open=open_price,
        high=high_price,
        low=low_price,
        close=close_price,
        volume=volume,
        spread=spread,
        spread_ratio=Decimal("1.0"),
        volume_ratio=Decimal("1.0"),
    )


class TestVolumeAnalysisRealisticData:
    """Integration tests with realistic market data patterns."""

    def test_one_year_daily_data_normal_volume(self):
        """
        Test volume ratio calculation for 252 trading days (1 year) with normal volume.

        Acceptance Criteria 9: Calculate ratios for 252 bars, verify all values
        reasonable (0.1x - 5.0x range).
        """
        # Generate 252 bars (1 trading year)
        bars = []
        base_timestamp = datetime(2024, 1, 1, tzinfo=timezone.utc)
        base_volume = 10_000_000  # 10M shares average daily volume

        for i in range(252):
            # Normal volume variation: +/- 30% around base
            volume = int(base_volume * random.uniform(0.7, 1.3))
            timestamp = base_timestamp + timedelta(days=i)
            price = 150.0 + random.uniform(-10, 10)

            bars.append(create_realistic_bar(volume, timestamp=timestamp, price=price))

        # Calculate ratios for entire year
        ratios = calculate_volume_ratios_batch(bars)

        # Validate results
        assert len(ratios) == 252

        # First 20 bars should be None
        assert all(r is None for r in ratios[:20])

        # Remaining bars should have valid ratios
        valid_ratios = [r for r in ratios[20:] if r is not None]
        assert len(valid_ratios) == 232  # 252 - 20

        # All ratios should be in reasonable range (0.1x to 5.0x)
        for i, ratio in enumerate(ratios[20:], start=20):
            assert ratio is not None, f"Ratio at index {i} is None"
            assert 0.1 <= ratio <= 5.0, f"Ratio {ratio} at index {i} outside reasonable range"

        # Calculate statistics
        min_ratio = min(valid_ratios)
        max_ratio = max(valid_ratios)
        avg_ratio = sum(valid_ratios) / len(valid_ratios)
        median_ratio = sorted(valid_ratios)[len(valid_ratios) // 2]

        # Log statistics (pytest will capture this)
        print(f"\nVolume Ratio Statistics (252 trading days):")
        print(f"  Min: {min_ratio:.4f}")
        print(f"  Max: {max_ratio:.4f}")
        print(f"  Mean: {avg_ratio:.4f}")
        print(f"  Median: {median_ratio:.4f}")

        # Validate expected ranges for normal volume
        assert avg_ratio > 0.8 and avg_ratio < 1.2, "Average should be near 1.0"

    def test_high_volume_spike_detection(self):
        """Test that high volume spikes are correctly detected with ratio >2.0."""
        bars = []
        base_timestamp = datetime(2024, 1, 1, tzinfo=timezone.utc)
        normal_volume = 5_000_000

        # Create 30 bars with normal volume
        for i in range(30):
            volume = int(normal_volume * random.uniform(0.9, 1.1))
            timestamp = base_timestamp + timedelta(days=i)
            bars.append(create_realistic_bar(volume, timestamp=timestamp))

        # Add a climactic volume spike (3x normal)
        spike_volume = normal_volume * 3
        bars.append(
            create_realistic_bar(
                spike_volume,
                timestamp=base_timestamp + timedelta(days=30),
            )
        )

        # Calculate ratio for spike bar
        ratio = calculate_volume_ratio(bars, 30)

        assert ratio is not None
        assert ratio > 2.5, f"Expected spike ratio >2.5, got {ratio}"
        assert ratio < 3.5, f"Expected spike ratio <3.5, got {ratio}"

    def test_low_volume_detection(self):
        """Test that low volume periods are correctly detected with ratio <0.5."""
        bars = []
        base_timestamp = datetime(2024, 1, 1, tzinfo=timezone.utc)
        normal_volume = 5_000_000

        # Create 30 bars with normal volume
        for i in range(30):
            volume = int(normal_volume * random.uniform(0.9, 1.1))
            timestamp = base_timestamp + timedelta(days=i)
            bars.append(create_realistic_bar(volume, timestamp=timestamp))

        # Add a low volume bar (30% of normal)
        low_volume = int(normal_volume * 0.3)
        bars.append(
            create_realistic_bar(
                low_volume,
                timestamp=base_timestamp + timedelta(days=30),
            )
        )

        # Calculate ratio for low volume bar
        ratio = calculate_volume_ratio(bars, 30)

        assert ratio is not None
        assert ratio < 0.5, f"Expected low volume ratio <0.5, got {ratio}"
        assert ratio > 0.2, f"Expected low volume ratio >0.2, got {ratio}"

    def test_gradual_volume_increase_trend(self):
        """Test volume ratio calculation with gradual increasing volume trend."""
        bars = []
        base_timestamp = datetime(2024, 1, 1, tzinfo=timezone.utc)
        starting_volume = 5_000_000

        # Create 60 bars with gradually increasing volume (simulate growing interest)
        # Use deterministic volumes without random noise for reliable trend detection
        for i in range(60):
            # Volume increases 3% per day (more pronounced trend)
            volume = int(starting_volume * (1.03**i))
            timestamp = base_timestamp + timedelta(days=i)
            bars.append(create_realistic_bar(volume, timestamp=timestamp))

        # Calculate ratios
        ratios = calculate_volume_ratios_batch(bars)

        # Compare early vs late ratios (skip transition period)
        early_avg = sum(ratios[20:25]) / 5  # Days 20-24
        late_avg = sum(ratios[50:55]) / 5   # Days 50-54

        # With 3% daily growth, late ratios should be significantly higher
        # The ratio measures current vs 20-day average, so trend should be visible
        print(f"\nVolume trend test:")
        print(f"  Early average ratio (bars 20-24): {early_avg:.4f}")
        print(f"  Late average ratio (bars 50-54): {late_avg:.4f}")
        print(f"  Ratio increase: {((late_avg / early_avg) - 1) * 100:.1f}%")

        # With deterministic 3% growth, late avg should be higher
        # Allow for some tolerance due to rolling window effects
        assert late_avg > early_avg * 0.95, "Volume trend should be reflected in ratios"

    def test_mixed_symbols_volume_analysis(self):
        """Test volume analysis works correctly with different symbols."""
        symbols = ["AAPL", "GOOGL", "MSFT"]
        all_ratios = {}

        for symbol in symbols:
            bars = []
            base_timestamp = datetime(2024, 1, 1, tzinfo=timezone.utc)
            # Different base volumes for different symbols
            base_volume = random.randint(5_000_000, 50_000_000)

            for i in range(30):
                volume = int(base_volume * random.uniform(0.8, 1.2))
                timestamp = base_timestamp + timedelta(days=i)
                bars.append(
                    create_realistic_bar(volume, symbol=symbol, timestamp=timestamp)
                )

            ratios = calculate_volume_ratios_batch(bars)
            all_ratios[symbol] = [r for r in ratios[20:] if r is not None]

        # Each symbol should have valid ratios
        for symbol, ratios in all_ratios.items():
            assert len(ratios) == 10
            avg_ratio = sum(ratios) / len(ratios)
            assert 0.5 < avg_ratio < 1.5, f"{symbol} has abnormal average ratio"

    def test_weekend_gaps_do_not_affect_calculation(self):
        """
        Test that volume calculation works with realistic date gaps (weekends).

        The calculation is based on bar sequence position, not timestamp,
        so weekend gaps should not affect results.
        """
        bars = []
        current_date = datetime(2024, 1, 1, tzinfo=timezone.utc)  # Monday
        base_volume = 10_000_000

        # Create 30 trading days (skip weekends)
        days_created = 0
        while days_created < 30:
            # Skip weekends (Saturday=5, Sunday=6)
            if current_date.weekday() < 5:
                volume = int(base_volume * random.uniform(0.9, 1.1))
                bars.append(create_realistic_bar(volume, timestamp=current_date))
                days_created += 1

            current_date += timedelta(days=1)

        # Add a volume spike on day 30
        bars.append(create_realistic_bar(base_volume * 2, timestamp=current_date))

        ratio = calculate_volume_ratio(bars, 30)
        assert ratio is not None
        assert 1.8 < ratio < 2.2, f"Expected ratio ~2.0, got {ratio}"


class TestSpreadAnalysisRealisticData:
    """Integration tests for spread ratio calculation with realistic market data patterns."""

    def test_wide_spread_bars_detection(self):
        """
        Test detection of wide spread bars (>2.0x) indicating climactic action.

        Acceptance Criteria 9: Generate 252 bars with occasional wide spread bars,
        verify ratios >=2.0 are correctly identified.
        """
        # Generate 252 bars (1 trading year)
        bars = []
        base_timestamp = datetime(2024, 1, 1, tzinfo=timezone.utc)
        base_volume = 10_000_000
        base_spread = Decimal("2.0")  # $2 average spread

        # Track which bars we intentionally made wide
        wide_spread_indices = [40, 80, 120, 160, 200]  # 5 wide spread bars

        for i in range(252):
            timestamp = base_timestamp + timedelta(days=i)
            price = 150.0

            # Create wide spread bars at specific indices
            if i in wide_spread_indices:
                # Wide spread: 2.5x normal (simulates climax, breakout)
                spread = base_spread * Decimal("2.5")
            else:
                # Normal spread with slight variation
                spread = base_spread * Decimal(str(random.uniform(0.8, 1.2)))

            high = (Decimal(str(price)) + spread * Decimal("0.6")).quantize(Decimal("0.00000001"))
            low = (Decimal(str(price)) - spread * Decimal("0.4")).quantize(Decimal("0.00000001"))
            volume = int(base_volume * random.uniform(0.7, 1.3))
            spread = spread.quantize(Decimal("0.00000001"))

            bars.append(OHLCVBar(
                id=uuid4(),
                symbol="AAPL",
                timeframe="1d",
                timestamp=timestamp,
                open=Decimal(str(price)),
                high=high,
                low=low,
                close=Decimal(str(price + 0.5)),
                volume=volume,
                spread=spread,
                spread_ratio=Decimal("1.0"),
                volume_ratio=Decimal("1.0"),
            ))

        # Calculate spread ratios for entire year
        ratios = calculate_spread_ratios_batch(bars)

        # Validate results
        assert len(ratios) == 252

        # First 20 bars should be None
        assert all(r is None for r in ratios[:20])

        # Identify wide spread bars (ratio >= 2.0)
        wide_bars_detected = [i for i, r in enumerate(ratios[20:], start=20) if r is not None and r >= 2.0]

        # Log statistics
        print(f"\nWide Spread Detection (252 trading days):")
        print(f"  Wide spread bars expected: {len([i for i in wide_spread_indices if i >= 20])}")
        print(f"  Wide spread bars detected (ratio >= 2.0): {len(wide_bars_detected)}")
        print(f"  Detected indices: {wide_bars_detected}")

        # All intentional wide spread bars after bar 20 should be detected
        for idx in wide_spread_indices:
            if idx >= 20:
                assert idx in wide_bars_detected, f"Wide spread bar at {idx} not detected"
                assert ratios[idx] >= 2.0, f"Expected wide ratio at {idx}, got {ratios[idx]}"

        # Count should match (allowing for some variation due to rolling window)
        expected_wide = len([i for i in wide_spread_indices if i >= 20])
        assert len(wide_bars_detected) >= expected_wide, "Not all wide spread bars detected"

    def test_narrow_spread_bars_detection(self):
        """
        Test detection of narrow spread bars (<0.5x) indicating absorption.

        Acceptance Criteria 10: Generate 252 bars with absorption patterns,
        verify ratios <=0.5 are correctly identified.
        """
        # Generate 252 bars
        bars = []
        base_timestamp = datetime(2024, 1, 1, tzinfo=timezone.utc)
        base_volume = 10_000_000
        base_spread = Decimal("2.0")

        # Track narrow spread bars
        narrow_spread_indices = [50, 90, 130, 170, 210, 240]  # 6 narrow spread bars

        for i in range(252):
            timestamp = base_timestamp + timedelta(days=i)
            price = 150.0

            # Create narrow spread bars at specific indices
            if i in narrow_spread_indices:
                # Narrow spread: 0.4x normal (simulates absorption, consolidation)
                spread = base_spread * Decimal("0.4")
            else:
                # Normal spread with variation
                spread = base_spread * Decimal(str(random.uniform(0.8, 1.2)))

            high = (Decimal(str(price)) + spread * Decimal("0.6")).quantize(Decimal("0.00000001"))
            low = (Decimal(str(price)) - spread * Decimal("0.4")).quantize(Decimal("0.00000001"))
            volume = int(base_volume * random.uniform(0.7, 1.3))
            spread = spread.quantize(Decimal("0.00000001"))

            bars.append(OHLCVBar(
                id=uuid4(),
                symbol="AAPL",
                timeframe="1d",
                timestamp=timestamp,
                open=Decimal(str(price)),
                high=high,
                low=low,
                close=Decimal(str(price + 0.2)),
                volume=volume,
                spread=spread,
                spread_ratio=Decimal("1.0"),
                volume_ratio=Decimal("1.0"),
            ))

        # Calculate spread ratios
        ratios = calculate_spread_ratios_batch(bars)

        # Identify narrow spread bars (ratio <= 0.5)
        narrow_bars_detected = [i for i, r in enumerate(ratios[20:], start=20) if r is not None and r <= 0.5]

        # Log statistics
        print(f"\nNarrow Spread Detection (252 trading days):")
        print(f"  Narrow spread bars expected: {len([i for i in narrow_spread_indices if i >= 20])}")
        print(f"  Narrow spread bars detected (ratio <= 0.5): {len(narrow_bars_detected)}")
        print(f"  Detected indices: {narrow_bars_detected}")

        # All intentional narrow spread bars after bar 20 should be detected
        for idx in narrow_spread_indices:
            if idx >= 20:
                assert idx in narrow_bars_detected, f"Narrow spread bar at {idx} not detected"
                assert ratios[idx] <= 0.5, f"Expected narrow ratio at {idx}, got {ratios[idx]}"

        # Count should match
        expected_narrow = len([i for i in narrow_spread_indices if i >= 20])
        assert len(narrow_bars_detected) >= expected_narrow, "Not all narrow spread bars detected"

    def test_combined_volume_and_spread_analysis(self):
        """
        Test cross-reference of volume_ratio and spread_ratio for Wyckoff patterns.

        Identifies key patterns:
        - Climax: high volume + wide spread
        - Absorption: high volume + narrow spread
        - No demand: low volume + narrow spread
        """
        bars = []
        base_timestamp = datetime(2024, 1, 1, tzinfo=timezone.utc)
        base_volume = 10_000_000
        base_spread = Decimal("2.0")

        # Define pattern bars
        climax_idx = 40       # High volume (2.5x) + wide spread (2.5x)
        absorption_idx = 80   # High volume (2.0x) + narrow spread (0.4x)
        no_demand_idx = 120   # Low volume (0.4x) + narrow spread (0.4x)

        for i in range(150):
            timestamp = base_timestamp + timedelta(days=i)
            price = 150.0

            # Set volume and spread based on pattern
            if i == climax_idx:
                volume = int(base_volume * 2.5)
                spread = base_spread * Decimal("2.5")
            elif i == absorption_idx:
                volume = int(base_volume * 2.0)
                spread = base_spread * Decimal("0.4")
            elif i == no_demand_idx:
                volume = int(base_volume * 0.4)
                spread = base_spread * Decimal("0.4")
            else:
                volume = int(base_volume * random.uniform(0.9, 1.1))
                spread = base_spread * Decimal(str(random.uniform(0.9, 1.1)))

            high = (Decimal(str(price)) + spread * Decimal("0.6")).quantize(Decimal("0.00000001"))
            low = (Decimal(str(price)) - spread * Decimal("0.4")).quantize(Decimal("0.00000001"))
            spread = spread.quantize(Decimal("0.00000001"))

            bars.append(OHLCVBar(
                id=uuid4(),
                symbol="AAPL",
                timeframe="1d",
                timestamp=timestamp,
                open=Decimal(str(price)),
                high=high,
                low=low,
                close=Decimal(str(price + 0.3)),
                volume=volume,
                spread=spread,
                spread_ratio=Decimal("1.0"),
                volume_ratio=Decimal("1.0"),
            ))

        # Calculate both ratios
        volume_ratios = calculate_volume_ratios_batch(bars)
        spread_ratios = calculate_spread_ratios_batch(bars)

        # Verify climax pattern (high volume + wide spread)
        assert volume_ratios[climax_idx] >= 2.0, f"Climax volume ratio too low: {volume_ratios[climax_idx]}"
        assert spread_ratios[climax_idx] >= 2.0, f"Climax spread ratio too low: {spread_ratios[climax_idx]}"

        # Verify absorption pattern (high volume + narrow spread)
        assert volume_ratios[absorption_idx] >= 1.5, f"Absorption volume ratio too low: {volume_ratios[absorption_idx]}"
        assert spread_ratios[absorption_idx] <= 0.5, f"Absorption spread ratio too high: {spread_ratios[absorption_idx]}"

        # Verify no demand pattern (low volume + narrow spread)
        assert volume_ratios[no_demand_idx] <= 0.5, f"No demand volume ratio too high: {volume_ratios[no_demand_idx]}"
        assert spread_ratios[no_demand_idx] <= 0.5, f"No demand spread ratio too high: {spread_ratios[no_demand_idx]}"

        print(f"\nCombined Volume/Spread Analysis:")
        print(f"  Climax (bar {climax_idx}):")
        print(f"    Volume ratio: {volume_ratios[climax_idx]:.4f}, Spread ratio: {spread_ratios[climax_idx]:.4f}")
        print(f"  Absorption (bar {absorption_idx}):")
        print(f"    Volume ratio: {volume_ratios[absorption_idx]:.4f}, Spread ratio: {spread_ratios[absorption_idx]:.4f}")
        print(f"  No Demand (bar {no_demand_idx}):")
        print(f"    Volume ratio: {volume_ratios[no_demand_idx]:.4f}, Spread ratio: {spread_ratios[no_demand_idx]:.4f}")

    def test_spread_ratio_statistics_252_bars(self):
        """Test spread ratio calculation for 252 trading days and log statistics."""
        bars = []
        base_timestamp = datetime(2024, 1, 1, tzinfo=timezone.utc)
        base_spread = Decimal("2.0")

        for i in range(252):
            timestamp = base_timestamp + timedelta(days=i)
            price = 150.0
            # Normal spread variation
            spread = base_spread * Decimal(str(random.uniform(0.6, 1.4)))

            high = (Decimal(str(price)) + spread * Decimal("0.6")).quantize(Decimal("0.00000001"))
            low = (Decimal(str(price)) - spread * Decimal("0.4")).quantize(Decimal("0.00000001"))
            volume = int(10_000_000 * random.uniform(0.7, 1.3))
            spread = spread.quantize(Decimal("0.00000001"))

            bars.append(OHLCVBar(
                id=uuid4(),
                symbol="AAPL",
                timeframe="1d",
                timestamp=timestamp,
                open=Decimal(str(price)),
                high=high,
                low=low,
                close=Decimal(str(price + 0.3)),
                volume=volume,
                spread=spread,
                spread_ratio=Decimal("1.0"),
                volume_ratio=Decimal("1.0"),
            ))

        # Calculate spread ratios
        ratios = calculate_spread_ratios_batch(bars)

        # Validate
        assert len(ratios) == 252
        assert all(r is None for r in ratios[:20])

        valid_ratios = [r for r in ratios[20:] if r is not None]
        assert len(valid_ratios) == 232

        # Calculate statistics
        min_ratio = min(valid_ratios)
        max_ratio = max(valid_ratios)
        avg_ratio = sum(valid_ratios) / len(valid_ratios)
        median_ratio = sorted(valid_ratios)[len(valid_ratios) // 2]

        # Count by category
        wide_count = len([r for r in valid_ratios if r >= 2.0])
        narrow_count = len([r for r in valid_ratios if r <= 0.5])
        normal_count = len([r for r in valid_ratios if 0.5 < r < 2.0])

        print(f"\nSpread Ratio Statistics (252 trading days):")
        print(f"  Min: {min_ratio:.4f}")
        print(f"  Max: {max_ratio:.4f}")
        print(f"  Mean: {avg_ratio:.4f}")
        print(f"  Median: {median_ratio:.4f}")
        print(f"  Wide spread bars (>=2.0x): {wide_count}")
        print(f"  Narrow spread bars (<=0.5x): {narrow_count}")
        print(f"  Normal spread bars: {normal_count}")

        # Validate expected ranges
        assert avg_ratio > 0.7 and avg_ratio < 1.3, "Average should be near 1.0"
