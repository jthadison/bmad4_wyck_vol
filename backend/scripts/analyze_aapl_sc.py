"""
Quick analysis script to examine AAPL data for Selling Climax detection.
This helps William (Wyckoff mentor) teach SC zone vs. multiple SC identification.
"""

import sys
from pathlib import Path
from decimal import Decimal
from datetime import datetime, timezone
import pandas as pd

# Add backend to path
backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

from src.models.ohlcv import OHLCVBar
from src.models.volume_analysis import VolumeAnalysis
from src.pattern_engine.volume_analyzer import VolumeAnalyzer
from src.pattern_engine.phase_detector import detect_selling_climax


def load_aapl_csv(csv_path: str) -> list[OHLCVBar]:
    """Load AAPL data from CSV into OHLCVBar objects."""
    df = pd.read_csv(csv_path)

    bars = []
    for _, row in df.iterrows():
        bar = OHLCVBar(
            symbol="AAPL",
            timeframe="1d",
            timestamp=datetime.fromisoformat(row['timestamp']).replace(tzinfo=timezone.utc),
            open=Decimal(str(row['open'])),
            high=Decimal(str(row['high'])),
            low=Decimal(str(row['low'])),
            close=Decimal(str(row['close'])),
            volume=int(row['volume']),
            spread=Decimal(str(row['high'])) - Decimal(str(row['low']))
        )
        bars.append(bar)

    # Reverse to chronological order (CSV is newest first)
    return list(reversed(bars))


def find_all_potential_scs(bars: list[OHLCVBar], volume_analysis: list[VolumeAnalysis]) -> list[dict]:
    """
    Find ALL bars that meet SC criteria (not just first).
    This helps identify if we have multiple separate SCs or one SC zone.
    """
    from src.models.effort_result import EffortResult

    potential_scs = []

    for i, analysis in enumerate(volume_analysis):
        if i == 0:
            continue  # Skip first bar

        # Check SC criteria (same as detect_selling_climax)
        if analysis.effort_result != EffortResult.CLIMACTIC:
            continue

        if (analysis.volume_ratio is None or analysis.spread_ratio is None or
            analysis.volume_ratio < Decimal("2.0") or analysis.spread_ratio < Decimal("1.5")):
            continue

        close_position = analysis.close_position
        if close_position is None:
            current_bar = bars[i]
            if current_bar.spread > 0:
                close_position = (current_bar.close - current_bar.low) / current_bar.spread
            else:
                close_position = Decimal("0.5")

        if close_position < Decimal("0.5"):
            continue

        current_bar = bars[i]
        prior_bar = bars[i - 1]

        if current_bar.close >= prior_bar.close:
            continue

        # This bar meets ALL SC criteria
        potential_scs.append({
            'index': i,
            'date': current_bar.timestamp.strftime('%Y-%m-%d'),
            'low': float(current_bar.low),
            'close': float(current_bar.close),
            'volume': current_bar.volume,
            'volume_ratio': float(analysis.volume_ratio),
            'spread_ratio': float(analysis.spread_ratio),
            'close_position': float(close_position),
            'bars_since_previous': 0 if not potential_scs else i - potential_scs[-1]['index']
        })

    return potential_scs


