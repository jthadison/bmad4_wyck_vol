"""
Core Spring Pattern Detector

This module provides the core SpringDetectorCore class with dependency injection
for confidence scoring and risk analysis. It implements clean detection logic
with methods that don't exceed 30 lines and cyclomatic complexity <10.

FR Requirements:
----------------
- FR4: Spring detection (0-5% penetration below Creek)
- FR12: Volume validation (<0.7x average)
- FR15: Phase C only

Author: Story 18.8.4 - Core Spring Detector and Facade
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import ROUND_HALF_UP, Decimal
from typing import TYPE_CHECKING, Optional

import structlog

from src.models.forex import ForexSession, get_forex_session
from src.models.spring import Spring
from src.pattern_engine.detectors.spring.confidence_scorer import SpringConfidenceScorer
from src.pattern_engine.detectors.spring.models import SpringCandidate
from src.pattern_engine.detectors.spring.risk_analyzer import SpringRiskAnalyzer
from src.pattern_engine.scoring.scorer_factory import detect_asset_class, get_scorer
from src.pattern_engine.timeframe_config import SPRING_VOLUME_THRESHOLD
from src.pattern_engine.volume_analyzer import calculate_volume_ratio

if TYPE_CHECKING:
    from src.models.ohlcv import OHLCVBar
    from src.models.phase_classification import WyckoffPhase
    from src.models.trading_range import TradingRange
    from src.pattern_engine.intraday_volume_analyzer import IntradayVolumeAnalyzer
    from src.pattern_engine.volume_cache import VolumeCache

logger = structlog.get_logger(__name__)


@dataclass
class DetectionConfig:
    """Configuration for Spring detection."""

    timeframe: str = "1d"
    session_filter_enabled: bool = False
    session_confidence_scoring_enabled: bool = False
    store_rejected_patterns: bool = True
    max_penetration_pct: Decimal = Decimal("0.05")
    volume_threshold: Decimal = SPRING_VOLUME_THRESHOLD
    max_recovery_bars: int = 5


@dataclass
class CandidateResult:
    """Result from finding a spring candidate."""

    candidate: Optional[SpringCandidate]
    bar_index: int
    rejection_reason: Optional[str] = None


class SpringDetectorCore:
    """
    Core Spring Detection with Dependency Injection.

    This class provides clean spring pattern detection with injected dependencies
    for confidence scoring and risk analysis. All methods are designed to be
    under 30 lines with cyclomatic complexity <10.

    Usage:
    ------
    >>> scorer = SpringConfidenceScorer()
    >>> analyzer = SpringRiskAnalyzer()
    >>> detector = SpringDetectorCore(scorer, analyzer)
    >>> spring = detector.detect(trading_range, bars, phase, symbol)
    """

    def __init__(
        self,
        confidence_scorer: SpringConfidenceScorer,
        risk_analyzer: SpringRiskAnalyzer,
        volume_cache: Optional[VolumeCache] = None,
        config: Optional[DetectionConfig] = None,
    ):
        """
        Initialize SpringDetectorCore with injected dependencies.

        Args:
            confidence_scorer: Scorer for calculating spring confidence
            risk_analyzer: Analyzer for risk profile calculation
            volume_cache: Optional cache for O(1) volume ratio lookups
            config: Optional detection configuration
        """
        self._scorer = confidence_scorer
        self._risk_analyzer = risk_analyzer
        self._volume_cache = volume_cache
        self._config = config or DetectionConfig()
        self._logger = structlog.get_logger(__name__)

    def detect(
        self,
        trading_range: TradingRange,
        bars: list[OHLCVBar],
        phase: WyckoffPhase,
        symbol: str,
        start_index: int = 20,
        skip_indices: Optional[set[int]] = None,
        intraday_volume_analyzer: Optional[IntradayVolumeAnalyzer] = None,
    ) -> Optional[Spring]:
        """
        Detect Spring pattern with clear validation steps.

        Args:
            trading_range: Active trading range with Creek level
            bars: OHLCV bars (minimum 20 for volume calculation)
            phase: Current Wyckoff phase (must be Phase C)
            symbol: Trading symbol
            start_index: Index to start scanning from
            skip_indices: Set of bar indices to skip
            intraday_volume_analyzer: Optional for session-relative volume

        Returns:
            Spring if detected, None otherwise
        """
        # Step 1: Input validation
        if not self._validate_inputs(trading_range, bars, phase):
            return None

        # Step 2: Initialize context
        creek_level = trading_range.creek.price
        asset_class = detect_asset_class(symbol)
        scorer = get_scorer(asset_class)
        skip_indices = skip_indices or set()

        # Step 3: Scan for candidates
        scan_start = max(20, start_index)
        for i in range(scan_start, len(bars)):
            if i in skip_indices:
                continue

            # Step 4: Find candidate
            result = self._find_spring_candidate(bars[i], i, creek_level)
            if result.candidate is None:
                continue

            # Step 5: Validate and build pattern
            spring = self._validate_and_build_pattern(
                result.candidate,
                bars,
                trading_range,
                scorer,
                intraday_volume_analyzer,
            )

            if spring is not None:
                return spring

        return None

    def _validate_inputs(
        self,
        trading_range: TradingRange,
        bars: list[OHLCVBar],
        phase: WyckoffPhase,
    ) -> bool:
        """Validate detection inputs. Returns True if valid."""
        from src.models.phase_classification import WyckoffPhase

        if trading_range is None or trading_range.creek is None:
            self._logger.error("trading_range_or_creek_missing")
            return False

        if trading_range.creek.price <= 0:
            self._logger.error("creek_price_invalid")
            return False

        if len(bars) < 20:
            self._logger.warning("insufficient_bars", bars=len(bars))
            return False

        if phase != WyckoffPhase.C:
            self._logger.debug("wrong_phase", phase=phase.value)
            return False

        return True

    def _find_spring_candidate(
        self,
        bar: OHLCVBar,
        bar_index: int,
        creek_level: Decimal,
    ) -> CandidateResult:
        """
        Find spring candidate from bar penetration.

        Returns CandidateResult with candidate if valid penetration found.
        """
        # Check penetration below Creek
        if bar.low >= creek_level:
            return CandidateResult(None, bar_index)

        # Calculate penetration percentage
        penetration_pct = (creek_level - bar.low) / creek_level

        # Validate penetration depth (max 5%)
        if penetration_pct > self._config.max_penetration_pct:
            self._logger.warning(
                "penetration_too_deep",
                pct=float(penetration_pct),
                max=float(self._config.max_penetration_pct),
            )
            return CandidateResult(None, bar_index, "penetration_too_deep")

        # Create candidate
        candidate = SpringCandidate(
            bar_index=bar_index,
            bar=bar,
            penetration_pct=penetration_pct,
            recovery_pct=Decimal("0"),  # Set during validation
            creek_level=creek_level,
        )

        return CandidateResult(candidate, bar_index)

    def _validate_and_build_pattern(
        self,
        candidate: SpringCandidate,
        bars: list[OHLCVBar],
        trading_range: TradingRange,
        scorer,
        intraday_volume_analyzer: Optional[IntradayVolumeAnalyzer],
    ) -> Optional[Spring]:
        """
        Validate candidate and build Spring pattern.

        Validates volume (FR12), recovery, and session filtering.
        """
        bar = candidate.bar
        i = candidate.bar_index
        creek_level = candidate.creek_level

        # Step 1: Volume validation (FR12)
        volume_ratio = self._calculate_volume_ratio(bars, i, intraday_volume_analyzer)
        if volume_ratio is None or volume_ratio >= self._config.volume_threshold:
            return None

        # Step 2: Recovery validation
        recovery = self._validate_recovery(bars, i, creek_level)
        if recovery is None:
            return None

        recovery_bars, recovery_price = recovery

        # Step 3: Session filtering
        rejected, rejection_reason = self._check_session_filter(bar)
        if rejected and not self._config.store_rejected_patterns:
            return None

        # Step 4: Build Spring instance
        return self._build_spring(
            candidate,
            volume_ratio,
            recovery_bars,
            recovery_price,
            trading_range,
            scorer,
            rejected,
            rejection_reason,
        )

    def _calculate_volume_ratio(
        self,
        bars: list[OHLCVBar],
        index: int,
        intraday_analyzer: Optional[IntradayVolumeAnalyzer],
    ) -> Optional[Decimal]:
        """Calculate volume ratio using cache or analyzer."""
        if self._volume_cache is not None:
            ratio = self._volume_cache.get_ratio(bars[index].timestamp)
            return ratio

        # Fallback to standard calculation
        ratio_float = calculate_volume_ratio(bars, index)
        if ratio_float is None:
            return None

        return Decimal(str(ratio_float)).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)

    def _validate_recovery(
        self,
        bars: list[OHLCVBar],
        spring_index: int,
        creek_level: Decimal,
    ) -> Optional[tuple[int, Decimal]]:
        """Validate price recovery above Creek within 5 bars."""
        recovery_end = min(spring_index + 6, len(bars))
        recovery_window = bars[spring_index + 1 : recovery_end]

        for j, bar in enumerate(recovery_window, start=1):
            if bar.close > creek_level:
                return (j, bar.close)

        return None

    def _check_session_filter(
        self,
        bar: OHLCVBar,
    ) -> tuple[bool, Optional[str]]:
        """Check session filter for intraday patterns."""
        if not self._config.session_filter_enabled:
            return (False, None)

        if self._config.timeframe not in ["1m", "5m", "15m", "1h"]:
            return (False, None)

        session = get_forex_session(bar.timestamp)
        if session in [ForexSession.ASIAN, ForexSession.NY_CLOSE]:
            reason = f"Low liquidity session: {session.value}"
            return (True, reason)

        return (False, None)

    def _build_spring(
        self,
        candidate: SpringCandidate,
        volume_ratio: Decimal,
        recovery_bars: int,
        recovery_price: Decimal,
        trading_range: TradingRange,
        scorer,
        rejected: bool,
        rejection_reason: Optional[str],
    ) -> Spring:
        """Build and return Spring instance."""
        bar = candidate.bar
        session = get_forex_session(bar.timestamp)

        return Spring(
            bar=bar,
            bar_index=candidate.bar_index,
            penetration_pct=candidate.penetration_pct,
            volume_ratio=volume_ratio,
            recovery_bars=recovery_bars,
            creek_reference=candidate.creek_level,
            spring_low=bar.low,
            recovery_price=recovery_price,
            detection_timestamp=datetime.now(UTC),
            trading_range_id=trading_range.id,
            asset_class=scorer.asset_class,
            volume_reliability=scorer.volume_reliability,
            session_quality=session,
            rejected_by_session_filter=rejected,
            rejection_reason=rejection_reason,
            rejection_timestamp=datetime.now(UTC) if rejected else None,
        )
