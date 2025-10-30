"""
Visual validation script for pivot detection.

This script generates realistic price data, detects pivots, and creates
a matplotlib chart with pivots marked visually to confirm they align
with swing points.

Requirements:
    pip install matplotlib (optional dependency for visualization)

Usage:
    python backend/scripts/visualize_pivots.py
"""

import os
import sys

# Add src to path for imports (must be before model imports)
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

# ruff: noqa: E402 - Module imports must come after sys.path modification
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import matplotlib.pyplot as plt
import numpy as np
from models.ohlcv import OHLCVBar
from pattern_engine.pivot_detector import detect_pivots, get_pivot_highs, get_pivot_lows


def generate_realistic_bars(num_bars: int = 252, symbol: str = "AAPL") -> list[OHLCVBar]:
    """
    Generate realistic OHLCV bars for visualization.

    Args:
        num_bars: Number of bars to generate (default 252 = 1 year daily)
        symbol: Stock symbol

    Returns:
        List of OHLCVBar objects
    """
    bars = []
    base_price = 170.0
    base_timestamp = datetime(2024, 1, 1, tzinfo=UTC)

    np.random.seed(42)  # For reproducibility

    for i in range(num_bars):
        # Create trend component with sine wave
        trend = np.sin(i / 20) * 10

        # Add random walk
        noise = np.random.randn() * 2

        # Calculate OHLC
        close = base_price + trend + noise
        open_price = close + np.random.randn() * 0.5
        high = max(open_price, close) + abs(np.random.randn() * 1.5)
        low = min(open_price, close) - abs(np.random.randn() * 1.5)

        timestamp = base_timestamp + timedelta(days=i)
        spread = high - low

        bar = OHLCVBar(
            symbol=symbol,
            timeframe="1d",
            timestamp=timestamp,
            open=Decimal(str(round(open_price, 2))),
            high=Decimal(str(round(high, 2))),
            low=Decimal(str(round(low, 2))),
            close=Decimal(str(round(close, 2))),
            volume=int(1_000_000 + np.random.randint(-200_000, 200_000)),
            spread=Decimal(str(round(spread, 2))),
        )
        bars.append(bar)

    return bars


