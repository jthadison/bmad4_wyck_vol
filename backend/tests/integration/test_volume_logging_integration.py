"""
Integration tests for Volume Logging (Story 13.8)

Tests:
- AC8.8: Volume validation integration with pattern detection
- AC8.9: Regression test - daily backtest with volume logging
- AC8.10: Integration test - 30-day backtest with enhanced logging

These tests verify that volume logging integrates correctly with
the backtesting engine and pattern detection pipeline.
"""

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

from src.models.forex import ForexSession
from src.models.ohlcv import OHLCVBar
from src.pattern_engine.volume_logger import VolumeLogger


def create_test_bar(
    symbol: str = "EURUSD",
    volume: int = 100000,
    open_price: Decimal = Decimal("1.0500"),
    high: Decimal = Decimal("1.0520"),
    low: Decimal = Decimal("1.0480"),
    close: Decimal = Decimal("1.0510"),
    timestamp: datetime | None = None,
    timeframe: str = "15m",
) -> OHLCVBar:
    """Create a test OHLCV bar."""
    if timestamp is None:
        timestamp = datetime.now(UTC)

    return OHLCVBar(
        id=uuid4(),
        symbol=symbol,
        timeframe=timeframe,
        timestamp=timestamp,
        open=open_price,
        high=high,
        low=low,
        close=close,
        volume=volume,
        spread=high - low,
        spread_ratio=Decimal("1.0"),
        volume_ratio=Decimal("1.0"),
    )


def generate_synthetic_bars(
    days: int = 30,
    timeframe: str = "15m",
    base_volume: int = 100000,
    include_patterns: bool = True,
) -> list[OHLCVBar]:
    """
    Generate synthetic bar data for integration testing.

    Creates realistic-looking price and volume data with:
    - Session-based volume patterns (higher during London/NY)
    - Occasional volume spikes
    - Declining volume in some periods (accumulation-like)

    Args:
        days: Number of days to generate
        timeframe: Bar timeframe
        base_volume: Base volume level
        include_patterns: Whether to include pattern-like structures

    Returns:
        List of OHLCVBar objects
    """
    bars = []
    base_time = datetime.now(UTC) - timedelta(days=days)
    price = Decimal("1.0500")

    # Calculate bars per day based on timeframe
    if timeframe == "15m":
        bars_per_day = 96  # 24 * 4
        delta = timedelta(minutes=15)
    elif timeframe == "1h":
        bars_per_day = 24
        delta = timedelta(hours=1)
    else:
        bars_per_day = 1
        delta = timedelta(days=1)

    import random

    random.seed(42)  # Reproducible

    for day in range(days):
        for bar_idx in range(bars_per_day):
            current_time = base_time + timedelta(days=day) + delta * bar_idx

            # Session-based volume adjustment
            hour = current_time.hour
            if 0 <= hour < 8:
                session_multiplier = 0.4  # Asian
            elif 8 <= hour < 13:
                session_multiplier = 1.3  # London
            elif 13 <= hour < 17:
                session_multiplier = 1.6  # Overlap
            else:
                session_multiplier = 1.0  # NY/other

            # Add some randomness
            volume_multiplier = session_multiplier * (0.8 + random.random() * 0.4)

            # Occasional volume spike (5% chance)
            if random.random() < 0.05:
                volume_multiplier *= 2.5

            volume = int(base_volume * volume_multiplier)

            # Price movement (round to 8 decimal places for OHLCVBar validation)
            price_change = Decimal(str(round(random.uniform(-0.003, 0.003), 8)))
            new_price = (price + price_change).quantize(Decimal("0.00000001"))

            # Create bar
            spread = Decimal(str(round(random.uniform(0.001, 0.004), 8)))
            high_val = (max(price, new_price) + spread / 2).quantize(Decimal("0.00000001"))
            low_val = (min(price, new_price) - spread / 2).quantize(Decimal("0.00000001"))
            bar = create_test_bar(
                volume=max(volume, 1000),
                open_price=price.quantize(Decimal("0.00000001")),
                high=high_val,
                low=low_val,
                close=new_price,
                timestamp=current_time,
                timeframe=timeframe,
            )
            bars.append(bar)
            price = new_price

    return bars


