"""
Integration tests for Automatic Rally (AR) detection with real AAPL March 2020 data.

Tests the AR detection following the Selling Climax (SC) during the COVID-19 crash.

AC 9: AAPL March 2020 AR detected following SC with expected characteristics.
"""

import csv
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from src.models.ohlcv import OHLCVBar
from src.pattern_engine.phase_detector import (
    detect_automatic_rally,
    detect_selling_climax,
    is_phase_a_confirmed,
)
from src.pattern_engine.volume_analyzer import VolumeAnalyzer


class TestAAPLMarch2020ARIntegration:
    """Integration tests for AR detection using AAPL March 2020 COVID crash data."""

    @pytest.fixture
    def aapl_data_path(self):
        """Get path to AAPL CSV data file."""
        # Path from project root (4 levels up from this test file)
        test_file_dir = Path(__file__).parent  # tests/integration/pattern_engine/
        backend_dir = test_file_dir.parent.parent.parent  # backend/
        project_root = backend_dir.parent  # project root
        return project_root / "daily_AAPL.csv"

    @pytest.fixture
    def aapl_bars(self, aapl_data_path):
        """
        Load AAPL data for January-April 2020.

        Returns bars from Jan 1 to April 30, 2020 to cover:
        - Pre-crash baseline (Jan 1 - Feb 15) - ~30 bars for good volume baseline
        - Crash period (Feb 16 - March 23)
        - Post-crash rally (March 24 - April 30) - AR detection period
        """
        if not aapl_data_path.exists():
            pytest.skip(f"AAPL data file not found at {aapl_data_path}")

        bars = []
        with open(aapl_data_path) as f:
            reader = csv.DictReader(f)
            for row in reader:
                # Parse timestamp
                timestamp = datetime.fromisoformat(row["timestamp"]).replace(tzinfo=UTC)

                # Filter for Jan-April 2020 (expanded for better baseline and AR detection)
                if not (
                    datetime(2020, 1, 1, tzinfo=UTC)
                    <= timestamp
                    <= datetime(2020, 4, 30, 23, 59, 59, tzinfo=UTC)
                ):
                    continue

                # Create OHLCV bar
                bar = OHLCVBar(
                    symbol="AAPL",
                    timeframe="1d",
                    timestamp=timestamp,
                    open=Decimal(row["open"]),
                    high=Decimal(row["high"]),
                    low=Decimal(row["low"]),
                    close=Decimal(row["close"]),
                    volume=int(row["volume"]),
                    spread=Decimal(row["high"]) - Decimal(row["low"]),
                )
                bars.append(bar)

        # Sort by timestamp (oldest first)
        bars.sort(key=lambda b: b.timestamp)

        if not bars:
            pytest.skip("No AAPL data found for Jan-April 2020")

        return bars

    def test_detect_ar_after_sc_march_2020(self, aapl_bars):
        """
        Test AR detection following SC on AAPL March 2020 COVID crash.

        AC 9: AAPL March 2020 AR detected following SC.

        Known sequence:
        - SC: Feb 28 or March 23, 2020 (first climactic event)
        - AR: Rally within 5 bars after SC (relief rally from bottom)
        - Expected AR rally: 3%+ from SC low

        Expected:
        - AR detected within 5 bars of SC (ideal)
        - rally_pct >= 0.03 (3%)
        - Volume profile: HIGH or NORMAL (both valid)
        """
        # Analyze volume
        volume_analyzer = VolumeAnalyzer()
        volume_analysis = volume_analyzer.analyze(aapl_bars)

        # Detect SC
        sc = detect_selling_climax(aapl_bars, volume_analysis)
        assert sc is not None, "SC should be detected in March 2020 data"

        # Detect AR
        ar = detect_automatic_rally(aapl_bars, sc, volume_analysis)

        # Assert AR detected
        assert ar is not None, "Automatic Rally should be detected after SC"

        # Assert AR characteristics
        assert ar.rally_pct >= Decimal(
            "0.03"
        ), f"Expected rally >= 3%, got {float(ar.rally_pct) * 100:.2f}%"
        assert 1 <= ar.bars_after_sc <= 10, f"Expected AR within 10 bars, got {ar.bars_after_sc}"
        assert ar.volume_profile in [
            "HIGH",
            "NORMAL",
        ], f"Expected HIGH or NORMAL, got {ar.volume_profile}"

        # Parse timestamps
        sc_timestamp = datetime.fromisoformat(sc.bar["timestamp"])
        ar_timestamp = datetime.fromisoformat(ar.bar["timestamp"])

        # Log AR details for manual verification
        print("\n=== AAPL March 2020 Automatic Rally Detected ===")
        print(f"SC Date: {sc_timestamp.date()}")
        print(f"SC Low: ${ar.sc_low}")
        print(f"\nAR Date: {ar_timestamp.date()}")
        print(f"AR High: ${ar.ar_high}")
        print(f"Rally: {float(ar.rally_pct) * 100:.2f}%")
        print(f"Bars After SC: {ar.bars_after_sc}")
        print(f"Volume Profile: {ar.volume_profile}")
        print("\nAR Bar Details:")
        print(f"Open: ${ar.bar['open']}")
        print(f"High: ${ar.bar['high']}")
        print(f"Low: ${ar.bar['low']}")
        print(f"Close: ${ar.bar['close']}")
        print(f"Volume: {ar.bar['volume']:,}")

        # Validate timing
        if ar.bars_after_sc <= 5:
            print("\n[OK] AR within ideal 5-bar window")
        else:
            print(f"\n[WARN] AR delayed: {ar.bars_after_sc} bars (ideal ≤5)")

        # Validate rally magnitude
        if float(ar.rally_pct) >= 0.05:
            print(f"[OK] Strong rally: {float(ar.rally_pct) * 100:.2f}%")
        else:
            print(f"[OK] Adequate rally: {float(ar.rally_pct) * 100:.2f}%")

    def test_phase_a_confirmed_march_2020(self, aapl_bars):
        """
        Test Phase A confirmation for AAPL March 2020.

        AC 7: Phase A confirmation requires SC + AR.

        Known sequence:
        - SC detected (climactic selling)
        - AR detected (relief rally)
        - Phase A = SC + AR (stopping action complete)

        Expected:
        - is_phase_a_confirmed(sc, ar) returns True
        - Both SC and AR present
        """
        # Analyze volume
        volume_analyzer = VolumeAnalyzer()
        volume_analysis = volume_analyzer.analyze(aapl_bars)

        # Detect SC
        sc = detect_selling_climax(aapl_bars, volume_analysis)
        assert sc is not None, "SC should be detected"

        # Detect AR
        ar = detect_automatic_rally(aapl_bars, sc, volume_analysis)
        assert ar is not None, "AR should be detected"

        # Test Phase A confirmation
        phase_a_confirmed = is_phase_a_confirmed(sc, ar)

        assert phase_a_confirmed, "Phase A should be confirmed with SC + AR"

        # Log Phase A confirmation
        print("\n=== AAPL March 2020 Phase A Confirmation ===")
        print(f"SC Timestamp: {sc.bar['timestamp']}")
        print(f"AR Timestamp: {ar.bar['timestamp']}")
        print(f"Phase A Confirmed: {phase_a_confirmed}")
        print("\n[OK] Stopping Action Complete (SC + AR)")
        print("[OK] Phase A confirmed - accumulation beginning")
        print("Next: Watch for Secondary Test (ST) retesting SC low")

    def test_ar_characteristics_match_manual_analysis(self, aapl_bars):
        """
        Test that AR characteristics match manual Wyckoff analysis.

        Validates:
        - Rally is upward from SC low
        - Rally meets 3%+ threshold
        - Rally occurs within reasonable timeframe
        - Volume profile classified correctly
        """
        # Analyze volume
        volume_analyzer = VolumeAnalyzer()
        volume_analysis = volume_analyzer.analyze(aapl_bars)

        # Detect SC
        sc = detect_selling_climax(aapl_bars, volume_analysis)
        assert sc is not None, "SC should be detected"

        # Detect AR
        ar = detect_automatic_rally(aapl_bars, sc, volume_analysis)
        assert ar is not None, "AR should be detected"

        print("\n=== Wyckoff AR Characteristics Validation ===")

        # 1. Rally is upward
        print(f"1. Rally Direction: ${ar.sc_low} -> ${ar.ar_high}")
        assert ar.ar_high > ar.sc_low, "AR high must be above SC low (upward rally)"

        # 2. Rally meets threshold
        rally_pct = float(ar.rally_pct) * 100
        print(f"2. Rally Magnitude: {rally_pct:.2f}%")
        assert rally_pct >= 3.0, "Rally should be >= 3% for valid AR"

        # 3. Timing window
        print(f"3. Timing: {ar.bars_after_sc} bars after SC")
        assert 1 <= ar.bars_after_sc <= 10, "AR should occur within 1-10 bars"

        # 4. Volume profile
        print(f"4. Volume Profile: {ar.volume_profile}")
        if ar.volume_profile == "HIGH":
            print("   -> Strong demand absorption (bullish)")
        else:
            print("   -> Weak relief rally (less bullish)")
        assert ar.volume_profile in ["HIGH", "NORMAL"], "Volume profile must be HIGH or NORMAL"

        # 5. SC reference integrity
        print(f"5. SC Reference: {ar.sc_reference['bar']['timestamp']}")
        assert ar.sc_reference is not None, "AR must reference SC"
        assert (
            ar.sc_reference["bar"]["timestamp"] == sc.bar["timestamp"]
        ), "AR must reference correct SC"

        print("\n[OK] All Wyckoff AR characteristics validated")
        print(f"[OK] Phase A sequence: SC ({sc.bar['timestamp']}) -> AR ({ar.bar['timestamp']})")

    def test_ar_timing_within_10_bars(self, aapl_bars):
        """
        Test that AR occurs within 10-bar timeout window.

        AC 2, 10: AR should occur within 5 bars (ideal), 10 bars (timeout).

        If no AR within 10 bars, SC is invalidated (no demand).
        """
        # Analyze volume
        volume_analyzer = VolumeAnalyzer()
        volume_analysis = volume_analyzer.analyze(aapl_bars)

        # Detect SC
        sc = detect_selling_climax(aapl_bars, volume_analysis)
        assert sc is not None, "SC should be detected"

        # Detect AR
        ar = detect_automatic_rally(aapl_bars, sc, volume_analysis)

        # For AAPL March 2020, AR should be detected
        assert ar is not None, "AR should be detected in March 2020 (strong demand)"

        # Validate timing
        print("\n=== AR Timing Validation ===")
        print(f"SC Date: {sc.bar['timestamp']}")
        print(f"AR Date: {ar.bar['timestamp']}")
        print(f"Bars After SC: {ar.bars_after_sc}")

        assert ar.bars_after_sc <= 10, f"AR must occur within 10 bars, got {ar.bars_after_sc}"

        if ar.bars_after_sc <= 5:
            print("[OK] AR within ideal window (≤5 bars)")
        else:
            print("[WARN] AR delayed but valid (6-10 bars)")

    def test_ar_volume_profile_classification(self, aapl_bars):
        """
        Test volume profile classification for AR.

        AC 4: Volume on rally can be normal or high.

        HIGH volume (>=1.2x): Strong demand absorption (bullish)
        NORMAL volume (<1.2x): Weak relief rally (less bullish)
        """
        # Analyze volume
        volume_analyzer = VolumeAnalyzer()
        volume_analysis = volume_analyzer.analyze(aapl_bars)

        # Detect SC
        sc = detect_selling_climax(aapl_bars, volume_analysis)
        assert sc is not None

        # Detect AR
        ar = detect_automatic_rally(aapl_bars, sc, volume_analysis)
        assert ar is not None

        # Find AR bar in volume_analysis
        ar_timestamp = datetime.fromisoformat(ar.bar["timestamp"])
        ar_volume_analysis = None
        for i, bar in enumerate(aapl_bars):
            if bar.timestamp == ar_timestamp:
                ar_volume_analysis = volume_analysis[i]
                break

        assert ar_volume_analysis is not None, "AR volume analysis should be found"

        print("\n=== AR Volume Profile Classification ===")
        print(f"AR Date: {ar_timestamp.date()}")
        print(
            f"Volume Ratio: {float(ar_volume_analysis.volume_ratio) if ar_volume_analysis.volume_ratio else 'N/A'}x"
        )
        print(f"Volume Profile: {ar.volume_profile}")

        # Validate classification
        if ar.volume_profile == "HIGH":
            print("[OK] HIGH volume - Strong demand absorption (bullish)")
            if ar_volume_analysis.volume_ratio:
                assert ar_volume_analysis.volume_ratio >= Decimal(
                    "1.2"
                ), "HIGH profile requires volume_ratio >= 1.2"
        else:
            print("[OK] NORMAL volume - Weak relief rally (less bullish)")

        print("\nInterpretation:")
        if ar.volume_profile == "HIGH":
            print("  -> Strong buying interest after SC")
            print("  -> Smart money accumulating")
            print("  -> Phase A strong foundation")
        else:
            print("  -> Weak buying interest")
            print("  -> Cautious accumulation")
            print("  -> Monitor for Secondary Test confirmation")
