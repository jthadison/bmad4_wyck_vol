"""
Spring Timing Analyzer

This module provides timing analysis for Spring patterns, evaluating temporal
spacing between springs to assess campaign quality.

Timing Classifications:
-----------------------
- COMPRESSED (<10 bars avg): Warning - excessive testing, weak hands present
- NORMAL (10-25 bars): Standard accumulation pace
- HEALTHY (>25 bars): Ideal - strong absorption between tests
- SINGLE_SPRING: Only one spring detected

Wyckoff Principle:
------------------
Professional operators allow time for absorption between springs. Rapid
successive springs (compressed timing) indicate weak hands still dumping stock.

Author: Story 18.8.4 - Core Spring Detector and Facade
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog

if TYPE_CHECKING:
    from src.models.spring import Spring

logger = structlog.get_logger(__name__)

# Timing thresholds (in bars)
COMPRESSED_THRESHOLD = 10
HEALTHY_THRESHOLD = 25


def analyze_spring_timing(springs: list[Spring]) -> tuple[str, list[int], float]:
    """
    Analyze temporal spacing between springs for campaign quality assessment.

    Evaluates bar-to-bar intervals between successive springs to determine if
    the accumulation campaign exhibits professional characteristics (healthy spacing)
    or amateur/weak characteristics (compressed timing).

    Args:
        springs: Chronologically ordered list of detected springs

    Returns:
        tuple[timing_classification, intervals, avg_interval]
        - timing_classification: "COMPRESSED" | "NORMAL" | "HEALTHY" | "SINGLE_SPRING"
        - intervals: List of bar counts between successive springs
        - avg_interval: Average spacing (bars) between springs

    Examples:
        >>> timing, intervals, avg = analyze_spring_timing([spring1, spring2])
        >>> print(timing)  # "NORMAL"
        >>> print(avg)  # 15.0
    """
    if len(springs) < 2:
        logger.debug(
            "spring_timing_single_spring",
            spring_count=len(springs),
            message="Single spring detected - no timing analysis possible",
        )
        return ("SINGLE_SPRING", [], 0.0)

    # Calculate intervals between successive springs
    intervals = _calculate_intervals(springs)

    # Calculate average interval
    avg_interval = sum(intervals) / len(intervals)

    # Classify timing
    classification = _classify_timing(avg_interval, len(springs), intervals)

    return (classification, intervals, avg_interval)


def _calculate_intervals(springs: list[Spring]) -> list[int]:
    """Calculate bar intervals between successive springs."""
    return [springs[i + 1].bar_index - springs[i].bar_index for i in range(len(springs) - 1)]


def _classify_timing(
    avg_interval: float,
    spring_count: int,
    intervals: list[int],
) -> str:
    """Classify timing based on average interval."""
    if avg_interval < COMPRESSED_THRESHOLD:
        logger.warning(
            "spring_timing_compressed",
            spring_count=spring_count,
            intervals=intervals,
            avg_interval=avg_interval,
            message="COMPRESSED timing (<10 bars avg) - excessive testing",
        )
        return "COMPRESSED"

    if avg_interval < HEALTHY_THRESHOLD:
        logger.info(
            "spring_timing_normal",
            spring_count=spring_count,
            intervals=intervals,
            avg_interval=avg_interval,
            message="NORMAL timing (10-25 bars) - standard accumulation",
        )
        return "NORMAL"

    logger.info(
        "spring_timing_healthy",
        spring_count=spring_count,
        intervals=intervals,
        avg_interval=avg_interval,
        message="HEALTHY timing (>25 bars) - professional absorption",
    )
    return "HEALTHY"