class TestVolumeLoggingIntegration:
    """Integration tests for volume logging with backtesting."""

    def test_volume_validation_integration_spring(self):
        """AC8.8: Volume validation integrates with Spring detection."""
        logger = VolumeLogger()

        # Simulate pattern detection sequence
        patterns_detected = [
            {"type": "Spring", "volume_ratio": Decimal("0.55"), "session": ForexSession.LONDON},
            {"type": "Spring", "volume_ratio": Decimal("0.45"), "session": ForexSession.OVERLAP},
            {
                "type": "Spring",
                "volume_ratio": Decimal("1.2"),
                "session": ForexSession.LONDON,
            },  # Should fail
        ]

        for pattern in patterns_detected:
            logger.validate_pattern_volume(
                pattern_type=pattern["type"],
                volume_ratio=pattern["volume_ratio"],
                timestamp=datetime.now(UTC),
                asset_class="forex",
                session=pattern["session"],
            )

        stats = logger.get_validation_stats()

        # 2 should pass, 1 should fail
        assert stats["Spring"]["passed"] == 2
        assert stats["Spring"]["failed"] == 1

    def test_volume_validation_integration_sos(self):
        """AC8.8: Volume validation integrates with SOS detection."""
        logger = VolumeLogger()

        patterns_detected = [
            {"type": "SOS", "volume_ratio": Decimal("2.0"), "session": ForexSession.LONDON},  # Pass
            {
                "type": "SOS",
                "volume_ratio": Decimal("2.5"),
                "session": ForexSession.OVERLAP,
            },  # Pass
            {
                "type": "SOS",
                "volume_ratio": Decimal("1.5"),
                "session": ForexSession.LONDON,
            },  # Fail (forex needs 1.8x)
        ]

        for pattern in patterns_detected:
            logger.validate_pattern_volume(
                pattern_type=pattern["type"],
                volume_ratio=pattern["volume_ratio"],
                timestamp=datetime.now(UTC),
                asset_class="forex",
                session=pattern["session"],
            )

        stats = logger.get_validation_stats()
        assert stats["SOS"]["passed"] == 2
        assert stats["SOS"]["failed"] == 1


class TestVolumeLoggingRegression:
    """Regression tests for volume logging (AC8.9)."""

    def test_volume_logging_doesnt_break_existing_logic(self):
        """AC8.9: Volume logging should not affect existing validation results."""
        logger = VolumeLogger()

        # Known good patterns (should always pass)
        known_good = [
            ("Spring", Decimal("0.50"), "stock", True),
            ("Spring", Decimal("0.68"), "stock", True),
            ("SOS", Decimal("1.60"), "stock", True),
            ("SOS", Decimal("2.50"), "stock", True),
            ("LPS", Decimal("0.80"), "stock", True),
        ]

        # Known bad patterns (should always fail)
        known_bad = [
            ("Spring", Decimal("0.80"), "stock", False),
            ("Spring", Decimal("1.50"), "stock", False),
            ("SOS", Decimal("1.20"), "stock", False),
            ("SOS", Decimal("0.80"), "stock", False),
            ("LPS", Decimal("1.80"), "stock", False),
        ]

        for pattern_type, volume_ratio, asset_class, expected in known_good + known_bad:
            result = logger.validate_pattern_volume(
                pattern_type=pattern_type,
                volume_ratio=volume_ratio,
                timestamp=datetime.now(UTC),
                asset_class=asset_class,
            )
            assert (
                result == expected
            ), f"{pattern_type} at {volume_ratio}x expected {expected}, got {result}"

    def test_volume_thresholds_stability(self):
        """AC8.9: Volume thresholds should remain stable."""
        from src.pattern_engine.volume_logger import VOLUME_THRESHOLDS

        # Verify key thresholds haven't changed
        assert VOLUME_THRESHOLDS["Spring"]["stock"]["max"] == Decimal("0.7")
        assert VOLUME_THRESHOLDS["Spring"]["forex"]["max"] == Decimal("0.85")
        assert VOLUME_THRESHOLDS["SOS"]["stock"]["min"] == Decimal("1.5")
        assert VOLUME_THRESHOLDS["SOS"]["forex"]["min"] == Decimal("1.8")
        assert VOLUME_THRESHOLDS["UTAD"]["forex"]["min"] == Decimal("2.5")