def visualize_pivots(
    bars: list[OHLCVBar], lookback: int = 5, save_path: str = None
) -> None:
    """
    Visualize pivot points on a price chart.

    Args:
        bars: List of OHLCV bars
        lookback: Lookback value for pivot detection
        save_path: Path to save chart (optional, default: output/pivot_validation_{symbol}.png)
    """
    # Detect pivots
    pivots = detect_pivots(bars, lookback=lookback)
    pivot_highs = get_pivot_highs(pivots)
    pivot_lows = get_pivot_lows(pivots)

    symbol = bars[0].symbol if bars else "UNKNOWN"

    print(f"\n{'='*60}")
    print(f"Pivot Detection Visual Validation - {symbol}")
    print(f"{'='*60}")
    print(f"Bars analyzed: {len(bars)}")
    print(f"Lookback: {lookback}")
    print(f"Total pivots: {len(pivots)}")
    print(f"  - Pivot highs (resistance): {len(pivot_highs)}")
    print(f"  - Pivot lows (support): {len(pivot_lows)}")
    print(f"{'='*60}\n")

    # Create figure
    fig, ax = plt.subplots(figsize=(16, 8))

    # Extract data for plotting
    indices = list(range(len(bars)))
    closes = [float(bar.close) for bar in bars]
    highs = [float(bar.high) for bar in bars]
    lows = [float(bar.low) for bar in bars]

    # Plot price data
    ax.plot(indices, closes, label="Close Price", color="#2E86DE", linewidth=1.5, alpha=0.8)
    ax.fill_between(
        indices, lows, highs, alpha=0.1, color="#2E86DE", label="High-Low Range"
    )

    # Mark pivot highs (resistance)
    for p in pivot_highs:
        ax.scatter(
            p.index,
            float(p.price),
            marker="v",
            color="#EE5A6F",
            s=150,
            zorder=10,
            edgecolors="darkred",
            linewidths=1.5,
        )
        # Add price label
        ax.annotate(
            f"${p.price}",
            xy=(p.index, float(p.price)),
            xytext=(0, 10),
            textcoords="offset points",
            fontsize=7,
            ha="center",
            color="darkred",
            bbox={"boxstyle": "round,pad=0.3", "fc": "#EE5A6F", "alpha": 0.3, "ec": "none"},
        )

    # Mark pivot lows (support)
    for p in pivot_lows:
        ax.scatter(
            p.index,
            float(p.price),
            marker="^",
            color="#1DD1A1",
            s=150,
            zorder=10,
            edgecolors="darkgreen",
            linewidths=1.5,
        )
        # Add price label
        ax.annotate(
            f"${p.price}",
            xy=(p.index, float(p.price)),
            xytext=(0, -15),
            textcoords="offset points",
            fontsize=7,
            ha="center",
            color="darkgreen",
            bbox={"boxstyle": "round,pad=0.3", "fc": "#1DD1A1", "alpha": 0.3, "ec": "none"},
        )

    # Styling
    ax.set_title(
        f"{symbol} - Pivot Point Detection (Lookback={lookback})",
        fontsize=16,
        fontweight="bold",
        pad=20,
    )
    ax.set_xlabel("Bar Index", fontsize=12)
    ax.set_ylabel("Price ($)", fontsize=12)
    ax.grid(True, alpha=0.3, linestyle="--", linewidth=0.5)
    ax.legend(
        loc="upper left",
        fontsize=10,
        framealpha=0.9,
        labels=[
            "Close Price",
            "High-Low Range",
            f"Pivot High (Resistance) - {len(pivot_highs)}",
            f"Pivot Low (Support) - {len(pivot_lows)}",
        ],
    )

    # Add info box
    info_text = f"Total Pivots: {len(pivots)}\nHighs: {len(pivot_highs)} | Lows: {len(pivot_lows)}"
    ax.text(
        0.98,
        0.02,
        info_text,
        transform=ax.transAxes,
        fontsize=10,
        verticalalignment="bottom",
        horizontalalignment="right",
        bbox={"boxstyle": "round", "facecolor": "wheat", "alpha": 0.5},
    )

    plt.tight_layout()

    # Save figure
    if save_path is None:
        # Create output directory if it doesn't exist
        output_dir = os.path.join(os.path.dirname(__file__), "..", "..", "output")
        os.makedirs(output_dir, exist_ok=True)
        save_path = os.path.join(
            output_dir, f"pivot_validation_{symbol}_lb{lookback}.png"
        )

    plt.savefig(save_path, dpi=150, bbox_inches="tight")
    print(f"Chart saved to: {save_path}")

    # Show plot (comment out if running in headless environment)
    # plt.show()

    plt.close()


def main():
    """Main function to run visual validation."""
    print("\nGenerating test data...")

    # Test 1: AAPL with default lookback (5)
    bars_aapl = generate_realistic_bars(num_bars=252, symbol="AAPL")
    visualize_pivots(bars_aapl, lookback=5)

    # Test 2: AAPL with smaller lookback (3) - more sensitive
    visualize_pivots(bars_aapl, lookback=3)

    # Test 3: AAPL with larger lookback (10) - less sensitive
    visualize_pivots(bars_aapl, lookback=10)

    # Test 4: Different symbol
    bars_msft = generate_realistic_bars(num_bars=252, symbol="MSFT")
    visualize_pivots(bars_msft, lookback=5)

    print("\n✓ Visual validation complete!")
    print(
        "Review the generated charts in the 'output' directory to confirm pivots align with visual swing points.\n"
    )


if __name__ == "__main__":
    main()