def main():
    """Analyze AAPL data for SC detection patterns."""
    print("=" * 80)
    print("William's AAPL Selling Climax Analysis")
    print("=" * 80)
    print()

    # Load data
    csv_path = backend_dir.parent / "daily_AAPL.csv"
    if not csv_path.exists():
        print(f"[X] CSV file not found: {csv_path}")
        return

    print(f"[*] Loading AAPL data from: {csv_path}")
    bars = load_aapl_csv(str(csv_path))
    print(f"[OK] Loaded {len(bars)} bars")
    print(f"   Date range: {bars[0].timestamp.date()} to {bars[-1].timestamp.date()}")
    print()

    # Analyze volume
    print("[*] Analyzing volume characteristics...")
    volume_analyzer = VolumeAnalyzer()
    volume_analysis = volume_analyzer.analyze(bars)
    print(f"[OK] Volume analysis complete")
    print()

    # Find first SC (standard detection)
    print("[*] Running standard SC detection (returns FIRST valid SC)...")
    sc = detect_selling_climax(bars, volume_analysis)

    if sc:
        print(f"[OK] SC Detected:")
        print(f"   Date: {sc.bar['timestamp']}")
        print(f"   Low: ${sc.bar['low']}")
        print(f"   Close: ${sc.bar['close']}")
        print(f"   Volume Ratio: {float(sc.volume_ratio):.2f}x")
        print(f"   Spread Ratio: {float(sc.spread_ratio):.2f}x")
        print(f"   Close Position: {float(sc.close_position):.2f}")
        print(f"   Confidence: {sc.confidence}%")
    else:
        print("[X] No SC detected")
    print()

    # Find ALL potential SCs
    print("[*] Finding ALL bars that meet SC criteria...")
    all_scs = find_all_potential_scs(bars, volume_analysis)

    if not all_scs:
        print("[X] No bars meet SC criteria")
        return

    print(f"[OK] Found {len(all_scs)} bar(s) meeting SC criteria:")
    print()

    # Print table
    print(f"{'#':<4} {'Date':<12} {'Low':>10} {'Close':>10} {'Vol Ratio':>10} {'Spread':>8} {'ClosePos':>9} {'Days Gap':>9}")
    print("-" * 80)

    for i, sc_data in enumerate(all_scs, 1):
        print(f"{i:<4} {sc_data['date']:<12} ${sc_data['low']:>9.2f} ${sc_data['close']:>9.2f} "
              f"{sc_data['volume_ratio']:>9.2f}x {sc_data['spread_ratio']:>7.2f}x "
              f"{sc_data['close_position']:>8.2f} {sc_data['bars_since_previous']:>9}")

    print()
    print("=" * 80)
    print("Wyckoff Teaching Analysis")
    print("=" * 80)

    if len(all_scs) == 1:
        print("[OK] Single SC Event")
        print("   This is a clean, single Selling Climax.")
        print("   Your algorithm's 'first SC' approach is perfect here.")
    else:
        print(f"[!]  Multiple SC Candidates ({len(all_scs)} bars)")
        print()

        # Analyze clustering
        max_gap = max(sc['bars_since_previous'] for sc in all_scs[1:]) if len(all_scs) > 1 else 0

        if max_gap <= 10:
            print("[WYCKOFF] ASSESSMENT: This appears to be ONE MULTI-BAR SC ZONE")
            print(f"   All SC bars occur within {max_gap} days of each other")
            print("   This represents EXTENDED climactic selling, not separate events")
            print()
            print("   Wyckoff Interpretation:")
            print("   - Multiple waves of panic selling")
            print("   - Extended exhaustion process")
            print("   - True 'bottom' likely at LAST climactic bar")
            print()
            print(f"   [ALGO] Your algorithm returns: {all_scs[0]['date']} (FIRST bar)")
            print(f"   [THEORY] Wyckoff theory suggests: {all_scs[-1]['date']} (LAST bar)")
            print()
            print("   [ENHANCE] Story 4.1.5 Enhancement Needed:")
            print("      - Detect SC zones (multiple climactic bars within 10 days)")
            print("      - Return zone start, zone end, and final exhaustion point")
            print("      - AR detection (Story 4.2) should use zone END as reference")
        else:
            print("[WYCKOFF] ASSESSMENT: These appear to be SEPARATE SC EVENTS")
            print(f"   Maximum gap: {max_gap} days (too long for single zone)")
            print("   These are likely distinct accumulation attempts or failed bottoms")
            print()
            print("   [ALGO] Your algorithm's 'first SC' approach is CORRECT")
            print("      The first SC marks the initial accumulation attempt")
            print("      Subsequent SCs are likely Secondary Tests or new attempts")

    print()
    print("=" * 80)
    print("Next Steps for Story 4.2 (AR Detection)")
    print("=" * 80)

    if sc and len(all_scs) > 1:
        first_sc_idx = next(i for i, bar in enumerate(bars) if bar.timestamp.isoformat() == sc.bar['timestamp'])
        print(f"[OK] AR Detection will start from: {sc.bar['timestamp']}")
        print(f"   Looking for 3%+ rally from low: ${sc.bar['low']}")
        print(f"   Window: Next 5-10 bars after index {first_sc_idx}")
        print()
        print("[!]  Note: If multiple SC bars exist, AR might fail because:")
        print("   - Continued selling pressure prevents rally")
        print("   - True AR occurs after LAST SC bar, not first")
        print()
        print("[TEACH] This is why multi-bar SC zone detection matters!")
    elif sc:
        print(f"[OK] Clean single SC at: {sc.bar['timestamp']}")
        print(f"   AR detection ready to proceed from low: ${sc.bar['low']}")


if __name__ == "__main__":
    main()