class TestVolumeLogging30DayBacktest:
    """30-day backtest integration tests (AC8.10)."""

    def test_30_day_backtest_volume_validation(self):
        """AC8.10: 30-day backtest should have ≥1 volume violation logged."""
        logger = VolumeLogger()
        bars = generate_synthetic_bars(days=30, timeframe="15m")

        # Simulate pattern detection during backtest
        import random

        random.seed(42)

        validation_count = 0
        violation_count = 0

        for i in range(50, len(bars), 50):  # Check every 50 bars
            bar = bars[i]
            hour = bar.timestamp.hour

            # Determine session
            if 0 <= hour < 8:
                session = ForexSession.ASIAN
            elif 8 <= hour < 13:
                session = ForexSession.LONDON
            elif 13 <= hour < 17:
                session = ForexSession.OVERLAP
            else:
                session = ForexSession.NY

            # Calculate mock volume ratio
            recent_volumes = [b.volume for b in bars[max(0, i - 20) : i]]
            if recent_volumes:
                import numpy as np

                avg_volume = np.mean(recent_volumes)
                volume_ratio = Decimal(str(bar.volume / avg_volume))
            else:
                volume_ratio = Decimal("1.0")

            # Randomly assign pattern types
            pattern_type = random.choice(["Spring", "SOS", "LPS"])

            is_valid = logger.validate_pattern_volume(
                pattern_type=pattern_type,
                volume_ratio=volume_ratio,
                timestamp=bar.timestamp,
                asset_class="forex",
                session=session,
            )

            validation_count += 1
            if not is_valid:
                violation_count += 1

        # Should have at least 1 violation
        assert violation_count >= 1, "Expected at least 1 volume violation in 30-day backtest"
        assert validation_count >= 10, "Expected at least 10 validations"

    def test_30_day_backtest_divergence_detection(self):
        """AC8.10: 30-day backtest should detect ≥1 volume divergence."""
        logger = VolumeLogger()
        bars = generate_synthetic_bars(days=30, timeframe="15m")

        # Inject a guaranteed bearish divergence near bar 200:
        # Set bar 195 to have a high price with high volume, then bar 199
        # to have an even higher price but much lower volume.
        if len(bars) > 200:
            bars[195] = create_test_bar(
                volume=200000,
                high=Decimal("1.0900"),
                low=Decimal("1.0850"),
                open_price=Decimal("1.0860"),
                close=Decimal("1.0890"),
                timestamp=bars[195].timestamp,
                timeframe="15m",
            )
            bars[199] = create_test_bar(
                volume=50000,  # 75% less volume = clear divergence
                high=Decimal("1.0950"),  # New high above 1.0900
                low=Decimal("1.0900"),
                open_price=Decimal("1.0910"),
                close=Decimal("1.0940"),
                timestamp=bars[199].timestamp,
                timeframe="15m",
            )

        divergence_count = 0

        # Check for divergences periodically
        for i in range(100, len(bars), 50):
            recent_bars = bars[max(0, i - 20) : i]
            divergence = logger.detect_volume_divergence(recent_bars, lookback=20)
            if divergence:
                divergence_count += 1

        # AC8.10: Must detect at least 1 divergence in 30-day backtest
        assert divergence_count >= 1, (
            f"Expected >=1 volume divergence in 30-day backtest, got {divergence_count}"
        )

    def test_30_day_backtest_spike_detection(self):
        """AC8.10: 30-day backtest should detect volume spikes."""
        logger = VolumeLogger()
        bars = generate_synthetic_bars(days=30, timeframe="15m")

        spike_count = 0

        for i in range(20, len(bars)):
            recent_volumes = [b.volume for b in bars[i - 20 : i]]
            import numpy as np

            avg_volume = Decimal(str(np.mean(recent_volumes)))

            spike = logger.detect_volume_spike(bars[i], avg_volume)
            if spike:
                spike_count += 1

        # Should detect some spikes given 5% spike probability in data generation
        assert spike_count >= 1, "Expected at least 1 volume spike in 30-day data"

    def test_30_day_backtest_report_generation(self, capsys):
        """AC8.10: Volume analysis report should be generated after backtest."""
        logger = VolumeLogger()
        bars = generate_synthetic_bars(days=30, timeframe="15m")

        # Simulate minimal pattern validation
        for i in range(100, min(200, len(bars)), 20):
            logger.validate_pattern_volume(
                pattern_type="Spring",
                volume_ratio=Decimal("0.6"),
                timestamp=bars[i].timestamp,
                asset_class="forex",
            )

        # Add some trends
        for i in range(50, min(150, len(bars)), 50):
            logger.analyze_volume_trend(bars[max(0, i - 20) : i])

        # Generate report
        logger.print_volume_analysis_report("15m")

        captured = capsys.readouterr()

        # Verify report sections exist
        assert "[VOLUME ANALYSIS] - 15m" in captured.out
        assert "PATTERN VOLUME VALIDATION" in captured.out
        assert "VOLUME TREND ANALYSIS" in captured.out
        assert "WYCKOFF EDUCATIONAL INSIGHTS" in captured.out


class TestVolumeLoggingEdgeCases:
    """Edge case tests for volume logging."""

    def test_empty_bars_trend_analysis(self):
        """Trend analysis with empty bars should not crash."""
        logger = VolumeLogger()
        result = logger.analyze_volume_trend([], lookback=20)
        assert result.trend == "INSUFFICIENT_DATA"

    def test_zero_average_volume_spike(self):
        """Spike detection with zero average should not crash."""
        logger = VolumeLogger()
        bar = create_test_bar(volume=100000)
        spike = logger.detect_volume_spike(bar, avg_volume=Decimal("0"))
        assert spike is None

    def test_unknown_pattern_type(self):
        """Unknown pattern type should still work (return True)."""
        logger = VolumeLogger()
        result = logger.validate_pattern_volume(
            pattern_type="UnknownPattern",
            volume_ratio=Decimal("1.0"),
            timestamp=datetime.now(UTC),
            asset_class="stock",
        )
        # Unknown patterns default to pass (no threshold defined)
        assert result is True

    def test_multiple_sessions_validation(self):
        """Validation should work across all forex sessions."""
        logger = VolumeLogger()
        sessions = [
            ForexSession.ASIAN,
            ForexSession.LONDON,
            ForexSession.OVERLAP,
            ForexSession.NY,
        ]

        for session in sessions:
            result = logger.validate_pattern_volume(
                pattern_type="Spring",
                volume_ratio=Decimal("0.5"),  # Should pass in all sessions
                timestamp=datetime.now(UTC),
                asset_class="forex",
                session=session,
            )
            assert result is True, f"Spring at 0.5x should pass in {session.value}"
