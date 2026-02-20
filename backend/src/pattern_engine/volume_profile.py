"""
Volume Profile by Wyckoff Phase computation.

Computes VPVR (Volume Profile Visible Range) segmented by Wyckoff phase.
Uses the "typical price" approach: (H + L + 2*C) / 4 per bar,
assigning all bar volume to the single bin closest to that price.

Victoria (Volume Analyst) validation notes:
- POC locations tell the accumulation/distribution story
- Phase C accumulation should show LOWER volume than Phase A (Spring = low volume)
- High-volume nodes (HVN) indicate support/resistance consolidation
- Low-volume nodes (LVN) indicate price imbalance / fast movement
"""

from __future__ import annotations

import structlog

from src.models.ohlcv import OHLCVBar
from src.models.volume_profile import (
    PhaseVolumeData,
    VolumeProfileBin,
    VolumeProfileResponse,
)

logger = structlog.get_logger(__name__)


def compute_volume_profile_by_phase(
    bars: list[OHLCVBar],
    phase_labels: list[str],
    num_bins: int = 50,
) -> VolumeProfileResponse:
    """
    Compute VPVR segmented by Wyckoff phase.

    Algorithm:
    1. Find price range across all bars.
    2. Create num_bins equal-width price bins.
    3. For each bar, compute typical price = (H + L + 2*C) / 4,
       assign all volume to the bin containing that price.
    4. Per phase: compute pct_of_phase_volume, POC, and 70% value area.

    Args:
        bars: OHLCV data in chronological order.
        phase_labels: Phase label per bar ("A", "B", "C", "D", "E").
                      Must be same length as bars.
        num_bins: Number of price bins (20-100).

    Returns:
        VolumeProfileResponse with per-phase and combined profiles.

    Raises:
        ValueError: If bars is empty or lengths mismatch.
    """
    if not bars:
        raise ValueError("Cannot compute volume profile from empty bars")
    if len(bars) != len(phase_labels):
        raise ValueError(
            f"bars ({len(bars)}) and phase_labels ({len(phase_labels)}) length mismatch"
        )

    # 1. Overall price range
    overall_low = min(float(b.low) for b in bars)
    overall_high = max(float(b.high) for b in bars)

    # Guard against zero range (all bars same price)
    if overall_high == overall_low:
        overall_high = overall_low + 1.0

    bin_width = (overall_high - overall_low) / num_bins

    # 2. Build empty bin arrays keyed by phase and "COMBINED"
    phases_seen: set[str] = set(phase_labels)
    # phase -> list of volumes per bin (index 0..num_bins-1)
    phase_volumes: dict[str, list[float]] = {}
    phase_bar_counts: dict[str, int] = {}
    for phase in phases_seen:
        phase_volumes[phase] = [0.0] * num_bins
        phase_bar_counts[phase] = 0
    combined_volumes: list[float] = [0.0] * num_bins

    # 3. Distribute volume into bins
    for bar, phase in zip(bars, phase_labels, strict=True):
        h = float(bar.high)
        low_price = float(bar.low)
        c = float(bar.close)
        typical = (h + low_price + 2.0 * c) / 4.0
        vol = float(bar.volume)

        # Determine bin index (clamp to valid range)
        idx = int((typical - overall_low) / bin_width)
        idx = max(0, min(idx, num_bins - 1))

        phase_volumes[phase][idx] += vol
        combined_volumes[idx] += vol
        phase_bar_counts[phase] = phase_bar_counts.get(phase, 0) + 1

    # 4. Build PhaseVolumeData for each phase and combined
    def _build_phase_data(
        phase_label: str,
        volumes: list[float],
        bar_count: int,
    ) -> PhaseVolumeData:
        total_vol = sum(volumes)
        bins: list[VolumeProfileBin] = []

        # Find POC (bin with max volume)
        poc_idx = 0
        max_vol = 0.0
        for i, v in enumerate(volumes):
            if v > max_vol:
                max_vol = v
                poc_idx = i

        # Value area: 70% of total volume around POC
        va_low_idx, va_high_idx = _compute_value_area(volumes, poc_idx, 0.70)

        for i, v in enumerate(volumes):
            p_low = overall_low + i * bin_width
            p_high = p_low + bin_width
            p_mid = (p_low + p_high) / 2.0
            pct = v / total_vol if total_vol > 0 else 0.0

            bins.append(
                VolumeProfileBin(
                    price_level=round(p_mid, 6),
                    price_low=round(p_low, 6),
                    price_high=round(p_high, 6),
                    volume=round(v, 4),
                    pct_of_phase_volume=round(pct, 6),
                    is_poc=(i == poc_idx and total_vol > 0),
                    in_value_area=(va_low_idx <= i <= va_high_idx and total_vol > 0),
                )
            )

        poc_price = (
            round((overall_low + poc_idx * bin_width + bin_width / 2), 6) if total_vol > 0 else None
        )
        va_low_price = round(overall_low + va_low_idx * bin_width, 6) if total_vol > 0 else None
        va_high_price = (
            round(overall_low + (va_high_idx + 1) * bin_width, 6) if total_vol > 0 else None
        )

        return PhaseVolumeData(
            phase=phase_label,
            bins=bins,
            poc_price=poc_price,
            total_volume=round(total_vol, 4),
            bar_count=bar_count,
            value_area_low=va_low_price,
            value_area_high=va_high_price,
        )

    phases_data: list[PhaseVolumeData] = []
    for phase in sorted(phases_seen):
        phases_data.append(_build_phase_data(phase, phase_volumes[phase], phase_bar_counts[phase]))

    combined_data = _build_phase_data("COMBINED", combined_volumes, len(bars))

    current_price = float(bars[-1].close) if bars else None

    return VolumeProfileResponse(
        symbol=bars[0].symbol,
        timeframe=bars[0].timeframe,
        price_range_low=round(overall_low, 6),
        price_range_high=round(overall_high, 6),
        bin_width=round(bin_width, 6),
        num_bins=num_bins,
        phases=phases_data,
        combined=combined_data,
        current_price=current_price,
    )


def _compute_value_area(
    volumes: list[float],
    poc_idx: int,
    target_pct: float,
) -> tuple[int, int]:
    """
    Compute value area indices containing target_pct of total volume.

    Expands outward from POC, one step at a time, adding the side
    with more volume until the target percentage is reached.

    Returns:
        (low_idx, high_idx) inclusive range of bin indices.
    """
    total = sum(volumes)
    if total == 0:
        return (0, len(volumes) - 1)

    accumulated = volumes[poc_idx]
    lo = poc_idx
    hi = poc_idx

    while accumulated / total < target_pct:
        # Check which side to expand
        left_vol = volumes[lo - 1] if lo > 0 else -1.0
        right_vol = volumes[hi + 1] if hi < len(volumes) - 1 else -1.0

        if left_vol < 0 and right_vol < 0:
            break  # Can't expand further

        if left_vol >= right_vol:
            lo -= 1
            accumulated += volumes[lo]
        else:
            hi += 1
            accumulated += volumes[hi]

    return (lo, hi)
