"""
Sample OHLCV fixture data for SPY 1d timeframe.

Represents a realistic Wyckoff accumulation pattern (Phase A through C):
- Phase A (bars 0-7): Selling Climax with ultra-high volume, Automatic Rally,
  Secondary Test
- Phase B (bars 8-27): Trading range with lower volume, tests of support/resistance
- Phase C (bars 28-34): Spring below support with low volume, then test hold

Volume profile follows Wyckoff rules:
- SC: 2-3x average volume
- ST: moderate volume (0.8-1.2x)
- Phase B: declining volume
- Spring: low volume (< 0.7x average)
- SOS breakout after spring: high volume (> 1.5x)

All prices are representative of SPY (S&P 500 ETF) in a realistic range.
"""

from typing import TypedDict


class BarDict(TypedDict):
    timestamp: str
    open: str
    high: str
    low: str
    close: str
    volume: int


# 50 daily bars for SPY, representing a Wyckoff accumulation pattern.
# Each bar: (timestamp_iso, open, high, low, close, volume)
# Timestamps are ISO 8601 UTC strings starting 2025-06-02 (Mon).
SAMPLE_BARS: list[BarDict] = [
    # ========================================================================
    # Phase A: Selling Climax & Automatic Rally (bars 0-7)
    # ========================================================================
    # Bar 0: Normal decline leading into range
    {
        "timestamp": "2025-06-02T20:00:00+00:00",
        "open": "445.50",
        "high": "446.20",
        "low": "441.80",
        "close": "442.30",
        "volume": 82_000_000,
    },
    # Bar 1: Accelerating sell-off
    {
        "timestamp": "2025-06-03T20:00:00+00:00",
        "open": "442.00",
        "high": "443.10",
        "low": "438.50",
        "close": "439.00",
        "volume": 95_000_000,
    },
    # Bar 2: SELLING CLIMAX (SC) - Ultra-high volume down move
    # close_position = (435.50 - 430.20) / (439.50 - 430.20) ≈ 0.57 (must be >= 0.50)
    # spread = 439.50 - 430.20 = 9.30, volume_ratio ≈ 2.3x avg
    {
        "timestamp": "2025-06-04T20:00:00+00:00",
        "open": "438.80",
        "high": "439.50",
        "low": "430.20",
        "close": "435.50",
        "volume": 185_000_000,
    },
    # Bar 3: AUTOMATIC RALLY (AR) - Bounce on high volume
    {
        "timestamp": "2025-06-05T20:00:00+00:00",
        "open": "432.00",
        "high": "440.00",
        "low": "431.00",
        "close": "438.80",
        "volume": 140_000_000,
    },
    # Bar 4: AR continuation
    {
        "timestamp": "2025-06-06T20:00:00+00:00",
        "open": "439.00",
        "high": "442.50",
        "low": "437.80",
        "close": "441.50",
        "volume": 110_000_000,
    },
    # Bar 5: Secondary Test (ST) - retest of SC low on lower volume
    {
        "timestamp": "2025-06-09T20:00:00+00:00",
        "open": "441.00",
        "high": "441.80",
        "low": "432.50",
        "close": "433.80",
        "volume": 88_000_000,
    },
    # Bar 6: ST holds above SC low
    {
        "timestamp": "2025-06-10T20:00:00+00:00",
        "open": "434.00",
        "high": "437.20",
        "low": "431.80",
        "close": "436.00",
        "volume": 78_000_000,
    },
    # Bar 7: Recovery from ST
    {
        "timestamp": "2025-06-11T20:00:00+00:00",
        "open": "436.50",
        "high": "439.00",
        "low": "435.00",
        "close": "438.20",
        "volume": 72_000_000,
    },
    # ========================================================================
    # Phase B: Trading range with declining volume (bars 8-27)
    # Support ~430, Resistance (Ice) ~442
    # ========================================================================
    # Bar 8
    {
        "timestamp": "2025-06-12T20:00:00+00:00",
        "open": "438.00",
        "high": "441.00",
        "low": "436.50",
        "close": "440.20",
        "volume": 68_000_000,
    },
    # Bar 9
    {
        "timestamp": "2025-06-13T20:00:00+00:00",
        "open": "440.00",
        "high": "442.80",
        "low": "439.00",
        "close": "441.50",
        "volume": 65_000_000,
    },
    # Bar 10 - test of Ice (resistance)
    {
        "timestamp": "2025-06-16T20:00:00+00:00",
        "open": "441.80",
        "high": "443.20",
        "low": "440.00",
        "close": "440.80",
        "volume": 70_000_000,
    },
    # Bar 11 - pull back
    {
        "timestamp": "2025-06-17T20:00:00+00:00",
        "open": "440.50",
        "high": "441.00",
        "low": "437.00",
        "close": "437.50",
        "volume": 62_000_000,
    },
    # Bar 12
    {
        "timestamp": "2025-06-18T20:00:00+00:00",
        "open": "437.80",
        "high": "439.50",
        "low": "436.00",
        "close": "438.50",
        "volume": 58_000_000,
    },
    # Bar 13 - test of support
    {
        "timestamp": "2025-06-19T20:00:00+00:00",
        "open": "438.00",
        "high": "438.80",
        "low": "432.50",
        "close": "433.20",
        "volume": 72_000_000,
    },
    # Bar 14 - bounce from support
    {
        "timestamp": "2025-06-20T20:00:00+00:00",
        "open": "433.50",
        "high": "436.80",
        "low": "432.00",
        "close": "435.80",
        "volume": 66_000_000,
    },
    # Bar 15
    {
        "timestamp": "2025-06-23T20:00:00+00:00",
        "open": "436.00",
        "high": "438.50",
        "low": "435.00",
        "close": "437.80",
        "volume": 55_000_000,
    },
    # Bar 16
    {
        "timestamp": "2025-06-24T20:00:00+00:00",
        "open": "438.00",
        "high": "440.50",
        "low": "437.00",
        "close": "439.50",
        "volume": 52_000_000,
    },
    # Bar 17 - mid-range
    {
        "timestamp": "2025-06-25T20:00:00+00:00",
        "open": "439.80",
        "high": "441.50",
        "low": "438.50",
        "close": "440.80",
        "volume": 50_000_000,
    },
    # Bar 18
    {
        "timestamp": "2025-06-26T20:00:00+00:00",
        "open": "441.00",
        "high": "442.00",
        "low": "439.00",
        "close": "439.50",
        "volume": 48_000_000,
    },
    # Bar 19 - slight dip
    {
        "timestamp": "2025-06-27T20:00:00+00:00",
        "open": "439.20",
        "high": "440.00",
        "low": "436.50",
        "close": "437.00",
        "volume": 54_000_000,
    },
    # Bar 20
    {
        "timestamp": "2025-06-30T20:00:00+00:00",
        "open": "437.20",
        "high": "439.00",
        "low": "435.80",
        "close": "438.50",
        "volume": 50_000_000,
    },
    # Bar 21
    {
        "timestamp": "2025-07-01T20:00:00+00:00",
        "open": "438.80",
        "high": "441.00",
        "low": "438.00",
        "close": "440.50",
        "volume": 47_000_000,
    },
    # Bar 22 - test of Ice
    {
        "timestamp": "2025-07-02T20:00:00+00:00",
        "open": "440.80",
        "high": "443.00",
        "low": "440.00",
        "close": "441.20",
        "volume": 58_000_000,
    },
    # Bar 23 - pull back from Ice
    {
        "timestamp": "2025-07-03T20:00:00+00:00",
        "open": "441.00",
        "high": "441.50",
        "low": "438.00",
        "close": "438.50",
        "volume": 45_000_000,
    },
    # Bar 24
    {
        "timestamp": "2025-07-07T20:00:00+00:00",
        "open": "438.80",
        "high": "440.00",
        "low": "436.50",
        "close": "437.20",
        "volume": 48_000_000,
    },
    # Bar 25 - drift toward support
    {
        "timestamp": "2025-07-08T20:00:00+00:00",
        "open": "437.00",
        "high": "438.50",
        "low": "434.50",
        "close": "435.00",
        "volume": 52_000_000,
    },
    # Bar 26 - near support
    {
        "timestamp": "2025-07-09T20:00:00+00:00",
        "open": "435.20",
        "high": "436.80",
        "low": "433.00",
        "close": "434.00",
        "volume": 55_000_000,
    },
    # Bar 27 - Phase B test of support
    {
        "timestamp": "2025-07-10T20:00:00+00:00",
        "open": "434.00",
        "high": "436.50",
        "low": "431.50",
        "close": "435.50",
        "volume": 60_000_000,
    },
    # ========================================================================
    # Phase C: Spring (bars 28-34)
    # Creek/support ~430.20 (SC low). Spring dips below then recovers on LOW volume.
    # ========================================================================
    # Bar 28 - approach to support
    {
        "timestamp": "2025-07-11T20:00:00+00:00",
        "open": "435.00",
        "high": "436.00",
        "low": "432.00",
        "close": "432.50",
        "volume": 50_000_000,
    },
    # Bar 29 - drift lower
    {
        "timestamp": "2025-07-14T20:00:00+00:00",
        "open": "432.20",
        "high": "433.50",
        "low": "430.80",
        "close": "431.00",
        "volume": 48_000_000,
    },
    # Bar 30 - SPRING: dip below SC low (430.20) on LOW volume
    {
        "timestamp": "2025-07-15T20:00:00+00:00",
        "open": "431.00",
        "high": "431.50",
        "low": "428.80",
        "close": "430.50",
        "volume": 38_000_000,
    },
    # Bar 31 - Spring test: holds above support on very low volume
    {
        "timestamp": "2025-07-16T20:00:00+00:00",
        "open": "430.80",
        "high": "433.00",
        "low": "429.50",
        "close": "432.50",
        "volume": 35_000_000,
    },
    # Bar 32 - Recovery from Spring
    {
        "timestamp": "2025-07-17T20:00:00+00:00",
        "open": "432.80",
        "high": "436.50",
        "low": "432.00",
        "close": "435.80",
        "volume": 55_000_000,
    },
    # Bar 33 - Continued recovery
    {
        "timestamp": "2025-07-18T20:00:00+00:00",
        "open": "436.00",
        "high": "439.50",
        "low": "435.50",
        "close": "438.80",
        "volume": 62_000_000,
    },
    # Bar 34 - approaching Ice from below
    {
        "timestamp": "2025-07-21T20:00:00+00:00",
        "open": "439.00",
        "high": "441.80",
        "low": "438.00",
        "close": "441.00",
        "volume": 68_000_000,
    },
    # ========================================================================
    # Phase D: SOS breakout above Ice (bars 35-42)
    # Ice level ~442. SOS breaks above on HIGH volume (> 1.5x avg).
    # ========================================================================
    # Bar 35 - testing Ice
    {
        "timestamp": "2025-07-22T20:00:00+00:00",
        "open": "441.20",
        "high": "442.80",
        "low": "440.00",
        "close": "442.20",
        "volume": 72_000_000,
    },
    # Bar 36 - SOS breakout above Ice on high volume
    {
        "timestamp": "2025-07-23T20:00:00+00:00",
        "open": "442.50",
        "high": "447.00",
        "low": "442.00",
        "close": "446.20",
        "volume": 125_000_000,
    },
    # Bar 37 - SOS continuation
    {
        "timestamp": "2025-07-24T20:00:00+00:00",
        "open": "446.50",
        "high": "449.00",
        "low": "445.50",
        "close": "448.00",
        "volume": 108_000_000,
    },
    # Bar 38 - consolidation above Ice
    {
        "timestamp": "2025-07-25T20:00:00+00:00",
        "open": "448.20",
        "high": "449.50",
        "low": "446.00",
        "close": "447.50",
        "volume": 78_000_000,
    },
    # Bar 39 - LPS: pullback retest of Ice level, holds
    {
        "timestamp": "2025-07-28T20:00:00+00:00",
        "open": "447.00",
        "high": "447.80",
        "low": "442.50",
        "close": "443.50",
        "volume": 65_000_000,
    },
    # Bar 40 - LPS test holds
    {
        "timestamp": "2025-07-29T20:00:00+00:00",
        "open": "443.80",
        "high": "445.50",
        "low": "442.00",
        "close": "444.80",
        "volume": 58_000_000,
    },
    # Bar 41 - resumption
    {
        "timestamp": "2025-07-30T20:00:00+00:00",
        "open": "445.00",
        "high": "448.50",
        "low": "444.50",
        "close": "447.80",
        "volume": 72_000_000,
    },
    # Bar 42 - strong move
    {
        "timestamp": "2025-07-31T20:00:00+00:00",
        "open": "448.00",
        "high": "451.00",
        "low": "447.00",
        "close": "450.20",
        "volume": 88_000_000,
    },
    # ========================================================================
    # Phase E: Markup (bars 43-49)
    # ========================================================================
    # Bar 43
    {
        "timestamp": "2025-08-01T20:00:00+00:00",
        "open": "450.50",
        "high": "453.00",
        "low": "449.80",
        "close": "452.00",
        "volume": 82_000_000,
    },
    # Bar 44
    {
        "timestamp": "2025-08-04T20:00:00+00:00",
        "open": "452.20",
        "high": "454.50",
        "low": "451.00",
        "close": "453.80",
        "volume": 75_000_000,
    },
    # Bar 45
    {
        "timestamp": "2025-08-05T20:00:00+00:00",
        "open": "454.00",
        "high": "456.00",
        "low": "452.50",
        "close": "455.20",
        "volume": 70_000_000,
    },
    # Bar 46 - minor pullback
    {
        "timestamp": "2025-08-06T20:00:00+00:00",
        "open": "455.00",
        "high": "455.80",
        "low": "452.00",
        "close": "453.50",
        "volume": 62_000_000,
    },
    # Bar 47
    {
        "timestamp": "2025-08-07T20:00:00+00:00",
        "open": "453.80",
        "high": "456.50",
        "low": "453.00",
        "close": "455.80",
        "volume": 68_000_000,
    },
    # Bar 48
    {
        "timestamp": "2025-08-08T20:00:00+00:00",
        "open": "456.00",
        "high": "458.20",
        "low": "455.00",
        "close": "457.50",
        "volume": 72_000_000,
    },
    # Bar 49 - continued markup
    {
        "timestamp": "2025-08-11T20:00:00+00:00",
        "open": "457.80",
        "high": "460.00",
        "low": "456.50",
        "close": "459.00",
        "volume": 78_000_000,
    },
]

SAMPLE_SYMBOL = "SPY"
SAMPLE_TIMEFRAME = "1d"
