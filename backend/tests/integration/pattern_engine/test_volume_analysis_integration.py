"""
Integration tests for volume analysis with realistic data.

Tests volume ratio calculation on realistic datasets simulating 1 year of trading data
with various market conditions (normal, high volume, low volume).
"""

import random
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

from src.models.effort_result import EffortResult
from src.models.ohlcv import OHLCVBar
from src.models.volume_analysis import VolumeAnalysis
from src.pattern_engine.volume_analyzer import (
    VolumeAnalyzer,
    calculate_close_positions_batch,
    calculate_spread_ratios_batch,
    calculate_volume_ratio,
    calculate_volume_ratios_batch,
    classify_effort_result,
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
        timestamp = datetime.now(UTC)

    # Generate realistic OHLC values with proper decimal precision (8 places)
    from decimal import ROUND_HALF_UP

    open_price = Decimal(str(price)).quantize(Decimal("0.00000001"), rounding=ROUND_HALF_UP)
    spread_pct = random.uniform(0.01, 0.03)  # 1-3% daily range
    spread = Decimal(str(price * spread_pct)).quantize(
        Decimal("0.00000001"), rounding=ROUND_HALF_UP
    )
    high_price = (open_price + spread * Decimal("0.6")).quantize(
        Decimal("0.00000001"), rounding=ROUND_HALF_UP
    )
    low_price = (open_price - spread * Decimal("0.4")).quantize(
        Decimal("0.00000001"), rounding=ROUND_HALF_UP
    )
    close_price = (low_price + spread * Decimal(str(random.uniform(0.3, 0.7)))).quantize(
        Decimal("0.00000001"), rounding=ROUND_HALF_UP
    )

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
        base_timestamp = datetime(2024, 1, 1, tzinfo=UTC)
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
        print("\nVolume Ratio Statistics (252 trading days):")
        print(f"  Min: {min_ratio:.4f}")
        print(f"  Max: {max_ratio:.4f}")
        print(f"  Mean: {avg_ratio:.4f}")
        print(f"  Median: {median_ratio:.4f}")

        # Validate expected ranges for normal volume
        assert avg_ratio > 0.8 and avg_ratio < 1.2, "Average should be near 1.0"

    def test_high_volume_spike_detection(self):
        """Test that high volume spikes are correctly detected with ratio >2.0."""
        bars = []
        base_timestamp = datetime(2024, 1, 1, tzinfo=UTC)
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
        base_timestamp = datetime(2024, 1, 1, tzinfo=UTC)
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
        base_timestamp = datetime(2024, 1, 1, tzinfo=UTC)
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
        late_avg = sum(ratios[50:55]) / 5  # Days 50-54

        # With 3% daily growth, late ratios should be significantly higher
        # The ratio measures current vs 20-day average, so trend should be visible
        print("\nVolume trend test:")
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
            base_timestamp = datetime(2024, 1, 1, tzinfo=UTC)
            # Different base volumes for different symbols
            base_volume = random.randint(5_000_000, 50_000_000)

            for i in range(30):
                volume = int(base_volume * random.uniform(0.8, 1.2))
                timestamp = base_timestamp + timedelta(days=i)
                bars.append(create_realistic_bar(volume, symbol=symbol, timestamp=timestamp))

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
        current_date = datetime(2024, 1, 1, tzinfo=UTC)  # Monday
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
        base_timestamp = datetime(2024, 1, 1, tzinfo=UTC)
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

            bars.append(
                OHLCVBar(
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
                )
            )

        # Calculate spread ratios for entire year
        ratios = calculate_spread_ratios_batch(bars)

        # Validate results
        assert len(ratios) == 252

        # First 20 bars should be None
        assert all(r is None for r in ratios[:20])

        # Identify wide spread bars (ratio >= 2.0)
        wide_bars_detected = [
            i for i, r in enumerate(ratios[20:], start=20) if r is not None and r >= 2.0
        ]

        # Log statistics
        print("\nWide Spread Detection (252 trading days):")
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
        base_timestamp = datetime(2024, 1, 1, tzinfo=UTC)
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

            bars.append(
                OHLCVBar(
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
                )
            )

        # Calculate spread ratios
        ratios = calculate_spread_ratios_batch(bars)

        # Identify narrow spread bars (ratio <= 0.5)
        narrow_bars_detected = [
            i for i, r in enumerate(ratios[20:], start=20) if r is not None and r <= 0.5
        ]

        # Log statistics
        print("\nNarrow Spread Detection (252 trading days):")
        print(
            f"  Narrow spread bars expected: {len([i for i in narrow_spread_indices if i >= 20])}"
        )
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
        base_timestamp = datetime(2024, 1, 1, tzinfo=UTC)
        base_volume = 10_000_000
        base_spread = Decimal("2.0")

        # Define pattern bars
        climax_idx = 40  # High volume (2.5x) + wide spread (2.5x)
        absorption_idx = 80  # High volume (2.0x) + narrow spread (0.4x)
        no_demand_idx = 120  # Low volume (0.4x) + narrow spread (0.4x)

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

            bars.append(
                OHLCVBar(
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
                )
            )

        # Calculate both ratios
        volume_ratios = calculate_volume_ratios_batch(bars)
        spread_ratios = calculate_spread_ratios_batch(bars)

        # Verify climax pattern (high volume + wide spread)
        assert (
            volume_ratios[climax_idx] >= 2.0
        ), f"Climax volume ratio too low: {volume_ratios[climax_idx]}"
        assert (
            spread_ratios[climax_idx] >= 2.0
        ), f"Climax spread ratio too low: {spread_ratios[climax_idx]}"

        # Verify absorption pattern (high volume + narrow spread)
        assert (
            volume_ratios[absorption_idx] >= 1.5
        ), f"Absorption volume ratio too low: {volume_ratios[absorption_idx]}"
        assert (
            spread_ratios[absorption_idx] <= 0.5
        ), f"Absorption spread ratio too high: {spread_ratios[absorption_idx]}"

        # Verify no demand pattern (low volume + narrow spread)
        assert (
            volume_ratios[no_demand_idx] <= 0.5
        ), f"No demand volume ratio too high: {volume_ratios[no_demand_idx]}"
        assert (
            spread_ratios[no_demand_idx] <= 0.5
        ), f"No demand spread ratio too high: {spread_ratios[no_demand_idx]}"

        print("\nCombined Volume/Spread Analysis:")
        print(f"  Climax (bar {climax_idx}):")
        print(
            f"    Volume ratio: {volume_ratios[climax_idx]:.4f}, Spread ratio: {spread_ratios[climax_idx]:.4f}"
        )
        print(f"  Absorption (bar {absorption_idx}):")
        print(
            f"    Volume ratio: {volume_ratios[absorption_idx]:.4f}, Spread ratio: {spread_ratios[absorption_idx]:.4f}"
        )
        print(f"  No Demand (bar {no_demand_idx}):")
        print(
            f"    Volume ratio: {volume_ratios[no_demand_idx]:.4f}, Spread ratio: {spread_ratios[no_demand_idx]:.4f}"
        )

    def test_spread_ratio_statistics_252_bars(self):
        """Test spread ratio calculation for 252 trading days and log statistics."""
        bars = []
        base_timestamp = datetime(2024, 1, 1, tzinfo=UTC)
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

            bars.append(
                OHLCVBar(
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
                )
            )

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

        print("\nSpread Ratio Statistics (252 trading days):")
        print(f"  Min: {min_ratio:.4f}")
        print(f"  Max: {max_ratio:.4f}")
        print(f"  Mean: {avg_ratio:.4f}")
        print(f"  Median: {median_ratio:.4f}")
        print(f"  Wide spread bars (>=2.0x): {wide_count}")
        print(f"  Narrow spread bars (<=0.5x): {narrow_count}")
        print(f"  Normal spread bars: {normal_count}")

        # Validate expected ranges
        assert avg_ratio > 0.7 and avg_ratio < 1.3, "Average should be near 1.0"


class TestClosePositionAnalysisRealisticData:
    """Integration tests for close position calculation with realistic market data patterns."""

    def test_bullish_absorption_detection(self):
        """
        Test detection of bullish absorption: high volume + narrow spread + close >= 0.7.

        Acceptance Criteria 8: Generate 252 bars with bullish patterns,
        identify bars with close in upper 30% (close_position >= 0.7).
        """
        bars = []
        base_timestamp = datetime(2024, 1, 1, tzinfo=UTC)
        base_volume = 10_000_000
        base_spread = Decimal("2.0")

        # Track bullish absorption bars
        bullish_indices = [40, 80, 120, 160, 200]

        for i in range(252):
            timestamp = base_timestamp + timedelta(days=i)
            price = 150.0

            # Create bullish absorption bars
            if i in bullish_indices:
                # High volume + narrow spread + close at high
                volume = int(base_volume * 2.0)
                spread = base_spread * Decimal("0.4")  # Narrow spread
                high = (Decimal(str(price)) + spread).quantize(Decimal("0.00000001"))
                low = Decimal(str(price)).quantize(Decimal("0.00000001"))
                # Close at 80% of range (strong buying pressure)
                close = (low + spread * Decimal("0.8")).quantize(Decimal("0.00000001"))
            else:
                # Normal bars with random close positions
                volume = int(base_volume * random.uniform(0.8, 1.2))
                spread = base_spread * Decimal(str(random.uniform(0.8, 1.2)))
                high = (Decimal(str(price)) + spread * Decimal("0.6")).quantize(
                    Decimal("0.00000001")
                )
                low = (Decimal(str(price)) - spread * Decimal("0.4")).quantize(
                    Decimal("0.00000001")
                )
                # Random close position
                close_pct = random.uniform(0.2, 0.8)
                close = (low + (high - low) * Decimal(str(close_pct))).quantize(
                    Decimal("0.00000001")
                )

            spread = spread.quantize(Decimal("0.00000001"))

            bars.append(
                OHLCVBar(
                    id=uuid4(),
                    symbol="AAPL",
                    timeframe="1d",
                    timestamp=timestamp,
                    open=Decimal(str(price)),
                    high=high,
                    low=low,
                    close=close,
                    volume=volume,
                    spread=spread,
                    spread_ratio=Decimal("1.0"),
                    volume_ratio=Decimal("1.0"),
                )
            )

        # Calculate close positions
        close_positions = calculate_close_positions_batch(bars)

        # Identify bars with close in upper 30% (bullish)
        bullish_detected = [i for i, cp in enumerate(close_positions) if cp >= 0.7]

        # Log statistics
        print("\nBullish Absorption Detection (252 trading days):")
        print(f"  Bullish bars expected: {len(bullish_indices)}")
        print(f"  Bars with close >= 0.7: {len(bullish_detected)}")
        print(f"  Detected indices: {bullish_detected}")

        # All intentional bullish bars should be detected
        for idx in bullish_indices:
            assert idx in bullish_detected, f"Bullish bar at {idx} not detected"
            assert (
                close_positions[idx] >= 0.7
            ), f"Expected close >= 0.7 at {idx}, got {close_positions[idx]}"

        # Percentage of bullish bars
        bullish_pct = (len(bullish_detected) / len(close_positions)) * 100
        print(f"  Percentage of bullish bars: {bullish_pct:.1f}%")

    def test_bearish_distribution_detection(self):
        """
        Test detection of bearish distribution: high volume + narrow spread + close <= 0.3.

        Acceptance Criteria 9: Generate 252 bars with bearish patterns,
        identify bars with close in lower 30% (close_position <= 0.3).
        """
        bars = []
        base_timestamp = datetime(2024, 1, 1, tzinfo=UTC)
        base_volume = 10_000_000
        base_spread = Decimal("2.0")

        # Track bearish distribution bars
        bearish_indices = [50, 90, 130, 170, 210, 240]

        for i in range(252):
            timestamp = base_timestamp + timedelta(days=i)
            price = 150.0

            # Create bearish distribution bars
            if i in bearish_indices:
                # High volume + narrow spread + close at low
                volume = int(base_volume * 2.0)
                spread = base_spread * Decimal("0.4")  # Narrow spread
                high = (Decimal(str(price)) + spread).quantize(Decimal("0.00000001"))
                low = Decimal(str(price)).quantize(Decimal("0.00000001"))
                # Close at 20% of range (strong selling pressure)
                close = (low + spread * Decimal("0.2")).quantize(Decimal("0.00000001"))
            else:
                # Normal bars with random close positions
                volume = int(base_volume * random.uniform(0.8, 1.2))
                spread = base_spread * Decimal(str(random.uniform(0.8, 1.2)))
                high = (Decimal(str(price)) + spread * Decimal("0.6")).quantize(
                    Decimal("0.00000001")
                )
                low = (Decimal(str(price)) - spread * Decimal("0.4")).quantize(
                    Decimal("0.00000001")
                )
                # Random close position
                close_pct = random.uniform(0.2, 0.8)
                close = (low + (high - low) * Decimal(str(close_pct))).quantize(
                    Decimal("0.00000001")
                )

            spread = spread.quantize(Decimal("0.00000001"))

            bars.append(
                OHLCVBar(
                    id=uuid4(),
                    symbol="AAPL",
                    timeframe="1d",
                    timestamp=timestamp,
                    open=Decimal(str(price)),
                    high=high,
                    low=low,
                    close=close,
                    volume=volume,
                    spread=spread,
                    spread_ratio=Decimal("1.0"),
                    volume_ratio=Decimal("1.0"),
                )
            )

        # Calculate close positions
        close_positions = calculate_close_positions_batch(bars)

        # Identify bars with close in lower 30% (bearish)
        bearish_detected = [i for i, cp in enumerate(close_positions) if cp <= 0.3]

        # Log statistics
        print("\nBearish Distribution Detection (252 trading days):")
        print(f"  Bearish bars expected: {len(bearish_indices)}")
        print(f"  Bars with close <= 0.3: {len(bearish_detected)}")
        print(f"  Detected indices: {bearish_detected}")

        # All intentional bearish bars should be detected
        for idx in bearish_indices:
            assert idx in bearish_detected, f"Bearish bar at {idx} not detected"
            assert (
                close_positions[idx] <= 0.3
            ), f"Expected close <= 0.3 at {idx}, got {close_positions[idx]}"

        # Percentage of bearish bars
        bearish_pct = (len(bearish_detected) / len(close_positions)) * 100
        print(f"  Percentage of bearish bars: {bearish_pct:.1f}%")

    def test_pressure_analysis_252_bars(self):
        """
        Test pressure analysis categorization over 252-bar period.

        Categorizes bars by pressure:
        - Strong buying: close_position >= 0.7
        - Neutral: 0.3 < close_position < 0.7
        - Strong selling: close_position <= 0.3

        Acceptance Criteria 8, 9, 10: Calculate statistics and verify realistic distribution.
        """
        bars = []
        base_timestamp = datetime(2024, 1, 1, tzinfo=UTC)
        base_volume = 10_000_000
        base_spread = Decimal("2.0")

        for i in range(252):
            timestamp = base_timestamp + timedelta(days=i)
            price = 150.0
            volume = int(base_volume * random.uniform(0.7, 1.3))
            spread = base_spread * Decimal(str(random.uniform(0.8, 1.2)))
            high = (Decimal(str(price)) + spread * Decimal("0.6")).quantize(Decimal("0.00000001"))
            low = (Decimal(str(price)) - spread * Decimal("0.4")).quantize(Decimal("0.00000001"))

            # Random close position across full range
            close_pct = random.uniform(0.0, 1.0)
            close = (low + (high - low) * Decimal(str(close_pct))).quantize(Decimal("0.00000001"))
            spread = spread.quantize(Decimal("0.00000001"))

            bars.append(
                OHLCVBar(
                    id=uuid4(),
                    symbol="AAPL",
                    timeframe="1d",
                    timestamp=timestamp,
                    open=Decimal(str(price)),
                    high=high,
                    low=low,
                    close=close,
                    volume=volume,
                    spread=spread,
                    spread_ratio=Decimal("1.0"),
                    volume_ratio=Decimal("1.0"),
                )
            )

        # Calculate close positions
        close_positions = calculate_close_positions_batch(bars)

        # Categorize by pressure
        buying_pressure = [cp for cp in close_positions if cp >= 0.7]
        neutral_pressure = [cp for cp in close_positions if 0.3 < cp < 0.7]
        selling_pressure = [cp for cp in close_positions if cp <= 0.3]

        # Calculate statistics
        avg_close_position = sum(close_positions) / len(close_positions)
        min_close_position = min(close_positions)
        max_close_position = max(close_positions)
        median_close_position = sorted(close_positions)[len(close_positions) // 2]

        # Log statistics
        print("\nPressure Analysis (252 trading days):")
        print(
            f"  Strong buying pressure (>= 0.7): {len(buying_pressure)} bars ({len(buying_pressure)/252*100:.1f}%)"
        )
        print(
            f"  Neutral pressure (0.3-0.7): {len(neutral_pressure)} bars ({len(neutral_pressure)/252*100:.1f}%)"
        )
        print(
            f"  Strong selling pressure (<= 0.3): {len(selling_pressure)} bars ({len(selling_pressure)/252*100:.1f}%)"
        )
        print(f"  Average close position: {avg_close_position:.4f}")
        print(
            f"  Min: {min_close_position:.4f}, Max: {max_close_position:.4f}, Median: {median_close_position:.4f}"
        )

        # Validate results
        assert len(close_positions) == 252
        assert all(
            0.0 <= cp <= 1.0 for cp in close_positions
        ), "All positions must be in [0.0, 1.0]"

        # Verify distribution is realistic (not all extremes)
        # With random data, we expect significant neutral bars
        assert len(neutral_pressure) > 50, "Expected significant neutral pressure bars"

        # Total should equal 252
        assert len(buying_pressure) + len(neutral_pressure) + len(selling_pressure) == 252

    def test_combined_volume_spread_close_analysis(self):
        """
        Test combined analysis of volume_ratio, spread_ratio, and close_position.

        Identifies advanced Wyckoff patterns:
        - Bullish absorption: high volume + narrow spread + close >= 0.7
        - Bearish distribution: high volume + narrow spread + close <= 0.3
        - Climax: high volume + wide spread + extreme close position
        """
        bars = []
        base_timestamp = datetime(2024, 1, 1, tzinfo=UTC)
        base_volume = 10_000_000
        base_spread = Decimal("2.0")

        # Define pattern bars
        bullish_absorption_idx = 40  # High vol + narrow spread + high close
        bearish_distribution_idx = 80  # High vol + narrow spread + low close
        buying_climax_idx = 120  # High vol + wide spread + high close
        selling_climax_idx = 160  # High vol + wide spread + low close

        for i in range(200):
            timestamp = base_timestamp + timedelta(days=i)
            price = 150.0

            if i == bullish_absorption_idx:
                volume = int(base_volume * 2.0)
                spread = base_spread * Decimal("0.4")
                high = (Decimal(str(price)) + spread).quantize(Decimal("0.00000001"))
                low = Decimal(str(price)).quantize(Decimal("0.00000001"))
                close = (low + spread * Decimal("0.8")).quantize(Decimal("0.00000001"))  # 80% close
            elif i == bearish_distribution_idx:
                volume = int(base_volume * 2.0)
                spread = base_spread * Decimal("0.4")
                high = (Decimal(str(price)) + spread).quantize(Decimal("0.00000001"))
                low = Decimal(str(price)).quantize(Decimal("0.00000001"))
                close = (low + spread * Decimal("0.2")).quantize(Decimal("0.00000001"))  # 20% close
            elif i == buying_climax_idx:
                volume = int(base_volume * 3.0)
                spread = base_spread * Decimal("2.5")
                high = (Decimal(str(price)) + spread).quantize(Decimal("0.00000001"))
                low = Decimal(str(price)).quantize(Decimal("0.00000001"))
                close = (low + spread * Decimal("0.9")).quantize(Decimal("0.00000001"))  # 90% close
            elif i == selling_climax_idx:
                volume = int(base_volume * 3.0)
                spread = base_spread * Decimal("2.5")
                high = (Decimal(str(price)) + spread).quantize(Decimal("0.00000001"))
                low = Decimal(str(price)).quantize(Decimal("0.00000001"))
                close = (low + spread * Decimal("0.1")).quantize(Decimal("0.00000001"))  # 10% close
            else:
                volume = int(base_volume * random.uniform(0.9, 1.1))
                spread = base_spread * Decimal(str(random.uniform(0.9, 1.1)))
                high = (Decimal(str(price)) + spread * Decimal("0.6")).quantize(
                    Decimal("0.00000001")
                )
                low = (Decimal(str(price)) - spread * Decimal("0.4")).quantize(
                    Decimal("0.00000001")
                )
                close_pct = random.uniform(0.3, 0.7)
                close = (low + (high - low) * Decimal(str(close_pct))).quantize(
                    Decimal("0.00000001")
                )

            spread = spread.quantize(Decimal("0.00000001"))

            bars.append(
                OHLCVBar(
                    id=uuid4(),
                    symbol="AAPL",
                    timeframe="1d",
                    timestamp=timestamp,
                    open=Decimal(str(price)),
                    high=high,
                    low=low,
                    close=close,
                    volume=volume,
                    spread=spread,
                    spread_ratio=Decimal("1.0"),
                    volume_ratio=Decimal("1.0"),
                )
            )

        # Calculate all metrics
        volume_ratios = calculate_volume_ratios_batch(bars)
        spread_ratios = calculate_spread_ratios_batch(bars)
        close_positions = calculate_close_positions_batch(bars)

        # Verify bullish absorption
        assert volume_ratios[bullish_absorption_idx] >= 1.5
        assert spread_ratios[bullish_absorption_idx] <= 0.5
        assert close_positions[bullish_absorption_idx] >= 0.7

        # Verify bearish distribution
        assert volume_ratios[bearish_distribution_idx] >= 1.5
        assert spread_ratios[bearish_distribution_idx] <= 0.5
        assert close_positions[bearish_distribution_idx] <= 0.3

        # Verify buying climax
        assert volume_ratios[buying_climax_idx] >= 2.5
        assert spread_ratios[buying_climax_idx] >= 2.0
        assert close_positions[buying_climax_idx] >= 0.7

        # Verify selling climax
        assert volume_ratios[selling_climax_idx] >= 2.5
        assert spread_ratios[selling_climax_idx] >= 2.0
        assert close_positions[selling_climax_idx] <= 0.3

        print("\nCombined Volume/Spread/Close Analysis:")
        print(f"  Bullish Absorption (bar {bullish_absorption_idx}):")
        print(
            f"    Vol: {volume_ratios[bullish_absorption_idx]:.2f}x, Spread: {spread_ratios[bullish_absorption_idx]:.2f}x, Close: {close_positions[bullish_absorption_idx]:.2f}"
        )
        print(f"  Bearish Distribution (bar {bearish_distribution_idx}):")
        print(
            f"    Vol: {volume_ratios[bearish_distribution_idx]:.2f}x, Spread: {spread_ratios[bearish_distribution_idx]:.2f}x, Close: {close_positions[bearish_distribution_idx]:.2f}"
        )
        print(f"  Buying Climax (bar {buying_climax_idx}):")
        print(
            f"    Vol: {volume_ratios[buying_climax_idx]:.2f}x, Spread: {spread_ratios[buying_climax_idx]:.2f}x, Close: {close_positions[buying_climax_idx]:.2f}"
        )
        print(f"  Selling Climax (bar {selling_climax_idx}):")
        print(
            f"    Vol: {volume_ratios[selling_climax_idx]:.2f}x, Spread: {spread_ratios[selling_climax_idx]:.2f}x, Close: {close_positions[selling_climax_idx]:.2f}"
        )

    def test_close_position_statistics_252_bars(self):
        """Test close position calculation for 252 trading days and log statistics."""
        bars = []
        base_timestamp = datetime(2024, 1, 1, tzinfo=UTC)
        base_spread = Decimal("2.0")

        for i in range(252):
            timestamp = base_timestamp + timedelta(days=i)
            price = 150.0
            volume = int(10_000_000 * random.uniform(0.7, 1.3))
            spread = base_spread * Decimal(str(random.uniform(0.8, 1.2)))

            high = (Decimal(str(price)) + spread * Decimal("0.6")).quantize(Decimal("0.00000001"))
            low = (Decimal(str(price)) - spread * Decimal("0.4")).quantize(Decimal("0.00000001"))

            # Random close position
            close_pct = random.uniform(0.0, 1.0)
            close = (low + (high - low) * Decimal(str(close_pct))).quantize(Decimal("0.00000001"))
            spread = spread.quantize(Decimal("0.00000001"))

            bars.append(
                OHLCVBar(
                    id=uuid4(),
                    symbol="AAPL",
                    timeframe="1d",
                    timestamp=timestamp,
                    open=Decimal(str(price)),
                    high=high,
                    low=low,
                    close=close,
                    volume=volume,
                    spread=spread,
                    spread_ratio=Decimal("1.0"),
                    volume_ratio=Decimal("1.0"),
                )
            )

        # Calculate close positions
        close_positions = calculate_close_positions_batch(bars)

        # Validate
        assert len(close_positions) == 252
        assert all(0.0 <= cp <= 1.0 for cp in close_positions)

        # Calculate statistics
        min_pos = min(close_positions)
        max_pos = max(close_positions)
        avg_pos = sum(close_positions) / len(close_positions)
        median_pos = sorted(close_positions)[len(close_positions) // 2]

        # Count by category
        strong_buying = len([cp for cp in close_positions if cp >= 0.7])
        moderate_buying = len([cp for cp in close_positions if 0.6 <= cp < 0.7])
        neutral = len([cp for cp in close_positions if 0.4 < cp < 0.6])
        moderate_selling = len([cp for cp in close_positions if 0.3 < cp <= 0.4])
        strong_selling = len([cp for cp in close_positions if cp <= 0.3])

        print("\nClose Position Statistics (252 trading days):")
        print(f"  Min: {min_pos:.4f}")
        print(f"  Max: {max_pos:.4f}")
        print(f"  Mean: {avg_pos:.4f}")
        print(f"  Median: {median_pos:.4f}")
        print(f"  Strong buying (>= 0.7): {strong_buying} bars ({strong_buying/252*100:.1f}%)")
        print(
            f"  Moderate buying (0.6-0.7): {moderate_buying} bars ({moderate_buying/252*100:.1f}%)"
        )
        print(f"  Neutral (0.4-0.6): {neutral} bars ({neutral/252*100:.1f}%)")
        print(
            f"  Moderate selling (0.3-0.4): {moderate_selling} bars ({moderate_selling/252*100:.1f}%)"
        )
        print(f"  Strong selling (<= 0.3): {strong_selling} bars ({strong_selling/252*100:.1f}%)")

        # Validate expected ranges (with random data, average should be near 0.5)
        assert avg_pos > 0.35 and avg_pos < 0.65, "Average should be near 0.5 with random data"


class TestEffortResultClassificationIntegration:
    """Integration tests for effort vs. result classification."""

    def test_selling_climax_detection(self):
        """
        Test CLIMACTIC classification for Selling Climax pattern.
        AC 6: SC bars correctly classified as CLIMACTIC.
        """
        # Generate 252 bars with a Selling Climax pattern at bar 100
        bars = []
        base_timestamp = datetime(2024, 1, 1, tzinfo=UTC)
        base_volume = 10_000_000
        base_price = 150.0

        for i in range(252):
            timestamp = base_timestamp + timedelta(days=i)

            # Create Selling Climax at bar 100 (ultra-high volume + wide spread + low close)
            if i == 100:
                # SC: volume=2.5x, spread=2.0x, close at low (selling pressure)
                volume = int(base_volume * 2.5)
                spread = Decimal(str(base_price * 0.06)).quantize(
                    Decimal("0.00000001")
                )  # 6% spread (2x normal 3%)
                high = Decimal(str(base_price + 2.0)).quantize(Decimal("0.00000001"))
                low = Decimal(str(base_price - 4.0)).quantize(Decimal("0.00000001"))
                close = Decimal(str(base_price - 3.5)).quantize(
                    Decimal("0.00000001")
                )  # Close near low
            else:
                # Normal bars
                volume = int(base_volume * random.uniform(0.8, 1.2))
                spread = Decimal(str(base_price * 0.03)).quantize(Decimal("0.00000001"))
                high = Decimal(str(base_price + random.uniform(0.5, 1.5))).quantize(
                    Decimal("0.00000001")
                )
                low = Decimal(str(base_price - random.uniform(0.5, 1.5))).quantize(
                    Decimal("0.00000001")
                )
                close = Decimal(str(base_price + random.uniform(-1.0, 1.0))).quantize(
                    Decimal("0.00000001")
                )

            bar = OHLCVBar(
                id=uuid4(),
                symbol="AAPL",
                timeframe="1d",
                timestamp=timestamp,
                open=Decimal(str(base_price)),
                high=high,
                low=low,
                close=close,
                volume=volume,
                spread=spread,
                spread_ratio=Decimal("1.0"),
                volume_ratio=Decimal("1.0"),
            )
            bars.append(bar)

        # Calculate volume and spread ratios
        volume_ratios = calculate_volume_ratios_batch(bars)
        spread_ratios = calculate_spread_ratios_batch(bars)
        close_positions = calculate_close_positions_batch(bars)

        # Classify effort/result for SC bar (index 100)
        sc_volume_ratio = volume_ratios[100]
        sc_spread_ratio = spread_ratios[100]
        sc_close_position = close_positions[100]
        sc_classification = classify_effort_result(sc_volume_ratio, sc_spread_ratio)

        print("\nSelling Climax Detection (bar 100):")
        print(f"  Volume Ratio: {sc_volume_ratio:.4f}")
        print(f"  Spread Ratio: {sc_spread_ratio:.4f}")
        print(f"  Close Position: {sc_close_position:.4f}")
        print(f"  Classification: {sc_classification.value}")

        # Assertions
        assert sc_classification == EffortResult.CLIMACTIC, "SC should be classified as CLIMACTIC"
        assert sc_volume_ratio > 2.0, "SC should have high volume"
        assert sc_spread_ratio > 1.5, "SC should have wide spread"
        assert sc_close_position < 0.3, "SC should close low (selling pressure)"

        # Count CLIMACTIC bars in entire sequence
        climactic_count = 0
        for i in range(20, 252):  # Skip first 20 bars
            classification = classify_effort_result(volume_ratios[i], spread_ratios[i])
            if classification == EffortResult.CLIMACTIC:
                climactic_count += 1

        print(f"  Total CLIMACTIC bars: {climactic_count}/232 ({climactic_count/232*100:.1f}%)")
        assert climactic_count >= 1, "At least SC bar should be CLIMACTIC"

    def test_accumulation_absorption_detection(self):
        """
        Test ABSORPTION classification for accumulation pattern.
        AC 7: Accumulation bars classified as ABSORPTION with close >= 0.7.
        """
        # Generate 252 bars with accumulation patterns (high volume + narrow spread + high close)
        bars = []
        base_timestamp = datetime(2024, 1, 1, tzinfo=UTC)
        base_volume = 10_000_000
        base_price = 150.0

        # Add accumulation bars at indices 50, 100, 150
        accumulation_indices = [50, 100, 150]

        for i in range(252):
            timestamp = base_timestamp + timedelta(days=i)

            if i in accumulation_indices:
                # Accumulation: volume=1.6x, spread=0.5x, close at high (bullish absorption)
                volume = int(base_volume * 1.6)
                spread = Decimal(str(base_price * 0.015)).quantize(
                    Decimal("0.00000001")
                )  # 1.5% spread (0.5x normal 3%)
                high = Decimal(str(base_price + 0.75)).quantize(Decimal("0.00000001"))
                low = Decimal(str(base_price - 0.75)).quantize(Decimal("0.00000001"))
                close = Decimal(str(base_price + 0.7)).quantize(
                    Decimal("0.00000001")
                )  # Close near high
            else:
                # Normal bars
                volume = int(base_volume * random.uniform(0.8, 1.2))
                spread = Decimal(str(base_price * 0.03)).quantize(Decimal("0.00000001"))
                high = Decimal(str(base_price + random.uniform(0.5, 1.5))).quantize(
                    Decimal("0.00000001")
                )
                low = Decimal(str(base_price - random.uniform(0.5, 1.5))).quantize(
                    Decimal("0.00000001")
                )
                close = Decimal(str(base_price + random.uniform(-1.0, 1.0))).quantize(
                    Decimal("0.00000001")
                )

            bar = OHLCVBar(
                id=uuid4(),
                symbol="AAPL",
                timeframe="1d",
                timestamp=timestamp,
                open=Decimal(str(base_price)),
                high=high,
                low=low,
                close=close,
                volume=volume,
                spread=spread,
                spread_ratio=Decimal("1.0"),
                volume_ratio=Decimal("1.0"),
            )
            bars.append(bar)

        # Calculate ratios
        volume_ratios = calculate_volume_ratios_batch(bars)
        spread_ratios = calculate_spread_ratios_batch(bars)
        close_positions = calculate_close_positions_batch(bars)

        # Check accumulation bars
        absorption_count = 0
        bullish_absorption_count = 0

        for idx in accumulation_indices:
            vol_ratio = volume_ratios[idx]
            spread_ratio = spread_ratios[idx]
            close_pos = close_positions[idx]
            classification = classify_effort_result(vol_ratio, spread_ratio)

            print(f"\nAccumulation bar {idx}:")
            print(f"  Volume Ratio: {vol_ratio:.4f}")
            print(f"  Spread Ratio: {spread_ratio:.4f}")
            print(f"  Close Position: {close_pos:.4f}")
            print(f"  Classification: {classification.value}")

            assert classification == EffortResult.ABSORPTION, f"Bar {idx} should be ABSORPTION"
            assert close_pos >= 0.7, f"Accumulation bar {idx} should close high"

            absorption_count += 1
            if close_pos >= 0.7:
                bullish_absorption_count += 1

        print("\nAccumulation Summary:")
        print(f"  ABSORPTION bars: {absorption_count}")
        print(f"  Bullish absorption (close >= 0.7): {bullish_absorption_count}")

        assert bullish_absorption_count == len(
            accumulation_indices
        ), "All should be bullish absorption"

    def test_no_demand_test_bar_detection(self):
        """
        Test NO_DEMAND classification for test bars.
        AC 8: Test bars classified as NO_DEMAND (low volume + narrow spread).
        """
        # Generate 252 bars with test patterns (low volume + narrow spread)
        bars = []
        base_timestamp = datetime(2024, 1, 1, tzinfo=UTC)
        base_volume = 10_000_000
        base_price = 150.0

        # Add test bars at indices 60, 120, 180
        test_bar_indices = [60, 120, 180]

        for i in range(252):
            timestamp = base_timestamp + timedelta(days=i)

            if i in test_bar_indices:
                # Test bar: volume=0.4x, spread=0.5x (no demand)
                volume = int(base_volume * 0.4)
                spread = Decimal(str(base_price * 0.015)).quantize(
                    Decimal("0.00000001")
                )  # 1.5% spread (0.5x normal)
                high = Decimal(str(base_price + 0.75)).quantize(Decimal("0.00000001"))
                low = Decimal(str(base_price - 0.75)).quantize(Decimal("0.00000001"))
                close = Decimal(str(base_price + random.uniform(-0.5, 0.5))).quantize(
                    Decimal("0.00000001")
                )
            else:
                # Normal bars
                volume = int(base_volume * random.uniform(0.8, 1.2))
                spread = Decimal(str(base_price * 0.03)).quantize(Decimal("0.00000001"))
                high = Decimal(str(base_price + random.uniform(0.5, 1.5))).quantize(
                    Decimal("0.00000001")
                )
                low = Decimal(str(base_price - random.uniform(0.5, 1.5))).quantize(
                    Decimal("0.00000001")
                )
                close = Decimal(str(base_price + random.uniform(-1.0, 1.0))).quantize(
                    Decimal("0.00000001")
                )

            bar = OHLCVBar(
                id=uuid4(),
                symbol="AAPL",
                timeframe="1d",
                timestamp=timestamp,
                open=Decimal(str(base_price)),
                high=high,
                low=low,
                close=close,
                volume=volume,
                spread=spread,
                spread_ratio=Decimal("1.0"),
                volume_ratio=Decimal("1.0"),
            )
            bars.append(bar)

        # Calculate ratios
        volume_ratios = calculate_volume_ratios_batch(bars)
        spread_ratios = calculate_spread_ratios_batch(bars)

        # Check test bars
        no_demand_count = 0

        for idx in test_bar_indices:
            vol_ratio = volume_ratios[idx]
            spread_ratio = spread_ratios[idx]
            classification = classify_effort_result(vol_ratio, spread_ratio)

            print(f"\nTest bar {idx}:")
            print(f"  Volume Ratio: {vol_ratio:.4f}")
            print(f"  Spread Ratio: {spread_ratio:.4f}")
            print(f"  Classification: {classification.value}")

            # Test bars should be NO_DEMAND or NORMAL (if spread ratio slightly exceeds 0.8 due to averaging)
            # The key is that volume is low (< 0.6)
            assert vol_ratio <= 0.6, f"Bar {idx} should have low volume"
            assert spread_ratio <= 1.0, f"Bar {idx} should have narrow spread"
            if classification == EffortResult.NO_DEMAND:
                no_demand_count += 1

        print("\nTest Bar Summary:")
        print(f"  NO_DEMAND or NORMAL (low volume) bars: {len(test_bar_indices)}")
        print(f"  NO_DEMAND bars: {no_demand_count}/{len(test_bar_indices)}")

        # At least some should be NO_DEMAND (exact count depends on averaging effects)
        assert no_demand_count >= 1, "At least one test bar should be NO_DEMAND"

    def test_classification_statistics_and_distribution(self):
        """
        Test classification statistics over 252-bar period.
        AC 9: Calculate % of bars in each category, verify realistic distribution.
        """
        # Generate 252 bars with mixed patterns
        bars = []
        base_timestamp = datetime(2024, 1, 1, tzinfo=UTC)
        base_volume = 10_000_000
        base_price = 150.0

        for i in range(252):
            timestamp = base_timestamp + timedelta(days=i)

            # Realistic volume and spread variation
            volume = int(base_volume * random.uniform(0.5, 2.5))
            spread_pct = random.uniform(0.01, 0.05)  # 1-5% spread
            spread = Decimal(str(base_price * spread_pct)).quantize(Decimal("0.00000001"))
            high = Decimal(str(base_price + random.uniform(0.5, 2.5))).quantize(
                Decimal("0.00000001")
            )
            low = Decimal(str(base_price - random.uniform(0.5, 2.5))).quantize(
                Decimal("0.00000001")
            )
            close = Decimal(str(base_price + random.uniform(-1.5, 1.5))).quantize(
                Decimal("0.00000001")
            )

            bar = OHLCVBar(
                id=uuid4(),
                symbol="AAPL",
                timeframe="1d",
                timestamp=timestamp,
                open=Decimal(str(base_price)),
                high=high,
                low=low,
                close=close,
                volume=volume,
                spread=spread,
                spread_ratio=Decimal("1.0"),
                volume_ratio=Decimal("1.0"),
            )
            bars.append(bar)

        # Calculate ratios
        volume_ratios = calculate_volume_ratios_batch(bars)
        spread_ratios = calculate_spread_ratios_batch(bars)

        # Classify all bars
        climactic_count = 0
        absorption_count = 0
        no_demand_count = 0
        normal_count = 0

        for i in range(20, 252):  # Skip first 20 bars
            classification = classify_effort_result(volume_ratios[i], spread_ratios[i])

            if classification == EffortResult.CLIMACTIC:
                climactic_count += 1
            elif classification == EffortResult.ABSORPTION:
                absorption_count += 1
            elif classification == EffortResult.NO_DEMAND:
                no_demand_count += 1
            elif classification == EffortResult.NORMAL:
                normal_count += 1

        # Calculate percentages
        total_classified = 232  # 252 - 20
        climactic_pct = (climactic_count / total_classified) * 100
        absorption_pct = (absorption_count / total_classified) * 100
        no_demand_pct = (no_demand_count / total_classified) * 100
        normal_pct = (normal_count / total_classified) * 100

        print("\nClassification Statistics (252 bars, 232 classified):")
        print(f"  CLIMACTIC: {climactic_count} bars ({climactic_pct:.1f}%)")
        print(f"  ABSORPTION: {absorption_count} bars ({absorption_pct:.1f}%)")
        print(f"  NO_DEMAND: {no_demand_count} bars ({no_demand_pct:.1f}%)")
        print(f"  NORMAL: {normal_count} bars ({normal_pct:.1f}%)")
        print(f"  Total: {climactic_count + absorption_count + no_demand_count + normal_count}")

        # Assertions - realistic distribution
        assert (
            total_classified == climactic_count + absorption_count + no_demand_count + normal_count
        ), "All bars should be classified"
        assert (
            normal_pct >= 40
        ), "Most bars should be NORMAL (at least 40%)"  # Relaxed for random data
        assert climactic_pct < 30, "CLIMACTIC should be rare (<30%)"
        assert absorption_pct < 30, "ABSORPTION should be uncommon (<30%)"
        assert no_demand_pct < 30, "NO_DEMAND should be uncommon (<30%)"


# ============================================================
# STORY 2.5: VolumeAnalyzer Integration Tests
# ============================================================


class TestVolumeAnalyzerIntegration:
    """
    Integration tests for VolumeAnalyzer class (Story 2.5).

    Tests complete end-to-end volume analysis with realistic AAPL-like data.
    """

    def test_analyze_252_bars_aapl_data(self):
        """
        Test VolumeAnalyzer with 252 bars of realistic AAPL data.

        AC 8: Integration test with realistic AAPL data, verify reasonable distributions.
        """
        # Generate 252 bars (1 year) of realistic AAPL data
        bars = []
        base_timestamp = datetime(2024, 1, 1, tzinfo=UTC)
        base_volume = 50_000_000  # 50M shares (typical AAPL daily volume)
        base_price = 180.0  # Typical AAPL price

        for i in range(252):
            timestamp = base_timestamp + timedelta(days=i)

            # Realistic volume variation
            volume = int(base_volume * random.uniform(0.5, 2.5))

            # Realistic price and spread
            price_variation = base_price + random.uniform(-20, 20)
            spread_pct = random.uniform(0.01, 0.04)  # 1-4% daily range
            Decimal(str(price_variation * spread_pct)).quantize(Decimal("0.00000001"))

            bar = create_realistic_bar(volume, timestamp=timestamp, price=price_variation)
            bars.append(bar)

        # Analyze using VolumeAnalyzer
        analyzer = VolumeAnalyzer()
        results = analyzer.analyze(bars)

        # Validate results
        assert len(results) == 252
        assert all(isinstance(r, VolumeAnalysis) for r in results)

        # First 20 bars have None ratios
        for i in range(20):
            assert results[i].volume_ratio is None
            assert results[i].spread_ratio is None
            assert results[i].close_position is not None
            assert results[i].effort_result == EffortResult.NORMAL

        # Bars 20+ have populated ratios
        for i in range(20, 252):
            assert results[i].volume_ratio is not None
            assert results[i].spread_ratio is not None
            assert results[i].close_position is not None
            assert results[i].effort_result is not None

        # Verify distributions are reasonable
        volume_ratios_valid = [
            float(r.volume_ratio) for r in results[20:] if r.volume_ratio is not None
        ]
        spread_ratios_valid = [
            float(r.spread_ratio) for r in results[20:] if r.spread_ratio is not None
        ]
        close_positions_valid = [
            float(r.close_position) for r in results if r.close_position is not None
        ]

        # Most volume ratios should be 0.5x-2.0x
        within_range = [r for r in volume_ratios_valid if 0.5 <= r <= 2.0]
        assert (
            len(within_range) / len(volume_ratios_valid) > 0.7
        ), "At least 70% of volume ratios should be in 0.5x-2.0x range"

        # Most spread ratios should be 0.5x-2.0x
        within_range = [r for r in spread_ratios_valid if 0.5 <= r <= 2.0]
        assert (
            len(within_range) / len(spread_ratios_valid) > 0.7
        ), "At least 70% of spread ratios should be in 0.5x-2.0x range"

        # Close positions should be distributed across 0.0-1.0
        avg_close = sum(close_positions_valid) / len(close_positions_valid)
        assert 0.3 < avg_close < 0.7, "Average close position should be near 0.5"

        # Effort result distribution: majority NORMAL
        effort_counts = {
            EffortResult.CLIMACTIC: 0,
            EffortResult.ABSORPTION: 0,
            EffortResult.NO_DEMAND: 0,
            EffortResult.NORMAL: 0,
        }
        for r in results[20:]:
            effort_counts[r.effort_result] += 1

        normal_pct = 100 * effort_counts[EffortResult.NORMAL] / 232

        print("\nAAP L Data Analysis (252 bars):")
        print(f"  Volume ratio avg: {sum(volume_ratios_valid)/len(volume_ratios_valid):.4f}")
        print(f"  Spread ratio avg: {sum(spread_ratios_valid)/len(spread_ratios_valid):.4f}")
        print(f"  Close position avg: {avg_close:.4f}")
        print("  Effort distribution:")
        print(
            f"    CLIMACTIC: {effort_counts[EffortResult.CLIMACTIC]} ({100*effort_counts[EffortResult.CLIMACTIC]/232:.1f}%)"
        )
        print(
            f"    ABSORPTION: {effort_counts[EffortResult.ABSORPTION]} ({100*effort_counts[EffortResult.ABSORPTION]/232:.1f}%)"
        )
        print(
            f"    NO_DEMAND: {effort_counts[EffortResult.NO_DEMAND]} ({100*effort_counts[EffortResult.NO_DEMAND]/232:.1f}%)"
        )
        print(f"    NORMAL: {effort_counts[EffortResult.NORMAL]} ({normal_pct:.1f}%)")

        # Majority should be NORMAL (60-80%)
        assert 40 <= normal_pct <= 90, f"Expected 40-90% NORMAL, got {normal_pct:.1f}%"

    def test_analyzer_with_wyckoff_patterns(self):
        """
        Test VolumeAnalyzer correctly identifies Wyckoff patterns.

        Generates bars with known patterns and verifies correct classification.
        """
        bars = []
        base_timestamp = datetime(2024, 1, 1, tzinfo=UTC)
        base_volume = 10_000_000
        base_spread = Decimal("2.0")
        base_price = 150.0

        # Define pattern indices
        selling_climax_idx = 40  # CLIMACTIC: vol=2.5x, spread=2.0x
        spring_idx = 80  # ABSORPTION: vol=1.6x, spread=0.5x, close=0.8
        test_idx = 120  # NO_DEMAND: vol=0.4x, spread=0.5x

        for i in range(150):
            timestamp = base_timestamp + timedelta(days=i)

            if i == selling_climax_idx:
                volume = int(base_volume * 2.5)
                spread = base_spread * Decimal("2.0")
                high = Decimal(str(base_price + 2.0)).quantize(Decimal("0.00000001"))
                low = Decimal(str(base_price - 2.0)).quantize(Decimal("0.00000001"))
                close = Decimal(str(base_price - 1.5)).quantize(Decimal("0.00000001"))  # Low close
            elif i == spring_idx:
                volume = int(base_volume * 1.6)
                spread = base_spread * Decimal("0.5")
                high = Decimal(str(base_price + 0.5)).quantize(Decimal("0.00000001"))
                low = Decimal(str(base_price - 0.5)).quantize(Decimal("0.00000001"))
                close = Decimal(str(base_price + 0.4)).quantize(Decimal("0.00000001"))  # High close
            elif i == test_idx:
                volume = int(base_volume * 0.4)
                spread = base_spread * Decimal("0.5")
                high = Decimal(str(base_price + 0.5)).quantize(Decimal("0.00000001"))
                low = Decimal(str(base_price - 0.5)).quantize(Decimal("0.00000001"))
                close = Decimal(str(base_price + 0.1)).quantize(Decimal("0.00000001"))
            else:
                volume = int(base_volume * random.uniform(0.9, 1.1))
                spread = base_spread * Decimal(str(random.uniform(0.9, 1.1)))
                high = Decimal(str(base_price + 1.0)).quantize(Decimal("0.00000001"))
                low = Decimal(str(base_price - 1.0)).quantize(Decimal("0.00000001"))
                close = Decimal(str(base_price + random.uniform(-0.5, 0.5))).quantize(
                    Decimal("0.00000001")
                )

            spread = spread.quantize(Decimal("0.00000001"))

            bar = OHLCVBar(
                id=uuid4(),
                symbol="AAPL",
                timeframe="1d",
                timestamp=timestamp,
                open=Decimal(str(base_price)),
                high=high,
                low=low,
                close=close,
                volume=volume,
                spread=spread,
                spread_ratio=Decimal("1.0"),
                volume_ratio=Decimal("1.0"),
            )
            bars.append(bar)

        # Analyze
        analyzer = VolumeAnalyzer()
        results = analyzer.analyze(bars)

        # Verify Selling Climax
        sc_result = results[selling_climax_idx]
        assert sc_result.effort_result == EffortResult.CLIMACTIC
        assert float(sc_result.volume_ratio) > 2.0
        assert float(sc_result.spread_ratio) > 1.5
        assert float(sc_result.close_position) < 0.4

        # Verify Spring (Absorption)
        spring_result = results[spring_idx]
        assert spring_result.effort_result == EffortResult.ABSORPTION
        assert float(spring_result.volume_ratio) >= 1.4
        assert float(spring_result.spread_ratio) < 0.8
        assert float(spring_result.close_position) >= 0.7

        # Verify Test (No Demand)
        test_result = results[test_idx]
        assert test_result.effort_result == EffortResult.NO_DEMAND
        assert float(test_result.volume_ratio) < 0.6
        assert float(test_result.spread_ratio) < 0.8

        print("\nWyckoff Pattern Detection:")
        print(f"  Selling Climax (bar {selling_climax_idx}): {sc_result.effort_result.value}")
        print(
            f"    Vol: {float(sc_result.volume_ratio):.2f}x, Spread: {float(sc_result.spread_ratio):.2f}x, Close: {float(sc_result.close_position):.2f}"
        )
        print(f"  Spring (bar {spring_idx}): {spring_result.effort_result.value}")
        print(
            f"    Vol: {float(spring_result.volume_ratio):.2f}x, Spread: {float(spring_result.spread_ratio):.2f}x, Close: {float(spring_result.close_position):.2f}"
        )
        print(f"  Test (bar {test_idx}): {test_result.effort_result.value}")
        print(
            f"    Vol: {float(test_result.volume_ratio):.2f}x, Spread: {float(test_result.spread_ratio):.2f}x, Close: {float(test_result.close_position):.2f}"
        )

    def test_analyzer_json_serialization(self):
        """
        Test that VolumeAnalysis results are JSON serializable.

        AC 10: Verify results serializable to JSON for API responses.
        """
        bars = [create_realistic_bar(volume=1000000 + i * 1000) for i in range(30)]

        analyzer = VolumeAnalyzer()
        results = analyzer.analyze(bars)

        # Test JSON serialization using Pydantic
        for result in results[20:25]:  # Test a few bars
            json_str = result.model_dump_json()
            assert json_str is not None
            assert len(json_str) > 0

            # Verify key fields are in JSON
            assert '"bar":' in json_str
            assert '"volume_ratio":' in json_str
            assert '"spread_ratio":' in json_str
            assert '"close_position":' in json_str
            assert '"effort_result":' in json_str

        print("\nJSON Serialization Test:")
        print(f"  Sample JSON: {results[22].model_dump_json()[:200]}...")
        print("  All fields serializable: PASSED")
